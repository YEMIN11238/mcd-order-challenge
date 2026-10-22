#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect a new private, read-only test snapshot. Does not publish or replace the deck."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys

from mcd_client import LiveClient, PlanError

UTC8 = dt.timezone(dt.timedelta(hours=8))


def collect(client, reservation=None):
    client.call("now-time-info", {})
    stores = client.call("query-nearby-stores", {"beType": 1, "searchType": 2, "city": "上海", "keyword": "南京东路"})["data"]
    for store in ["1450104", "1450056"]:
        if not any(s["storeCode"] == store for s in stores):
            raise PlanError("测试门店未在本轮结果中出现，停止采集")
        args = {"storeCode": store, "beType": 1, "orderType": 1}
        if reservation:
            args["reservationDate"] = reservation
        menu = client.call("query-meals", args)["data"]
        codes = ["9900005462", "9900000890"] if store == "1450104" else ["9900005462"]
        for product in codes:
            if product not in menu.get("meals", {}):
                raise PlanError("测试套餐已不在本轮菜单中，不能继续复用旧编码")
            detail = client.call("query-meal-detail", dict(args, code=product))["data"]
            variants = [[str(rd["choices"][0]["code"]) for rd in detail["rounds"]]] if product == "9900000890" else [["1406", "4810", "3050"], ["1406", "4820", "3050"], ["1406", "4810", "3100"]] if store == "1450104" else [["1406", "4820", "3050"]]
            for choices in variants:
                if len(choices) != len(detail["rounds"]):
                    raise PlanError("套餐轮次已改变，先人工审题")
                rounds = []
                for rd, code in zip(detail["rounds"], choices):
                    if rd.get("quantity") != 1 or not any(str(c["code"]) == code for c in rd["choices"]):
                        raise PlanError("所选规格在本店详情中不再可用，先人工审题")
                    rounds.append({"round": str(rd["id"]), "comboItemList": [{"code": code, "quantity": 1}]})
                client.call("calculate-price", dict(args, needTableware=False, items=[{"productCode": product, "quantity": 1, "roundList": rounds}]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reservation", help="明确指定技术测试预约时段，格式 yyyy-MM-dd HH:mm；不创建预约或订单")
    parser.add_argument("--out", type=Path, help="新建采集文件；默认 .mcd-private/ 下的唯一文件")
    args = parser.parse_args()
    if args.reservation:
        try:
            dt.datetime.strptime(args.reservation, "%Y-%m-%d %H:%M")
        except ValueError:
            parser.error("预约时间格式应为 yyyy-MM-dd HH:mm")
    stamp = dt.datetime.now(UTC8).strftime("%Y%m%d-%H%M%S")
    path = args.out or Path(".mcd-private") / ("candidate-" + stamp + ".json")
    if path.exists():
        parser.error("采集输出已存在，不覆盖旧记录")
    client = None
    error = None
    try:
        client = LiveClient(record=True)
        collect(client, args.reservation)
    except PlanError as exc:
        error = str(exc)
    if client and client.records:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {"version": 1, "captured_at": dt.datetime.now(UTC8).isoformat(timespec="seconds"), "reservation": args.reservation, "complete": error is None, "calls": client.records}
        for index, record in enumerate(payload["calls"]):
            record["id"] = stamp + "-" + str(index + 1).zfill(2)
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(json.dumps({"saved": str(path), "calls": len(client.records), "complete": error is None}, ensure_ascii=False))
    if error:
        print(error, file=sys.stderr)
        return 1
    print("采集完毕；这是一份候选证据，没有修改已发布题目。先审查事实、题干、唯一答案与脱敏，再发布新题库版本。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
