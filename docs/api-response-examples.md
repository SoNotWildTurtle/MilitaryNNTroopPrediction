# API response examples

This document describes the synthetic API response examples provided by
`app.api.examples` and exported by `python -m app.cli.export_api_examples`.

The examples are intentionally non-operational fixtures for dashboard builders,
client developers, documentation, and smoke tests. They do not require MongoDB,
Sentinel Hub, TensorFlow, YOLO, or live imagery.

## Export commands

```bash
python -m app.cli.export_api_examples
python -m app.cli.export_api_examples --json-path api-response-examples.json --markdown-path api-response-examples.md
python -m app.cli.export_api_examples --no-markdown --json-path /tmp/api-response-examples.json
```

## Included endpoint examples

- `GET /healthz`
- `GET /readyz`
- `GET /detections/{area}?limit=10`
- `GET /predictions/{area}?limit=10`
- `POST /predict/{area}`

## Why this helps

- Frontend and dashboard work can begin before a database is populated.
- API consumers get stable example payloads alongside the OpenAPI contract.
- Tests can verify JSON-safe public records without reaching external services.
- Generated examples can be included in CI artifacts or copied into integration docs.
