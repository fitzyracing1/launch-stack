"""Educational rocket mission software starter.

The models here are simplified and are meant for learning. They are not
suitable for operational flight, certification, or official mission design.
This project is independent and is not affiliated with any launch provider.
"""

from .vehicle import Stage, Vehicle, load_vehicle
from .simulator import SimulationConfig, simulate
from .telemetry import write_telemetry, ingest_telemetry
from .checklist import load_checklist, evaluate_checklist

__version__ = "0.1.0"

__all__ = [
    "Stage",
    "Vehicle",
    "load_vehicle",
    "SimulationConfig",
    "simulate",
    "write_telemetry",
    "ingest_telemetry",
    "load_checklist",
    "evaluate_checklist",
    "__version__",
]
