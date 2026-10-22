#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build five reviewed questions; prices and answers are computed from MCP records."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/YEMIN11238/mcd-order-challenge"
TOOLS = {"now-time-info", "query-nearby-stores", "query-meals", "query-meal-detail", "calculate-price"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def money(fen):
    return "¥{:.2f}".format(fen / 100)


class Evidence:
    def __init__(self, root=ROOT):
        self.records, self.files = {}, []
        for path in sorted((root / "evidence").glob("official-*.json")):
            raw = path.read_bytes()
            payload = json.loads(raw)
            self.files.append({"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
            for call in payload["calls"]:
                require(call["id"] not in self.records, "Duplicate evidence ID")
                require(call["tool"] in TOOLS, "Unexpected tool in evidence")
                require(call["response"].get("success") is True, "Failed responses cannot substantiate an answer")
                require(call["response"].get("traceId") and call["response"].get("datetime"), "Missing official provenance")
                self.records[call["id"]] = dict(call, file=path.relative_to(root).as_posix())

    def quote(self, key):
        call = self.records[key]
        require(call["tool"] == "calculate-price", "Price must come from calculate-price")
        args, data = call["arguments"], call["response"]["data"]
        require(type(data.get("price")) is int and data["price"] > 0, "Invalid integer-fen quote")
        require(len(args["items"]) == 1 and args["items"][0]["quantity"] == 1, "This deck uses one combo per quote")
        item = args["items"][0]
        require(not args.get("withOrder") and not item.get("couponCode") and not item.get("couponId"), "Deck assumes no coupons or with-order card")
        detail = next((c["response"]["data"] for c in self.records.values() if c["tool"] == "query-meal-detail" and c["arguments"]["storeCode"] == args["storeCode"] and c["arguments"].get("reservationDate") == args.get("reservationDate") and c["arguments"]["code"] == item["productCode"]), None)
        require(detail is not None, "Quote has no matching store/time detail")
        cart = []
        require(len(detail["rounds"]) == len(item["roundList"]), "Incomplete combo")
        for rd in item["roundList"]:
            source = next(x for x in detail["rounds"] if str(x["id"]) == rd["round"])
            require(len(rd["comboItemList"]) == 1, "One choice per round required")
            choice = rd["comboItemList"][0]
            require(choice["quantity"] == 1, "Invalid choice quantity")
            actual = next((c for c in source["choices"] if str(c["code"]) == choice["code"]), None)
            require(actual is not None, "Choice is absent from matching detail")
            if choice.get("modification"):
                available = [(str(v["code"]), str(v.get(k))) for group in actual.get("modification", {}).get("items", []) for v in group.get("values", []) for k in ["selectedKey", "unselectedKey"] if v.get(k) is not None]
                for value in choice["modification"]["values"]:
                    require((value["code"], value["key"]) in available, "Modification key not from this detail")
            cart.append(actual["name"])
        require(any(p["productCode"] == item["productCode"] and p["quantity"] == 1 for p in data["productList"]), "Quote did not echo the combo")
        names = [s["storeName"] for c in self.records.values() if c["tool"] == "query-nearby-stores" for s in c["response"]["data"] if s["storeCode"] == args["storeCode"]]
        return {"sourceId": key, "storeCode": args["storeCode"], "store": names[-1], "product": detail["name"], "cart": cart, "priceFen": data["price"], "at": call["response"]["datetime"], "reservation": args.get("reservationDate")}

    def sources(self, keys):
        result = []
        for key in keys:
            call = self.records[key]
            row = {"id": key, "tool": call["tool"], "at": call["response"]["datetime"], "traceId": call["response"]["traceId"], "file": call["file"], "storeCode": call["arguments"].get("storeCode"), "reservation": call["arguments"].get("reservationDate")}
            if call["tool"] == "calculate-price":
                row["priceFen"] = call["response"]["data"]["price"]
            result.append(row)
        return result


def plan_option(key, plan, subtitle):
    return {"id": key, "title": " · ".join(plan["cart"]), "subtitle": subtitle, "priceFen": plan["priceFen"], "sourceId": plan["sourceId"]}


def build(root=ROOT):
    e = Evidence(root)
    medium, large, cup, other = [e.quote(key) for key in ["20261023-07", "20261023-08", "20261023-09", "20261023-12"]]
    curry, fries = e.quote("20261020-03"), e.quote("20261020-05")
    promo = e.quote("20261023-05")
    menu = e.records["20261023-03"]["response"]["data"]["meals"]["9900000890"]
    display = int(Decimal(menu["currentPrice"]) * 100)
    require(menu["discountType"] == "随单购麦金卡优惠", "Promo condition changed; review this question")
    require(display != promo["priceFen"], "No display/quote difference; review this question")
    require(display == 2800, "Menu display changed; review the fixed 28-yuan title")
    require(medium["cart"] == ["板烧鸡腿堡", "中薯条", "可乐中杯"], "Unexpected baseline")
    require(large["cart"] == other["cart"], "Store comparison must keep composition identical")
    require(medium["cart"][:2] == cup["cart"][:2], "Drink comparison changed other items")
    delta = cup["priceFen"] - medium["priceFen"]
    require(delta > 0 and delta != cup["priceFen"], "Review drink-upgrade choices")
    valid_budget = [p for p in [large, medium] if p["priceFen"] <= 3500]
    require(len(valid_budget) == 1, "Budget question must have exactly one answer")
    require(medium["priceFen"] <= 3500 < large["priceFen"], "Budget ordering changed; review the explanation")
    required = "马来咖喱风味薄皮肉骨鸡3块"
    require(required in curry["cart"] and required not in fries["cart"], "Required-side question changed")
    require(curry["priceFen"] - fries["priceFen"] == 100, "Review the fixed one-yuan title")
    detail_b = e.records["20261020-04"]["response"]["data"]
    require(not any(c["name"] == required for rd in detail_b["rounds"] for c in rd["choices"]), "Availability difference no longer supported")
    require(large["priceFen"] > other["priceFen"], "Store price ordering changed; review choices")
    gap = large["priceFen"] - other["priceFen"]
    questions = [
        {"id": "budget", "tag": "预算关", "title": "35 元，这顿怎么选？", "story": "在悦荟广场店，想吃板烧鸡腿堡和中杯可乐，薯条选中份或大份都可以。预算不超过 35 元，下面哪份符合？", "conditions": ["预算 ≤ ¥35", "同一家店", "薯条规格可调整"], "context": "2026-10-23 采集 · 测试预约 12:00 自取", "options": [plan_option("large", large, "大薯条方案"), plan_option("medium", medium, "中薯条方案")], "correctId": "medium" if valid_budget[0] == medium else "large", "verdict": "先过预算，再看搭配。", "explanation": f"本次中薯方案核价 {money(medium['priceFen'])}，大薯方案 {money(large['priceFen'])}。明确允许调整规格时，中薯方案在 35 元以内；大薯方案超出 {money(large['priceFen']-3500)}。", "takeaway": "比较的是整份餐的官方核价，套餐名称相同也可能因选项不同而改变总价。", "sourceIds": [medium["sourceId"], large["sourceId"]]},
        {"id": "must-keep", "tag": "口味关", "title": "便宜 1 元，就能替你换吗？", "story": "你坚持小食必须是咖喱风味肉骨鸡 3 块；板烧去烤味酱、中杯无糖可乐去冰也要保留。这两份已核价方案，哪份符合你的要求？", "conditions": ["咖喱肉骨鸡必须保留", "不接受改成薯条", "去酱 · 无糖 · 去冰"], "context": "2026-10-20 历史即时自取实测", "options": [plan_option("keep", curry, "悦荟广场 · 原小食"), plan_option("swap", fries, "食品一店 · 改成大薯条")], "correctId": "keep", "verdict": "必须项，不能被低价覆盖。", "explanation": f"悦荟广场的 {money(curry['priceFen'])} 方案包含指定的小食。食品一店 {money(fries['priceFen'])} 的实际小食是大薯条。本次该店同套餐详情未列出咖喱肉骨鸡；只有明确允许替代后，这个改餐方案才成立。", "takeaway": "这是本次套餐选项的差异，不能据此判断全店缺货或永久停售。特制参数已提交，核价不证明实际出餐。", "sourceIds": ["20261020-02", curry["sourceId"], "20261020-04", fries["sourceId"]]},
        {"id": "upgrade", "tag": "加价关", "title": "只把可乐升杯，多付多少？", "story": f"同店、同一板烧三件套，板烧和中薯条保持不变。中杯可乐方案核价 {money(medium['priceFen'])}，大杯可乐方案核价 {money(cup['priceFen'])}。这一次升杯的增量是多少？", "conditions": ["同店 · 同一时段", "只改可乐杯型", "求增量，不是求总价"], "context": "2026-10-23 采集 · 测试预约 12:00 自取", "options": [{"id": "zero", "title": "没有增加", "subtitle": "觉得套餐内换选项都免费", "amountFen": 0}, {"id": "total", "title": money(cup["priceFen"]), "subtitle": "把新套餐总价当作升杯费用", "amountFen": cup["priceFen"]}, {"id": "delta", "title": money(delta), "subtitle": "用两份整单核价相减", "amountFen": delta}], "correctId": "delta", "verdict": "增量，要用同条件的两份报价相减。", "explanation": f"{money(cup['priceFen'])} − {money(medium['priceFen'])} = {money(delta)}。两份请求都保留板烧和中薯，仅将可乐中杯换为大杯。这里没有把饮料单点价当作套餐升杯费。", "takeaway": "这是该次、该店、该组合的差额，不是全国通用的升杯价。", "sourceIds": [medium["sourceId"], cup["sourceId"]]},
        {"id": "stores", "tag": "换店关", "title": "同一份餐，两家店一定同价吗？", "story": f"本次都选板烧鸡腿堡、大薯条、中杯可乐，不用券、不随单购卡。悦荟广场核价 {money(large['priceFen'])}，食品一店核价 {money(other['priceFen'])}。哪一个判断成立？", "conditions": ["餐品与份数相同", "相同预约时段", "只比较这两份报价"], "context": "2026-10-23 采集 · 测试预约 12:00 自取", "options": [{"id": "a", "title": f"悦荟广场少付 {money(gap)}", "subtitle": "选择悦荟广场"}, {"id": "b", "title": f"食品一店少付 {money(gap)}", "subtitle": "选择食品一店"}, {"id": "same", "title": "两家价格相同", "subtitle": "觉得同套餐应该统一价格"}], "correctId": "b", "verdict": "同一搭配，也要逐店核价。", "explanation": f"食品一店 {money(other['priceFen'])}，比悦荟广场 {money(large['priceFen'])} 少 {money(gap)}。这两份请求的商品、数量、餐段和渠道一致，比较依据是官方总金额。", "takeaway": "这没有计算路程与时间成本，也不代表食品一店所有餐品都更便宜。", "sourceIds": [large["sourceId"], other["sourceId"]]},
        {"id": "promo", "tag": "压轴关", "title": "菜单写 28，这次真付 28 吗？", "story": f"板烧鸡腿堡四件套，菜单 currentPrice 展示 {money(display)}，并标注“{menu['discountType']}”。本次选板烧、中薯、麦乐鸡 4 块和中杯可乐，不用券、不随单购卡。应按哪个金额判断这份报价？", "conditions": ["菜单展示价有条件", "本次不随单购卡", "已取得官方整单核价"], "context": "2026-10-23 采集 · 测试预约 12:00 自取", "options": [{"id": "quote", "title": money(promo["priceFen"]), "subtitle": "本次 calculate-price 返回的应付", "amountFen": promo["priceFen"]}, {"id": "display", "title": money(display), "subtitle": "直接把菜单展示价当应付", "amountFen": display}, {"id": "order-first", "title": "必须先下单才知道", "subtitle": "觉得单独核价无法得到总金额"}], "correctId": "quote", "verdict": "有附加条件的展示价，先核整单。", "explanation": f"这次 calculate-price 返回 price={promo['priceFen']} 分，即 {money(promo['priceFen'])}，与菜单展示的 {money(display)} 相差 {money(promo['priceFen']-display)}。请求没有 withOrder 随单购卡参数，也没有券；全程没有创建订单。", "takeaway": "没有测试购卡后的整单费用，不能据此推算开卡是否划算；也不能把本次报价当成所有人的固定价。", "sourceIds": ["20261023-03", "20261023-04", promo["sourceId"]]}
    ]
    for q in questions:
        require(sum(o["id"] == q["correctId"] for o in q["options"]) == 1, "Answer must be unique")
        q["sources"] = e.sources(q.pop("sourceIds"))
        q["evidenceUrl"] = REPO + "/blob/main/docs/evidence.md#" + q["id"]
    return {"version": 1, "deckId": "verified-20261023-v1", "title": "麦麦点餐挑战", "mode": "recorded", "repo": REPO, "playUrl": "https://yemin11238.github.io/mcd-order-challenge/", "recordDates": ["2026-10-20", "2026-10-23"], "sourceFiles": e.files, "questions": questions}


def evidence_markdown(data):
    lines = ["# 五道题的真实证据", "", "题目使用历史官方 MCP 响应。错选项是用于辨析的判断，不是新增官方报价。所有正确金额、组成与答案均由 `scripts/build_quiz.py` 从下面的业务记录生成。", "", "2026-10-23 采集时门店已打烊；新增查询明确使用测试预约 `2026-10-23 12:00`，只查菜单、详情与核价，没有预约或创建订单。2026-10-20 为此前即时自取记录。所有时间均为北京时间。", "", "## 来源文件", ""]
    for source in data["sourceFiles"]:
        lines += [f"- [{source['path']}](../{source['path']})，SHA-256 `{source['sha256']}`"]
    for q in data["questions"]:
        answer = next(o for o in q["options"] if o["id"] == q["correctId"])
        answer_text = answer["title"] + (" " + money(answer["priceFen"]) if "priceFen" in answer else "")
        lines += ["", f"<a id=\"{q['id']}\"></a>", f"## {q['tag']}：{q['title']}", "", q["story"], "", "**正确选择：" + answer_text + "**", "", q["explanation"], "", q["takeaway"], "", "| 记录 ID | 工具 | 核价应付 | 响应时间 | traceId |", "|---|---|---:|---|---|"]
        for s in q["sources"]:
            lines.append(f"| {s['id']} | {s['tool']} | {money(s['priceFen']) if 'priceFen' in s else '—'} | {s['at']} | `{s['traceId']}` |")
    lines += ["", "## 核验边界", "", "原始业务响应保留工具名、请求参数、响应时间与 traceId；未保存认证头或 MCP 会话标识，菜单 frequent 已移除。公开内容为指定技术测试地点的门店信息，不是用户位置或个人历史订单。", "", "核价成功确认套餐、数量与总金额；响应未逐项回显所有特制，未验证出餐。题库只比较有限候选，不能证明全国价格、全局最便宜或持续供应。", "", "10 月 20 日的 5 条证据摘自作者此前作品 [mcd-usual-migrate](https://github.com/YEMIN11238/mcd-usual-migrate/tree/main/examples)，保留原始 traceId。新增 12 次业务调用与 5 次核价在本项目开发时完成。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify generated files without changing them")
    args = parser.parse_args()
    data = build()
    outputs = {ROOT / "web/quiz.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n", ROOT / "docs/evidence.md": evidence_markdown(data)}
    for path, content in outputs.items():
        if args.check:
            require(path.exists() and path.read_text(encoding="utf-8") == content, "Generated file is stale: " + str(path))
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text(content, encoding="utf-8")
    print("Verified" if args.check else "Built", len(data["questions"]), "evidence-backed questions")


if __name__ == "__main__":
    main()
