# Synthetic Data Fixtures

Use the synthetic fixture exporter when you need safe local records for demos,
dashboard work, client integration tests, screenshots, or documentation examples.
The exporter never calls Sentinel Hub, MongoDB, YOLO, TensorFlow, OSINT sources,
or deployment workflows.

```bash
python -m app.cli.synthetic_data_fixtures
# or
make synthetic-fixtures
```

By default, the command writes these files under `data/fixtures/`:

- `synthetic-detections.jsonl` - JSON Lines detection records.
- `synthetic-predictions.jsonl` - JSON Lines prediction records with flattened waypoints.
- `synthetic-detections.csv` - spreadsheet-friendly detection records.
- `synthetic-fixtures.md` - a human-readable fixture summary.

For isolated CI or review artifacts, point the command at a custom directory:

```bash
python -m app.cli.synthetic_data_fixtures --output-dir /tmp/militarynntroopprediction-fixtures --json
```

The records are generated from `app.api.examples`, so API examples, dashboard
mockups, and data fixtures remain aligned. Treat these outputs as placeholders
only; they are intentionally synthetic and should not be used as operational or
real-world intelligence data.
