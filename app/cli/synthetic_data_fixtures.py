"""Export safe synthetic data fixtures for local demos and integration tests.

The generated files are intentionally non-operational placeholders. They help
contributors exercise data-loading, dashboards, and API clients without touching
live OSINT, imagery providers, databases, or model pipelines.
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
            "description": "Safe synthetic records for local demos, docs, and client integration tests.",
            "area": SAMPLE_AREA,
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
            row["bbox"] = json.dumps(row["bbox"])
            writer.writerow(row)


def _summary_lines(bundle: Mapping[str, Any]) -> Iterable[str]:
    metadata = bundle["metadata"]
    counts = metadata["record_counts"]
    yield "# Synthetic Data Fixtures"
    yield ""
    yield str(metadata["description"])
    yield ""
    yield f"- Area: `{metadata['area']}`"
    yield f"- Detection records: {counts['detections']}"
    yield f"- Prediction records: {counts['predictions']}"
    yield f"- Safe scope: {metadata['safe_scope']}"
    yield ""
    yield "## Files"
    yield ""
    yield f"- `{DEFAULT_DETECTIONS_JSONL}`: JSON Lines detection records."
    yield f"- `{DEFAULT_PREDICTIONS_JSONL}`: JSON Lines prediction records."
    yield f"- `{DEFAULT_DETECTIONS_CSV}`: Spreadsheet-friendly detection records."
    yield ""
    yield "These records are generated from `app.api.examples` so API examples, dashboard"
    yield "mockups, and local data fixtures stay aligned."


def write_fixture_bundle(bundle: Mapping[str, Any], output_dir: Path) -> Dict[str, str]:
    """Write JSONL, CSV, and Markdown fixture files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    detections = list(bundle["detections"])
    predictions = list(bundle["predictions"])

    paths = {
        "detections_jsonl": output_dir / DEFAULT_DETECTIONS_JSONL,
        "predictions_jsonl": output_dir / DEFAULT_PREDICTIONS_JSONL,
        "detections_csv": output_dir / DEFAULT_DETECTIONS_CSV,
        "summary_markdown": output_dir / DEFAULT_SUMMARY_NAME,
    }
    paths["detections_jsonl"].write_text(_jsonl_lines(detections), encoding="utf-8")
    paths["predictions_jsonl"].write_text(_jsonl_lines(predictions), encoding="utf-8")
    _write_detections_csv(detections, paths["detections_csv"])
    paths["summary_markdown"].write_text("\n".join(_summary_lines(bundle)).rstrip() + "\n", encoding="utf-8")
    return {name: path.as_posix() for name, path in paths.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export safe synthetic data fixtures for demos, docs, and client integration tests."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated fixture files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary to stdout.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bundle = build_fixture_bundle()
    written = write_fixture_bundle(bundle, args.output_dir)

    if args.json:
        print(
            json.dumps(
                {"output_dir": args.output_dir.as_posix(), "written": written, "metadata": bundle["metadata"]},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"Wrote synthetic data fixtures to {args.output_dir}")
        for label, path in written.items():
            print(f"- {label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
