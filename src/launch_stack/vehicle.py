"""Multi-stage vehicle description and mass accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .constants import G0


@dataclass
class Stage:
    name: str
    dry_mass_kg: float
    propellant_mass_kg: float
    thrust_n: float
    isp_s: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("stage name must not be empty")
        if self.dry_mass_kg <= 0:
            raise ValueError(f"{self.name}: dry_mass_kg must be positive")
        if self.propellant_mass_kg < 0:
            raise ValueError(f"{self.name}: propellant_mass_kg must be >= 0")
        if self.thrust_n < 0:
            raise ValueError(f"{self.name}: thrust_n must be >= 0")
        if self.isp_s <= 0:
            raise ValueError(f"{self.name}: isp_s must be positive")

    @property
    def mass_flow_kg_s(self) -> float:
        """mdot = thrust / (Isp * g0), using constant vacuum thrust and Isp."""
        return self.thrust_n / (self.isp_s * G0)


@dataclass
class Vehicle:
    name: str
    stages: list[Stage]
    payload_mass_kg: float
    cd: float
    ref_area_m2: float
    remaining_propellant_kg: list[float] = field(init=False)
    current_stage_index: int = field(default=0)

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("vehicle needs at least one stage")
        if self.payload_mass_kg < 0:
            raise ValueError("payload_mass_kg must be >= 0")
        if self.cd < 0:
            raise ValueError("cd must be >= 0")
        if self.ref_area_m2 < 0:
            raise ValueError("ref_area_m2 must be >= 0")
        self.remaining_propellant_kg = [s.propellant_mass_kg for s in self.stages]
        self.current_stage_index = 0

    def copy(self) -> "Vehicle":
        clone = Vehicle(
            name=self.name,
            stages=list(self.stages),
            payload_mass_kg=self.payload_mass_kg,
            cd=self.cd,
            ref_area_m2=self.ref_area_m2,
        )
        clone.remaining_propellant_kg = list(self.remaining_propellant_kg)
        clone.current_stage_index = self.current_stage_index
        return clone

    @property
    def stage_number(self) -> int:
        """1-based stage number, or 0 after the last stage is gone."""
        if self.current_stage_index >= len(self.stages):
            return 0
        return self.current_stage_index + 1

    def current_stage(self) -> Stage | None:
        if self.current_stage_index >= len(self.stages):
            return None
        return self.stages[self.current_stage_index]

    def mass_kg(self) -> float:
        mass = self.payload_mass_kg
        for i, stage in enumerate(self.stages):
            if i < self.current_stage_index:
                continue
            mass += stage.dry_mass_kg + self.remaining_propellant_kg[i]
        return mass

    def thrust_n(self) -> float:
        stage = self.current_stage()
        if stage is None:
            return 0.0
        if self.remaining_propellant_kg[self.current_stage_index] <= 0:
            return 0.0
        return stage.thrust_n

    def mass_flow_kg_s(self) -> float:
        stage = self.current_stage()
        if stage is None:
            return 0.0
        if self.remaining_propellant_kg[self.current_stage_index] <= 0:
            return 0.0
        return stage.mass_flow_kg_s

    def consume(self, dt: float) -> dict[str, Any]:
        """Burn propellant for dt seconds. Drop a spent stage if it is empty.

        Returns a small event dict when staging happens, otherwise an empty
        dict. Staging is modeled as an instantaneous mass drop at the end of
        the step in which the tank reaches empty.
        """
        events: dict[str, Any] = {}
        stage = self.current_stage()
        if stage is None or dt <= 0:
            return events
        idx = self.current_stage_index
        burned = min(self.remaining_propellant_kg[idx], stage.mass_flow_kg_s * dt)
        self.remaining_propellant_kg[idx] -= burned
        if self.remaining_propellant_kg[idx] <= 1e-9:
            self.remaining_propellant_kg[idx] = 0.0
            dropped = stage.name
            dropped_index = idx
            # Only drop a spent stage when a later stage remains. The last
            # stage keeps its dry mass attached after burnout.
            if idx < len(self.stages) - 1:
                self.current_stage_index += 1
                events["staging"] = {
                    "dropped_stage": dropped,
                    "dropped_stage_number": dropped_index + 1,
                    "next_stage_number": self.stage_number,
                }
            else:
                events["burnout"] = {
                    "stage": dropped,
                    "stage_number": dropped_index + 1,
                }
        return events


def _require_number(data: dict[str, Any], key: str, path: str) -> float:
    if key not in data:
        raise ValueError(f"{path} is missing {key}")
    value = data[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{path}.{key} must be a number")
    return float(value)


def load_vehicle(path: str | Path) -> Vehicle:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("vehicle file must be a JSON object")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("vehicle.name must be a non-empty string")
    stages_raw = raw.get("stages")
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ValueError("vehicle.stages must be a non-empty list")
    stages = []
    for i, item in enumerate(stages_raw):
        if not isinstance(item, dict):
            raise ValueError(f"vehicle.stages[{i}] must be an object")
        stage_name = item.get("name")
        if not isinstance(stage_name, str):
            stage_name = f"stage-{i + 1}"
        prefix = f"vehicle.stages[{i}]"
        stages.append(
            Stage(
                name=stage_name,
                dry_mass_kg=_require_number(item, "dry_mass_kg", prefix),
                propellant_mass_kg=_require_number(item, "propellant_mass_kg", prefix),
                thrust_n=_require_number(item, "thrust_n", prefix),
                isp_s=_require_number(item, "isp_s", prefix),
            )
        )
    return Vehicle(
        name=name.strip(),
        stages=stages,
        payload_mass_kg=_require_number(raw, "payload_mass_kg", "vehicle"),
        cd=_require_number(raw, "cd", "vehicle"),
        ref_area_m2=_require_number(raw, "ref_area_m2", "vehicle"),
    )
