import copy
import json
import tempfile
import unittest
from pathlib import Path
from research_harness.core import Workspace

ROOT = Path(__file__).resolve().parents[1]


class GatesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Workspace(self.temp.name)
        self.p = json.loads((ROOT / "examples/protocol.json").read_text())
        self.r = json.loads((ROOT / "examples/result.json").read_text())
        self.ws.register(self.p)

    def result(self, seed, effect=0.8):
        result = copy.deepcopy(self.r)
        result.update(seed=seed, candidate_score=10 - effect)
        return result

    def test_success_requires_all_planned_replications(self):
        for seed in (11, 22):
            self.assertEqual(self.ws.record(self.p["id"], self.result(seed))["status"], "PENDING")
        report = self.ws.record(self.p["id"], self.result(33))
        self.assertEqual(report["status"], "CONTINUE")
        self.assertAlmostEqual(report["mean_effect"], 0.8)
        self.assertAlmostEqual(report["total_usd"], 0.3)
        self.assertEqual(report["mean_latency_ms"], 5)
        self.assertEqual(self.ws.evaluate(self.p["id"]), report)

    def test_below_threshold_stops_and_closes(self):
        for seed in (11, 22, 33):
            report = self.ws.record(self.p["id"], self.result(seed, 0.2))
        self.assertEqual(report["status"], "STOP")
        with self.assertRaises(ValueError):
            self.ws.record(self.p["id"], self.result(11, 2))

    def test_best_seed_cannot_rescue_regression(self):
        for seed, effect in ((11, 3), (22, 3), (33, -0.1)):
            report = self.ws.record(self.p["id"], self.result(seed, effect))
        self.assertEqual(report["status"], "STOP")

    def test_duplicate_unplanned_and_nonfinite_rejected(self):
        for seed, effect in ((44, 1), (11, float("nan"))):
            with self.assertRaises(ValueError):
                self.ws.record(self.p["id"], self.result(seed, effect))
        self.ws.record(self.p["id"], self.result(11))
        with self.assertRaises(ValueError):
            self.ws.record(self.p["id"], self.result(11))

    def test_invalid_and_budget_stop_immediately(self):
        result = self.result(11)
        result["validity"]["No test leakage"] = False
        self.assertEqual(self.ws.record(self.p["id"], result)["status"], "STOP")
        other = copy.deepcopy(self.p)
        other["id"] = "budget"
        self.ws.register(other)
        result = self.result(11)
        result["costs"]["compute_usd"] = 31
        self.assertEqual(self.ws.record("budget", result)["status"], "STOP")

    def test_protocol_changes_detected(self):
        path = self.ws.folder(self.p["id"]) / "protocol.json"
        envelope = json.loads(path.read_text())
        envelope["protocol"]["minimum_effect"] = 0.01
        path.write_text(json.dumps(envelope))
        with self.assertRaises(ValueError):
            self.ws.evaluate(self.p["id"])

    def test_registration_never_overwrites(self):
        with self.assertRaises(FileExistsError):
            self.ws.register(self.p)

    def test_higher_metric_direction(self):
        p = copy.deepcopy(self.p)
        p.update(id="higher", primary_metric={"name": "score", "unit": "points", "direction": "higher"})
        self.ws.register(p)
        for seed in p["seeds"]:
            result = self.result(seed)
            result["candidate_score"] = 11
            report = self.ws.record("higher", result)
        self.assertEqual(report["status"], "CONTINUE")


if __name__ == "__main__":
    unittest.main()
