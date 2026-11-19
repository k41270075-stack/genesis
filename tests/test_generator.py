"""Generator: determinism, invariants, error plugins, rendering, disk layout."""

import os
import tempfile
import time
import unittest
from collections import Counter, defaultdict

from vouchai.config import ConfigError, resolve_config
from vouchai.episode import generate_episode, load_episode, oracle_findings, save_episode
from vouchai.grader import Issue, grade
from vouchai.render import fx_csv, jsonl, ledger_csv
from vouchai.rng import SeedError
from vouchai.timeutil import parse_ts, utc_seconds

FULL = os.environ.get("VOUCHAI_CHECK_FULL") == "1"
SEEDS = range(200) if FULL else range(24)
FIXED = {"errors": {"duplicate_invoice": {"count": 2}, "period_cutoff": {"count": 2}}}


def file_bytes(ep):
    return (ledger_csv(ep.tables["ledger"]), jsonl(ep.tables["invoices"]),
            jsonl(ep.tables["payments"]), fx_csv(ep.tables["fx"]))


def oracle_reward(ep):
    record = grade(oracle_findings(ep), episode_id=ep.episode_id,
                   issues=[Issue.from_json(i) for i in ep.issues],
                   public_ids=ep.public_ids(), inspection_steps=0)
    return record


_CACHE = {}


def episode(seed, config=None):
    key = (seed, repr(config))
    if key not in _CACHE:
        _CACHE[key] = generate_episode(seed, config)
    return _CACHE[key]


class DeterminismTest(unittest.TestCase):
    def test_same_seed_same_bytes(self):
        a = generate_episode(7, "jury_like")
        b = generate_episode(7, "jury_like")
        self.assertEqual(file_bytes(a), file_bytes(b))
        self.assertEqual(a.episode_id, b.episode_id)
        self.assertEqual(a.issues, b.issues)

    def test_different_seeds_differ(self):
        ids = {episode(s).episode_id for s in range(12)}
        self.assertEqual(len(ids), 12)
        bases = {episode(s).manifest["base_currency"] for s in range(12)}
        offsets = {episode(s).manifest["timezone"] for s in range(12)}
        self.assertGreater(len(bases), 1)
        self.assertGreater(len(offsets), 2)

    def test_render_seeds_change_only_ids_and_order(self):
        a = episode(5, FIXED)
        cfg = {"preset": "default",
               "overrides": dict(FIXED, render={"id_seed": 3, "order_seed": 9})}
        b = generate_episode(5, cfg)
        self.assertNotEqual(a.episode_id, b.episode_id)
        self.assertFalse({r["row_id"] for r in a.tables["ledger"]} &
                         {r["row_id"] for r in b.tables["ledger"]})
        def amounts(ep):
            return Counter((r["account"], r["debit_minor"], r["credit_minor"])
                           for r in ep.tables["ledger"])
        self.assertEqual(amounts(a), amounts(b))
        self.assertEqual(sorted((i["type"], i["expected_amount_minor"]) for i in a.issues),
                         sorted((i["type"], i["expected_amount_minor"]) for i in b.issues))
        self.assertEqual(oracle_reward(b)["reward"], 1.0)

    def test_generation_time(self):
        worst = 0
        for seed in range(100, 110):
            t0 = time.monotonic()
            generate_episode(seed, "L5")
            worst = max(worst, time.monotonic() - t0)
        self.assertLess(worst, 3)


class EpisodeShapeTest(unittest.TestCase):
    def test_every_episode_is_consistent(self):
        for seed in SEEDS:
            for config in (None, "jury_like", FIXED):
                ep = episode(seed, config)
                with self.subTest(seed=seed, config=config):
                    self._check(ep)

    def _check(self, ep):
        m, t = ep.manifest, ep.tables
        start, end = parse_ts(m["period_start"]), parse_ts(m["period_end"])
        self.assertTrue(200 <= m["counts"]["ledger_rows"] <= 2000)
        self.assertEqual(m["counts"]["ledger_rows"], len(t["ledger"]))
        # I1, I2: balanced in total and per entry (entry = rows of one timestamp)
        by_ts = defaultdict(lambda: [0, 0])
        for r in t["ledger"]:
            self.assertTrue((r["debit_minor"] > 0) != (r["credit_minor"] > 0))
            self.assertEqual(r["currency"], m["base_currency"])
            by_ts[r["timestamp"]][0] += r["debit_minor"]
            by_ts[r["timestamp"]][1] += r["credit_minor"]
        self.assertTrue(all(d == c for d, c in by_ts.values()))
        # I10: IDs globally unique, references exist
        ids = [r["row_id"] for r in t["ledger"]] + [r["doc_id"] for r in t["invoices"]] + \
              [r["doc_id"] for r in t["payments"]] + [r["invoice_id"] for r in t["invoices"]] + \
              [r["payment_id"] for r in t["payments"]] + [r["id"] for r in t["fx"]]
        self.assertEqual(len(ids), len(set(ids)))
        invoice_ids = {r["invoice_id"] for r in t["invoices"]}
        payment_ids = {r["payment_id"] for r in t["payments"]}
        for r in t["ledger"]:
            self.assertTrue(r["invoice_id"] is None or r["invoice_id"] in invoice_ids)
            self.assertTrue(r["payment_id"] is None or r["payment_id"] in payment_ids)
        for p in t["payments"]:
            refs = p["invoice_refs"]
            self.assertTrue(refs is None or (refs and set(refs) <= invoice_ids))
        # I12: nothing within 60 s of a period edge
        stamps = [r["timestamp"] for r in t["ledger"]] + [r["issued_at"] for r in t["invoices"]] \
            + [r["timestamp"] for r in t["payments"]]
        for s in stamps:
            for edge in (start, end):
                self.assertGreaterEqual(abs(utc_seconds(parse_ts(s)) - utc_seconds(edge)), 60)
        # I13, I16
        for inv in t["invoices"]:
            lines = inv["line_items"]
            self.assertEqual(inv["total_minor"], sum(li["amount_minor"] for li in lines))
        pairs = [(r["date"], r["source_currency"], r["target_currency"]) for r in t["fx"]]
        self.assertEqual(len(pairs), len(set(pairs)))
        # truth
        public = ep.public_ids()
        keys = set()
        for issue in ep.issues:
            keys.add((issue["type"], frozenset(issue["affected_ids"])))
            self.assertTrue(set(issue["affected_ids"]) <= public)
            self.assertTrue(all(slot and set(slot) <= public for slot in issue["evidence_slots"]))
            self.assertLessEqual(len(issue["evidence_slots"]), 10)
            self.assertLessEqual(len(issue["evidence_sets"]), 64)
            self.assertGreaterEqual(issue["expected_amount_minor"],
                                    10 ** m["currency_exponents"][m["base_currency"]])
            if issue["type"] in ("duplicate_invoice", "period_cutoff"):
                carriers = [r for r in t["ledger"] if r["row_id"] in issue["carrier_row_ids"]]
                self.assertEqual(sum(r["debit_minor"] for r in carriers),
                                 issue["expected_amount_minor"])
            self.assertTrue(issue["carrier_row_ids"])
            self._check_manifestation(ep, issue, start, end)
        self.assertEqual(len(keys), len(ep.issues))
        self.assertEqual(oracle_reward(ep)["reward"], 1.0)

    def _check_manifestation(self, ep, issue, start, end):
        t = ep.tables
        if issue["type"] == "duplicate_invoice" and len(issue["affected_ids"]) == 1:
            inv = issue["affected_ids"][0]
            issuing = {r["timestamp"] for r in t["ledger"]
                       if r["invoice_id"] == inv and r["account"] == "4000"}
            self.assertEqual(len(issuing), 2)
        elif issue["type"] == "duplicate_invoice":
            a, b = [next(i for i in t["invoices"] if i["invoice_id"] == x)
                    for x in issue["affected_ids"]]
            for f in ("entity_id", "issued_at", "currency", "total_minor", "line_items"):
                self.assertEqual(a[f], b[f])
        elif issue["type"] == "period_cutoff":
            target = issue["affected_ids"][0]
            doc = next((i for i in t["invoices"] if i["invoice_id"] == target), None)
            event = doc["issued_at"] if doc else next(
                p["timestamp"] for p in t["payments"] if p["payment_id"] == target)
            posted = next(r["timestamp"] for r in t["ledger"]
                          if r["row_id"] in issue["carrier_row_ids"])

            def zone(ts):
                x = parse_ts(ts)
                return -1 if x < start else (0 if x < end else 1)

            self.assertNotEqual(zone(event), zone(posted))

    def test_all_types_and_interactions_occur(self):
        types, groups = set(), set()
        for seed in range(16):
            ep = episode(seed, "L5")
            types.update(i["type"] for i in ep.issues)
            groups.update(i["interaction_group"] for i in ep.issues if i["interaction_group"])
            self.assertEqual(ep.provenance["unplaced_errors"], [])
        self.assertEqual(types, {"duplicate_invoice", "payment_allocation", "fx_conversion",
                                 "period_cutoff"})
        self.assertEqual(groups, {"X1", "X2"})

    def test_interaction_x1_shape(self):
        for seed in range(16):
            ep = episode(seed, "L5")
            x1 = [i for i in ep.issues if i["interaction_group"] == "X1"]
            if not x1:
                continue
            fx, alloc = x1
            self.assertEqual((fx["type"], alloc["type"]), ("fx_conversion", "payment_allocation"))
            pay_id = fx["affected_ids"][0]
            self.assertEqual(alloc["affected_ids"][0], pay_id)
            pay = next(p for p in ep.tables["payments"] if p["payment_id"] == pay_id)
            stamp = parse_ts(pay["timestamp"])
            start, end = (parse_ts(ep.manifest["period_start"]),
                          parse_ts(ep.manifest["period_end"]))
            self.assertTrue(start <= stamp < end)          # in the period by company time
            utc_day = stamp.astimezone(parse_ts("2000-01-01T00:00:00+00:00").tzinfo).date()
            local_day = stamp.astimezone(start.tzinfo).date()
            self.assertNotEqual(utc_day, local_day)        # but another day (period) in UTC

    def test_doubles_present_in_clean_books(self):
        totals = Counter()
        for seed in range(16):
            totals.update(episode(seed, "clean").provenance["doubles"])
        for name in ("D2_split_payments", "D5_fees", "D17_two_step", "D19_multi_invoice"):
            self.assertGreater(totals[name], 0, name)

    def test_clean_preset_has_no_issues(self):
        for seed in range(6):
            ep = episode(seed, "clean")
            self.assertEqual(ep.issues, [])
            self.assertEqual(oracle_reward(ep)["reward"], 1.0)

    def test_counterfactual_twin(self):
        both = {"errors": {"duplicate_invoice": {"count": 1}, "period_cutoff": {"count": 1}}}
        only = {"errors": {"duplicate_invoice": {"count": 1}, "period_cutoff": {"count": 0}}}
        checked = 0
        for seed in range(8):
            a, b = generate_episode(seed, both), generate_episode(seed, only)
            if a.provenance["attempt"] or b.provenance["attempt"]:
                continue
            ia = [i for i in a.issues if i["type"] == "duplicate_invoice"]
            ib = [i for i in b.issues if i["type"] == "duplicate_invoice"]
            self.assertEqual([{k: v for k, v in i.items() if k != "issue_id"} for i in ia],
                             [{k: v for k, v in i.items() if k != "issue_id"} for i in ib])
            checked += 1
        self.assertGreater(checked, 3)


class DiskTest(unittest.TestCase):
    def test_save_load_roundtrip(self):
        ep = episode(3, FIXED)
        with tempfile.TemporaryDirectory() as tmp:
            save_episode(ep, tmp)
            for name in ("ledger.csv", "fx.csv", "invoices.jsonl", "payments.jsonl"):
                data = open(os.path.join(tmp, "public", name), "rb").read()
                self.assertNotIn(b"\r\n", data)
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
            loaded = load_episode(tmp)
        self.assertEqual(loaded.episode_id, ep.episode_id)
        self.assertEqual(loaded.tables, ep.tables)
        self.assertEqual(loaded.issues, ep.issues)
        self.assertEqual(file_bytes(loaded), file_bytes(ep))


class ConfigTest(unittest.TestCase):
    def test_rejects(self):
        for config in ("nope", {"preset": "nope"}, {"size": {"customers": 1}},
                       {"bogus": 1}, {"interactions": {"partial_fx_boundary": 7}},
                       {"interactions": {"x3": 1}}, {"mix": "chaos"},
                       {"errors": {"period_cutoff": {"count": 13}}}, 5, ["x"],
                       {"company": {"timezone": "+25:00"}}):
            with self.assertRaises(ConfigError, msg=repr(config)):
                resolve_config(config, 1)
        for seed in (True, -1, 1.5):
            with self.assertRaises(SeedError):
                generate_episode(seed)

    def test_seed_and_config_variants(self):
        self.assertEqual(resolve_config(None, 4), resolve_config({"preset": "default"}, 4))
        generate_episode(2 ** 64 - 1, "smoke")
        cfg = resolve_config({"company": {"base_currency": "USD", "timezone": "-05:00"}}, 9)
        self.assertEqual((cfg["company"]["base_currency"], cfg["company"]["timezone"]),
                         ("USD", "-05:00"))
        self.assertEqual(resolve_config({"size": {"foreign_share": 0.25}}, 1)["size"]
                         ["foreign_share"], "1/4")


if __name__ == "__main__":
    unittest.main()
