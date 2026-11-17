"""Mission-timeline go/no-go checklist runner."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .telemetry import TelemetryStream

SCHEMA = "launch-stack-checklist/v0.1"
COMPARISONS = {
    ">=": lambda actual, expected: actual >= expected,
    "<=": lambda actual, expected: actual <= expected,
    ">": lambda actual, expected: actual > expected,
    "<": lambda actual, expected: actual < expected,
    "==": lambda actual, expected: actual == expected,
}


@dataclass
class GateResult:
    id: str
    label: str
    event: str
    stage: int | None
    decision: str
    reason: str
    actual: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChecklistReport:
    name: str
    decision: str
    gates: list[GateResult]
    telemetry_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "decision": self.decision,
            "gate_count": len(self.gates),
            "go_count": sum(1 for g in self.gates if g.decision == "go"),
            "no_go_count": sum(1 for g in self.gates if g.decision == "no-go"),
            "gates": [
                {
                    "id": g.id,
                    "label": g.label,
                    "event": g.event,
                    "stage": g.stage,
                    "decision": g.decision,
                    "reason": g.reason,
                    "actual": g.actual,
                }
                for g in self.gates
            ],
            "telemetry_path": self.telemetry_path,
        }


def load_checklist(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("checklist file must be a JSON object")
    if raw.get("schema") != SCHEMA:
        raise ValueError(f"expected schema {SCHEMA!r}, got {raw.get('schema')!r}")
    if not isinstance(raw.get("name"), str) or not raw["name"].strip():
        raise ValueError("checklist.name must be a non-empty string")
    gates = raw.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("checklist.gates must be a non-empty list")
    for i, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise ValueError(f"gates[{i}] must be an object")
        if not isinstance(gate.get("id"), str):
            raise ValueError(f"gates[{i}].id must be a string")
        when = gate.get("when")
        if not isinstance(when, dict) or not isinstance(when.get("event"), str):
            raise ValueError(f"gates[{i}].when.event is required")
        require = gate.get("require")
        if not isinstance(require, dict) or not require:
            raise ValueError(f"gates[{i}].require must be a non-empty object")
    return raw


def _pick_sample(stream: TelemetryStream, event: str, stage: int | None) -> dict[str, Any] | None:
    if event == "max_q":
        sample = stream.max_q_sample()
        if sample is not None and stage is not None and sample.get("stage") != stage:
            return None
        return sample
    if event == "apogee":
        return stream.apogee_sample()
    return stream.sample_at_event(event, stage)


def _compare(field_name: str, actual: Any, rule: Any) -> tuple[bool, str]:
    if not isinstance(rule, dict) or not rule:
        raise ValueError(f"require.{field_name} must be an object of comparisons")
    for op, expected in rule.items():
        if op not in COMPARISONS:
            raise ValueError(f"unsupported comparison {op!r} on {field_name}")
        if actual is None:
            return False, f"{field_name} is missing"
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False, f"{field_name} is not numeric"
        if not COMPARISONS[op](actual, expected):
            return False, f"{field_name} {actual} is not {op} {expected}"
    parts = [f"{field_name} {actual} {op} {expected}" for op, expected in rule.items()]
    return True, "; ".join(parts)


def evaluate_checklist(stream: TelemetryStream, checklist: dict[str, Any]) -> ChecklistReport:
    results: list[GateResult] = []
    for gate in checklist["gates"]:
        gate_id = gate["id"]
        label = gate.get("label") or gate_id
        event = gate["when"]["event"]
        stage = gate["when"].get("stage")
        sample = _pick_sample(stream, event, stage)
        if sample is None:
            results.append(
                GateResult(
                    id=gate_id,
                    label=label,
                    event=event,
                    stage=stage,
                    decision="no-go",
                    reason=f"no telemetry sample for event {event!r}"
                    + (f" stage {stage}" if stage is not None else ""),
                )
            )
            continue
        reasons = []
        actuals = {}
        failed = False
        for field_name, rule in gate["require"].items():
            actual = sample.get(field_name)
            actuals[field_name] = actual
            ok, reason = _compare(field_name, actual, rule)
            reasons.append(reason)
            if not ok:
                failed = True
        results.append(
            GateResult(
                id=gate_id,
                label=label,
                event=event,
                stage=stage,
                decision="no-go" if failed else "go",
                reason="; ".join(reasons),
                actual=actuals,
            )
        )
    overall = "go" if results and all(g.decision == "go" for g in results) else "no-go"
    return ChecklistReport(
        name=checklist["name"],
        decision=overall,
        gates=results,
        telemetry_path=stream.path,
    )
