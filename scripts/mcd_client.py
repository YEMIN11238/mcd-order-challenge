#!/usr/bin/env python3
"""Read-only official MCP transport. Adapted from mcd-usual-migrate (MIT)."""
import copy
import json
import os
import urllib.error
import urllib.request

ALLOWED = frozenset({'now-time-info', 'query-nearby-stores', 'query-meals', 'query-meal-detail', 'calculate-price'})
ENDPOINT = 'https://mcp.mcd.cn'

class PlanError(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PlanError("MCP 返回重定向，已停止，未向其他地址发送凭证")


class LiveClient:
    mode = "live"

    def __init__(self, record=False):
        self.token = os.environ.get("MCD_MCP_TOKEN", "").strip()
        if not self.token:
            raise PlanError("请在当前进程环境设置 MCD_MCP_TOKEN，不要将 Token 写进餐单或命令参数")
        self.headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        self.sequence, self.records = 0, []
        self.record = record
        self.opener = urllib.request.build_opener(NoRedirect())
        result = self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "mcd-order-challenge", "version": "1.0.0"}})
        self.headers["MCP-Protocol-Version"] = result["protocolVersion"]
        self.rpc("notifications/initialized", notification=True)

    def rpc(self, method, params=None, notification=False):
        self.sequence += 1
        request = {"jsonrpc": "2.0", "method": method}
        if not notification:
            request["id"] = self.sequence
        if params is not None:
            request["params"] = params
        if method not in ("initialize", "notifications/initialized", "tools/list", "tools/call"):
            raise PlanError("不支持的 MCP 方法")
        if method == "tools/call" and params.get("name") not in ALLOWED:
            raise PlanError("工具不在只读白名单，已拒绝")
        req = urllib.request.Request(ENDPOINT, data=json.dumps(request).encode(), headers=self.headers)
        try:
            with self.opener.open(req, timeout=25) as response:
                sid = response.headers.get("Mcp-Session-Id")
                if sid:
                    self.headers["Mcp-Session-Id"] = sid
                raw = response.read(12_000_001)
        except urllib.error.HTTPError as error:
            raise PlanError("MCP HTTP " + str(error.code) + "；未保存错误响应或凭证")
        except (OSError, TimeoutError):
            raise PlanError("MCP 网络请求失败或超时；本轮未获得有效报价")
        if len(raw) > 12_000_000:
            raise PlanError("MCP 响应过大，停止解析")
        if notification and not raw.strip():
            return {}
        try:
            decoded = raw.decode("utf-8")
            if decoded.lstrip().startswith("{"):
                envelopes = [json.loads(decoded)]
            else:
                envelopes = [json.loads(line[5:].strip()) for line in decoded.splitlines() if line.startswith("data:") and line[5:].strip()]
            for envelope in envelopes:
                if envelope.get("id") == request.get("id"):
                    if "error" in envelope:
                        raise PlanError("MCP 返回协议错误；本轮工具调用失败")
                    return envelope["result"]
        except (ValueError, KeyError, UnicodeError):
            raise PlanError("无法解析 MCP 响应")
        if notification:
            return {}
        raise PlanError("未收到匹配请求的 MCP 响应")

    def call(self, name, arguments):
        if name not in ALLOWED:
            raise PlanError("工具不在只读白名单，已拒绝")
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise PlanError(name + " 调用失败")
        data = result.get("structuredContent")
        if data is None:
            for content in result.get("content", []):
                text = content.get("text", "")
                if "## Original Response" in text:
                    body = text.split("## Original Response", 1)[1].strip()
                    if body.startswith("```"):
                        body = body.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    try:
                        data = json.loads(body)
                        break
                    except ValueError:
                        pass
        if not isinstance(data, dict) or data.get("success") is not True:
            raise PlanError(name + " 未返回成功的业务数据")
        if self.record:
            clean = copy.deepcopy(data)
            if name == "query-meals" and isinstance(clean.get("data"), dict):
                clean["data"].pop("frequent", None)
            self.records.append({"tool": name, "arguments": copy.deepcopy(arguments), "response": clean})
        return data
