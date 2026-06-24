# API record endpoint testing

The API exposes MongoDB-backed analytical routes for recent detections and
predictions. These routes are intentionally tested without a live MongoDB server
so contributors can validate the public API contract in a small core install.

## What is covered

`tests/test_api_records.py` patches the movement-history helpers imported by
`app.api.main` and then calls the route functions directly. This verifies that:

- route handlers pass the requested `area` and `limit` through to the data layer;
- MongoDB `_id` values are converted to public `id` strings;
- nested `ObjectId` values are stringified;
- `datetime` values are returned as ISO-8601 strings;
- tuples are converted to JSON-safe lists; and
- FastAPI route metadata keeps `limit` constrained to `1..100`.

## Why this matters

The heavier prediction pipeline and database runtime can evolve independently
from the user-facing API contract. Mocked endpoint tests keep CI fast while still
catching accidental changes that would break dashboards, scripts, or integrators
that consume `/detections/{area}` and `/predictions/{area}`.

Run the full lightweight suite with:

```bash
bash scripts/test.sh
```

Or run only the API record tests with:

```bash
python -m unittest tests.test_api_records
```

These tests are defensive and local-only; they do not fetch imagery, query OSINT,
run ML inference, or connect to external services.
