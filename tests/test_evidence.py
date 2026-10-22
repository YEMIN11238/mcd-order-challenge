# -*- coding: utf-8 -*-
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


b = module("build_quiz")
c = module("mcd_client")


class EvidenceTests(unittest.TestCase):
    def test_five_answers_are_derived_from_reviewed_official_records(self):
        deck = b.build()
        self.assertEqual(len(deck["questions"]), 5)
        self.assertEqual([q["correctId"] for q in deck["questions"]], ["medium", "keep", "delta", "b", "quote"])
        self.assertEqual(next(o for o in deck["questions"][2]["options"] if o["id"] == "delta")["amountFen"], 200)
        self.assertEqual(deck["mode"], "recorded")

    def test_every_displayed_official_price_matches_its_actual_response(self):
        records = b.Evidence().records
        for q in b.build()["questions"]:
            self.assertTrue(q["sources"])
            for option in q["options"]:
                if "priceFen" in option:
                    raw = records[option["sourceId"]]["response"]
                    self.assertEqual(option["priceFen"], raw["data"]["price"])
            for source in q["sources"]:
                raw = records[source["id"]]["response"]
                self.assertEqual(source["traceId"], raw["traceId"])
                self.assertEqual(source["at"], raw["datetime"])

    def mutate(self, filename, apply):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        shutil.copytree(ROOT / "evidence", root / "evidence")
        path = root / "evidence" / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        apply(data)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return root

    def test_second_budget_answer_is_rejected_instead_of_silently_publishing(self):
        def change(data):
            next(x for x in data["calls"] if x["id"] == "20261023-08")["response"]["data"]["price"] = 3400
        with self.assertRaisesRegex(ValueError, "exactly one"):
            b.build(self.mutate("official-20261023.json", change))

    def test_missing_price_is_never_converted_to_a_zero_price(self):
        def change(data):
            next(x for x in data["calls"] if x["id"] == "20261023-07")["response"]["data"].pop("price")
        with self.assertRaisesRegex(ValueError, "integer-fen"):
            b.build(self.mutate("official-20261023.json", change))

    def test_changed_store_composition_blocks_price_comparison(self):
        def change(data):
            call = next(x for x in data["calls"] if x["id"] == "20261023-12")
            call["arguments"]["items"][0]["roundList"][1]["comboItemList"][0]["code"] = "4810"
        with self.assertRaisesRegex(ValueError, "composition identical"):
            b.build(self.mutate("official-20261023.json", change))

    def test_invalid_store_choice_cannot_be_used_as_evidence(self):
        def change(data):
            call = next(x for x in data["calls"] if x["id"] == "20261023-07")
            call["arguments"]["items"][0]["roundList"][1]["comboItemList"][0]["code"] = "not-an-official-choice"
        with self.assertRaisesRegex(ValueError, "absent"):
            b.build(self.mutate("official-20261023.json", change))

    def test_failed_business_response_cannot_support_an_answer(self):
        def change(data):
            data["calls"][0]["response"]["success"] = False
        with self.assertRaisesRegex(ValueError, "Failed responses"):
            b.build(self.mutate("official-20261023.json", change))

    def test_public_recordings_do_not_contain_authentication_or_user_history_fields(self):
        forbidden = {"authorization", "cookie", "set-cookie", "mcp-session-id", "frequent", "token", "openid", "mobile", "phone"}
        def walk(data):
            if isinstance(data, dict):
                for key, value in data.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(value)
            elif isinstance(data, list):
                for value in data:
                    walk(value)
        for path in (ROOT / "evidence").glob("official-*.json"):
            walk(json.loads(path.read_text(encoding="utf-8")))

    def test_generated_deck_matches_evidence_and_hashes(self):
        actual = json.loads((ROOT / "web/quiz.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, b.build())
        self.assertEqual((ROOT / "docs/evidence.md").read_text(encoding="utf-8"), b.evidence_markdown(actual))

    def test_write_calls_fail_before_any_network_request(self):
        client = c.LiveClient.__new__(c.LiveClient)
        client.sequence, client.headers = 0, {}
        with patch("urllib.request.Request") as network:
            for tool in ["create-order", "cancel-order", "auto-bind-coupons", "mall-create-order", "draw-lottery", "delivery-create-address"]:
                with self.assertRaises(c.PlanError):
                    client.call(tool, {})
                with self.assertRaises(c.PlanError):
                    client.rpc("tools/call", {"name": tool, "arguments": {}})
            network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
