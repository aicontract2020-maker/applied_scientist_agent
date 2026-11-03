"""Deterministic research gates; results are reported, not independently verified.

Use one writer per workspace. Hashes detect accidental protocol edits, not malicious
changes by an agent with write access to the entire filesystem.
"""
import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

COST_FIELDS = ("compute_seconds", "storage_byte_hours", "latency_ms", "data_usd", "tuning_usd", "compute_usd", "storage_usd")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def validate_protocol(p, check_inputs=True):
    if not isinstance(p, dict):
        raise ValueError("Protocol must be an object")
    for field in ("id", "hypothesis", "baseline", "controlled_variables", "primary_metric", "minimum_effect", "replicates", "seeds", "outcomes", "validity_checks", "budget_usd"):
        if field not in p:
            raise ValueError(f"Missing protocol field: {field}")
    if not isinstance(p["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", p["id"]):
        raise ValueError("id must be a safe lowercase identifier")
    for field in ("hypothesis", "baseline"):
        if not isinstance(p[field], str) or not p[field].strip():
            raise ValueError(f"{field} must be nonempty text")
    for field in ("controlled_variables", "validity_checks"):
        if not isinstance(p[field], list) or not p[field] or any(not isinstance(x, str) or not x.strip() for x in p[field]):
            raise ValueError(f"{field} must be a nonempty list of descriptions")
    metric = p["primary_metric"]
    if not isinstance(metric, dict) or not metric.get("name") or metric.get("direction") not in ("higher", "lower") or not metric.get("unit"):
        raise ValueError("primary_metric needs name, unit, and direction: higher/lower")
    number(p["minimum_effect"], "minimum_effect", 0)
    if p["minimum_effect"] == 0:
        raise ValueError("minimum_effect must be positive (absolute metric units)")
    if type(p["replicates"]) is not int or p["replicates"] < 3:
        raise ValueError("At least 3 paired replications are required")
    if not isinstance(p["seeds"], list) or len(p["seeds"]) != p["replicates"] or any(type(x) is not int for x in p["seeds"]) or len(set(p["seeds"])) != len(p["seeds"]):
        raise ValueError("seeds must contain exactly replicates unique integers")
    number(p["budget_usd"], "budget_usd", 0)
    if not isinstance(p["outcomes"], dict) or any(not isinstance(p["outcomes"].get(k), str) or not p["outcomes"][k].strip() for k in ("go", "stop", "invalid")):
        raise ValueError("outcomes needs go, stop, invalid decision implications")

    if "execution" in p and check_inputs:
        from .execution import validate_execution
        validate_execution(p["execution"])


class Workspace:
    def __init__(self, root):
        self.root = Path(root)

    def folder(self, experiment_id):
        if not isinstance(experiment_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", experiment_id):
            raise ValueError("Invalid experiment id")
        return self.root / experiment_id

    def register(self, protocol):
        validate_protocol(protocol)
        folder = self.folder(protocol["id"])
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / "protocol.json").open("x") as f:
            json.dump({"protocol": protocol, "sha256": digest(protocol)}, f, indent=2, ensure_ascii=False)
        self.append(folder, {"event": "REGISTER", "protocol_sha256": digest(protocol)})
        return folder

    def load(self, experiment_id):
        folder = self.folder(experiment_id)
        envelope = json.loads((folder / "protocol.json").read_text())
        p = envelope["protocol"]
        validate_protocol(p, check_inputs=False)
        events = [json.loads(line) for line in (folder / "ledger.jsonl").read_text().splitlines()]
        if p["id"] != experiment_id or digest(p) != envelope["sha256"] or events[0]["protocol_sha256"] != digest(p):
            raise ValueError("Frozen protocol changed")
        return folder, p, events

    @staticmethod
    def append(folder, event):
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        with (folder / "ledger.jsonl").open("a") as f:
            f.write(json.dumps(event, allow_nan=False, ensure_ascii=False) + "\n")

    def record(self, experiment_id, result):
        folder, p, events = self.load(experiment_id)
        if any(e["event"] == "DECISION" for e in events):
            raise ValueError("Experiment closed. A new hypothesis requires a new preregistration.")
        if not isinstance(result, dict):
            raise ValueError("Result must be an object")
        if "execution" in p:
            attempt = result.get("execution_attempt")
            finished = [e for e in events if e["event"] == "ATTEMPT_FINISHED" and e["attempt"] == attempt and e["seed"] == result.get("seed") and not e["error"]]
            if not finished:
                raise ValueError("Managed results require a completed execution attempt")
        if type(result.get("seed")) is not int:
            raise ValueError("A paired integer seed is required")
        if result["seed"] not in p["seeds"]:
            raise ValueError("Seed not preregistered")
        records = [e["result"] for e in events if e["event"] == "RESULT"]
        if any(r["seed"] == result["seed"] for r in records):
            raise ValueError("Duplicate seed")
        if len(records) >= p["replicates"]:
            raise ValueError("Preregistered replication count reached")
        for field in ("baseline_score", "candidate_score"):
            number(result.get(field), field)
        if not isinstance(result.get("artifact"), str) or not result["artifact"].strip():
            raise ValueError("artifact must identify the raw output/log location")
        checks = result.get("validity", {})
        if not isinstance(checks, dict) or set(checks) != set(p["validity_checks"]) or any(type(v) is not bool for v in checks.values()):
            raise ValueError("Report true/false for every preregistered validity check")
        costs = result.get("costs", {})
        if not isinstance(costs, dict) or set(costs) != set(COST_FIELDS):
            raise ValueError(f"Report all costs (baseline + candidate + failed attempts): {COST_FIELDS}")
        for k in COST_FIELDS:
            number(costs[k], k, 0)
        self.append(folder, {"event": "RESULT", "result": result})
        # Invalid measurement and budget overruns close immediately; never hide
        # invalid/failed attempts by replacing them with a more favorable seed.
        return self.evaluate(experiment_id)

    def evaluate(self, experiment_id):
        folder, p, events = self.load(experiment_id)
        previous = [e for e in events if e["event"] == "DECISION"]
        if previous:
            return previous[-1]["report"]
        records = [e["result"] for e in events if e["event"] == "RESULT"]
        # Managed result charges overlap their attempt charges. Count each attempt
        # once, including failed/unrecorded attempts; use result storage measurement.
        attempts = [e for e in events if e["event"] == "ATTEMPT_FINISHED"]
        billed = [r["costs"] for r in records if "execution_attempt" not in r]
        by_attempt = {r["execution_attempt"]: r["costs"] for r in records if "execution_attempt" in r}
        billed.extend(by_attempt.get(e["attempt"], e["costs"]) for e in attempts)
        totals = {k: sum(c[k] for c in billed) for k in COST_FIELDS if k != "latency_ms"}
        # Latency is per replication, not additive.
        latency = [r["costs"]["latency_ms"] for r in records]
        usd = sum(totals[k] for k in ("compute_usd", "storage_usd", "data_usd", "tuning_usd"))
        sign = 1 if p["primary_metric"]["direction"] == "higher" else -1
        effects = [sign * (r["candidate_score"] - r["baseline_score"]) for r in records]
        report = {"id": experiment_id, "n": len(records), "planned_n": p["replicates"], "effects": effects,
                  "mean_effect": statistics.mean(effects) if effects else None,
                  "effect_std": statistics.stdev(effects) if len(effects) > 1 else None,
                  "cost_totals": totals, "total_usd": usd,
                  "mean_latency_ms": statistics.mean(latency) if latency else None,
                  "max_latency_ms": max(latency) if latency else None}
        failures = [e for e in events if e["event"] == "EXECUTION_STOP" or (e["event"] == "ATTEMPT_FINISHED" and e["error"])]
        if failures:
            status, reason, outcome = "STOP", failures[-1].get("reason") or failures[-1]["error"], "invalid"
        elif any(not all(r["validity"].values()) for r in records):
            status, reason, outcome = "STOP", "Measurement invalid; a revised protocol must explain the failed validity check.", "invalid"
        elif usd > p["budget_usd"]:
            status, reason, outcome = "STOP", "Declared cost budget exceeded.", "stop"
        elif len(records) < p["replicates"]:
            report.update(status="PENDING", reason="Collect exactly the preregistered replications; no early success decision.")
            return report
        elif report["mean_effect"] >= p["minimum_effect"] and min(effects) > 0:
            status, reason, outcome = "CONTINUE", "Mean effect meets threshold and every paired replication improves.", "go"
        else:
            status, reason, outcome = "STOP", "Effect below threshold or improvement did not replicate across every seed.", "stop"
        report.update(status=status, reason=reason, conclusion=p["outcomes"][outcome])
        self.append(folder, {"event": "DECISION", "report": report})
        return report
