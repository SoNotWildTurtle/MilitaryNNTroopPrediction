"""Export safe synthetic data fixtures for local demos and integration tests.

The generated files are intentionally non-operational placeholders. They help
contributors exercise data-loading, dashboards, and API clients without touching
live OSINT, imagery providers, databases, model pipelines, or deployment flows.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from app.api.examples import SAMPLE_AREA, sample_detection_records, sample_prediction_records

DEFAULT_OUTPUT_DIR = Path("data/fixtures")
DEFAULT_SUMMARY_NAME = "synthetic-fixtures.md"
DEFAULT_DETECTIONS_JSONL = "synthetic-detections.jsonl"
DEFAULT_PREDICTIONS_JSONL = "synthetic-predictions.jsonl"
DEFAULT_DETECTIONS_CSV = "synthetic-detections.csv"
DEFAULT_BUNDLE_JSON = "synthetic-fixtures-summary.json"


def _jsonl_lines(records: Iterable[Mapping[str, Any]]) -> str:
    return "".join(json.dumps(dict(record), sort_keys=True) + "\n" for record in records)


def _prediction_records_for_fixture() -> List[Dict[str, Any]]:
    """Return predictions with flattened waypoints useful for file-based demos."""

    records: List[Dict[str, Any]] = []
    for record in sample_prediction_records():
        item = dict(record)
        trajectory = item.get("trajectory", {})
        if isinstance(trajectory, Mapping):
            item["current_point"] = trajectory.get("current_point")
            item["next_point"] = trajectory.get("next_point")
        records.append(item)
    return records


def build_fixture_bundle() -> Dict[str, Any]:
    """Build deterministic synthetic fixtures from the shared API examples."""

    detections = sample_detection_records()
    predictions = _prediction_records_for_fixture()
    return {
        "metadata": {
            "schema": "militarynntroopprediction.synthetic_fixtures.v1",
            "description": "Safe synthetic records for local demos, docs, and client integration tests.",
            "area": SAMPLE_AREA,
            "generated_from": "app.api.examples",
            "record_counts": {
                "detections": len(detections),
                "predictions": len(predictions),
            },
            "safe_scope": "Synthetic placeholders only; no live OSINT, imagery, database, model, or deployment calls.",
        },
        "detections": detections,
        "predictions": predictions,
    }


def _write_detections_csv(records: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["id", "area", "label", "confidence", "bbox", "timestamp", "source", "notes"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {name: record.get(name, "") for name in fieldnames}
            row["bbox"] = json.dumps(row["bbox"], sort_keys=True)
            writer.writerow(row)


def _summary_lines(bundle: Mapping[str, Any]) -> Iterable[str]:
    metadata = bundle["metadata"]
    counts = metadata["record_counts"]
    yield "# Synthetic Data Fixtures"
    yield ""
    yield str(metadata["description"])
    yield ""
    yield f"- Schema: `{metadata['schema']}`"
    yield f"- Area: `{metadata['area']}`"
    yield f"- Generated from: `{metadata['generated_from']}`"
    yield f"- Detection records: {counts['detections']}"
    yield f"- Prediction records: {counts['predictions']}"
    yield f"- Safe scope: {metadata['safe_scope']}"
    yield ""
    yield "## Files"
    yield ""
    yield f"- `{DEFAULT_BUNDLE_JSON}`: Machine-readable bundle metadata and file paths."
    yield f"- `{DEFAULT_DETECTIONS_JSONL}`: JSON Lines detection records."
    yield f"- `{DEFAULT_PREDICTIONS_JSONL}`: JSON Lines prediction records."
    yield f"- `{DEFAULT_DETECTIONS_CSV}`: Spreadsheet-friendly detection records."
    yield ""
    yield "## Use cases"
    yield ""
    yield "- Build dashboard table loaders without live data access."
    yield "- Share privacy-safe screenshots or client examples."
    yield "- Reproduce fixture-backed tests in CI or local reviews."


def write_fixture_bundle(bundle: Mapping[str, Any], output_dir: Path) -> Dict[str, str]:
    """Write fixture files and return a machine-readable path summary."""

    output_dir.mkdir(parents=True, exist_ok=True)
    detections = list(bundle["detections"])
    predictions = list(bundle["predictions"])

    detections_jsonl = output_dir / DEFAULT_DETECTIONS_JSONL
    predictions_jsonl = output_dir / DEFAULT_PREDICTIONS_JSONL
    detections_csv = output_dir / DEFAULT_DETECTIONS_CSV
    summary_markdown = output_dir / DEFAULT_SUMMARY_NAME
    bundle_json = output_dir / DEFAULT_BUNDLE_JSON

    detections_jsonl.write_text(_jsonl_lines(detections), encoding="utf-8")
    predictions_jsonl.write_text(_jsonl_lines(predictions), encoding="utf-8")
    _write_detections_csv(detections, detections_csv)
    summary_markdown.write_text("\n".join(_summary_lines(bundle)).rstrip() + "\n", encoding="utf-8")

    written = {
        "bundle_json": bundle_json.as_posix(),
        "detections_jsonl": detections_jsonl.as_posix(),
        "predictions_jsonl": predictions_jsonl.as_posix(),
        "detections_csv": detections_csv.as_posix(),
        "summary_markdown": summary_markdown.as_posix(),
    }
    serializable = dict(bundle)
    serializable["files"] = written
    bundle_json.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return written


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Export safe synthetic JSONL, CSV, and Markdown fixtures for demos and tests."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated fixtures. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable summary of written fixture paths.",
    )
    return parser


def main() -> int:
    """CLI entry point."""

    args = build_parser().parse_args()
    bundle = build_fixture_bundle()
    written = write_fixture_bundle(bundle, args.output_dir)
    if args.json:
        print(json.dumps({"status": "ok", "files": written}, indent=2, sort_keys=True))
    else:
        print(f"Wrote synthetic fixtures to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
