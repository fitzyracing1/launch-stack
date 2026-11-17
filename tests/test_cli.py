import json
from pathlib import Path

from launch_stack.cli import main


def examples() -> Path:
    return Path(__file__).resolve().parents[1] / "examples"


def test_cli_requires_a_command(capsys):
    assert main([]) == 1
    out = capsys.readouterr().out
    assert "simulate" in out
    assert "checklist" in out


def test_simulate_ingest_and_checklist_loop(tmp_path: Path):
    tele = tmp_path / "ascent.jsonl"
    report = tmp_path / "report.json"
    rc = main(
        [
            "simulate",
            "--vehicle",
            str(examples() / "two_stage_vehicle.json"),
            "--out",
            str(tele),
            "--mode",
            "2d",
        ]
    )
    assert rc == 0
    assert tele.exists()
    rc = main(["ingest", str(tele)])
    assert rc == 0
    rc = main(
        [
            "checklist",
            "--telemetry",
            str(tele),
            "--checklist",
            str(examples() / "ascent_checklist.json"),
            "--out",
            str(report),
        ]
    )
    assert rc == 0
    payload = json.loads(report.read_text())
    assert payload["decision"] == "go"


def test_cli_reports_a_missing_vehicle(tmp_path: Path, capsys):
    rc = main(["simulate", "--vehicle", str(tmp_path / "nope.json"), "--out", str(tmp_path / "t.jsonl")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "launch-stack:" in err
