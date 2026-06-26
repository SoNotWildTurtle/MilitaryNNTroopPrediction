# Synthetic Data Fixtures

The synthetic fixture exporter creates privacy-safe local records for demos, dashboard loaders, screenshots, and client integration tests. It uses the shared examples in `app.api.examples`, so fixture files stay aligned with the OpenAPI examples and static dashboard mockups without connecting to live OSINT, imagery, MongoDB, model, or deployment workflows.

## Generate fixtures

```bash
python -m app.cli.synthetic_data_fixtures
python -m app.cli.synthetic_data_fixtures --output-dir data/fixtures --json
# or
make synthetic-fixtures
```

By default the command writes to `data/fixtures/`. Use `--output-dir` when you want an isolated CI or review directory.

## Generated files

- `synthetic-fixtures-summary.json` - machine-readable bundle metadata, safe-scope statement, record counts, and file paths.
- `synthetic-detections.jsonl` - JSON Lines detection records for client loaders.
- `synthetic-predictions.jsonl` - JSON Lines prediction records with flattened current/next points for file-based demos.
- `synthetic-detections.csv` - spreadsheet-friendly detection records for reviewers and dashboard prototyping.
- `synthetic-fixtures.md` - human-readable summary of the bundle.

## Safety and privacy notes

These files are synthetic placeholders only. The exporter does not call Sentinel Hub, live OSINT sources, MongoDB, TensorFlow, YOLO, prediction endpoints, ingestion jobs, or deployment scripts. The generated records are suitable for screenshots, documentation, local UI testing, and CI artifact bundles, but they are not evidence and must not be presented as operational truth.

## Validation

The standard smoke suite now runs:

```bash
python -m app.cli.synthetic_data_fixtures --output-dir /tmp/militarynntroopprediction-synthetic-fixtures --json
python -m unittest discover -s tests -p 'test_*.py'
```

`bash scripts/ci_report.sh` also includes the fixture files and CLI help in the diagnostic artifact bundle so reviewers can validate schema, provenance, and safe scope from the release bundle index.

## Rollback

This feature is additive. To roll it back, remove `app/cli/synthetic_data_fixtures.py`, `tests/test_synthetic_data_fixtures.py`, this document, the `synthetic-fixtures` Make target, and the fixture export lines in `scripts/test.sh`, `scripts/ci_report.sh`, and `app/cli/artifact_manifest.py`.
