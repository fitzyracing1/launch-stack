# launch-stack

An open-source starter for rocket mission software. It includes a simplified educational launch-and-ascent simulator, a telemetry stream format with an ingest tool, and a mission-timeline go/no-go checklist runner.

The physics in this project are simplified and are meant for learning. They are not a substitute for operational flight software, official mission analysis, or range safety work. The model uses a spherical non-rotating Earth, a single exponential atmosphere, constant vacuum thrust and specific impulse, and a basic gravity-turn steering law. There is no wind, no engine-out logic, no structural loads model, and no claim that a simulated trajectory would fly.

This project is independent. It is not affiliated with, endorsed by, or a product of any launch provider.

Author: Joshua Almeida ([@fitzyracing1](https://github.com/fitzyracing1)). MIT License. Copyright (c) 2026 Joshua Almeida.

## What is in the box

- A 1D vertical or 2D planar ascent simulator. The vehicle can have more than one stage. Each stage has dry mass, propellant, thrust, and specific impulse. When a stage runs out of propellant, it is dropped and the next stage can ignite.
- A gravity turn: the vehicle holds vertical for a short time, pitches over by a set angle, then steers along the velocity vector.
- A JSON Lines telemetry stream with a header and one sample per recording step, plus a tool that reads the stream and summarizes liftoff, max-q, staging, burnout, and apogee.
- A go/no-go checklist runner. You write gates such as "thrust-to-weight must be at least 1 at liftoff" or "dynamic pressure at max-q must stay under a limit." The runner evaluates a telemetry stream against those gates and prints a report.

## Install and run

Python 3.11 or newer. No third-party runtime dependencies.

```
python -m pip install -e .
python -m pytest
```

Or run the module without installing:

```
PYTHONPATH=src python -m launch_stack simulate --vehicle examples/two_stage_vehicle.json --out /tmp/ascent.jsonl
PYTHONPATH=src python -m launch_stack ingest /tmp/ascent.jsonl
PYTHONPATH=src python -m launch_stack checklist --telemetry /tmp/ascent.jsonl --checklist examples/ascent_checklist.json
```

The example vehicle is a made-up two-stage light-lift design for demos. It is not a model of any real rocket.

## Telemetry format

The stream is JSON Lines. The first record is a header with `"schema": "launch-stack-telemetry/v0.1"` and `"type": "header"`. Every later record has `"type": "sample"` and fields for time, position, velocity, mass, thrust, stage number, dynamic pressure, and pitch.

## Checklist format

A checklist is a JSON object with `"schema": "launch-stack-checklist/v0.1"` and a list of gates. Each gate has an `id`, a `when` event (`liftoff`, `max_q`, `staging`, `burnout`, or `apogee`), and a `require` map of sample fields with numeric comparisons (`>=`, `<=`, `>`, `<`).

## Tests and CI

`python -m pytest` is the test suite. GitHub Actions runs that command on every push and pull request.

## License

MIT. Copyright (c) 2026 Joshua Almeida.
