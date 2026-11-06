# Simulation scenarios

`iot.simulate` reads a JSON scenario and writes `telemetry.jsonl`, `telemetry.csv` and `summary.json` (readings, devices, per-sensor min/max/mean, failed devices).

```json
{
  "start": "2026-03-02T00:00:00+01:00",
  "duration_hours": 168,
  "interval_seconds": 300,
  "seed": 7,
  "devices": [
    {"group": "bus", "count": 40, "weekend_factor": 0.6, "failure_rate_per_day": 0.02,
     "sensors": [
       {"name": "passengers", "mode": "count", "baseline": 45, "noise": 6, "profile": "commute", "unit": "people"},
       {"name": "co2", "baseline": 1100, "noise": 60, "profile": "commute", "min": 420, "unit": "ppm"}]},
    {"group": "bin", "count": 200,
     "sensors": [{"name": "fill", "mode": "accumulate", "rate_per_hour": 2.5, "noise": 0.2, "profile": "daytime",
                  "start": 5, "reset_at": 90, "max": 100, "unit": "%"}]}
  ],
  "events": [{"group": "bus", "sensor": "passengers", "start": "2026-03-04T17:00:00+01:00",
              "end": "2026-03-04T20:00:00+01:00", "factor": 1.6}]
}
```

- `mode`: `level` (baseline × hourly profile + drift + noise), `count` (people, vehicles, events per interval), `accumulate` (fill levels, counters; `reset_at` empties).
- `profile`: `flat`, `commute`, `daytime`, `evening` or 24 hourly factors. `weekend_factor` scales Saturdays and Sundays.
- `failure_rate_per_day`: probability per device and day of going offline; offline devices stop reporting.
- `events`: multiply a group/sensor by `factor` in a time window (match days, works, strikes, holidays).
- Limits: up to 5000 devices, 744 hours and 2 million readings per run.

Write hypotheses before running (for example "with 20% more buses at peak no stop exceeds 60 passengers"), run baseline and alternative scenarios with the same seed, compare them with DuckDB, and state which parameters are assumptions to calibrate with real data.
