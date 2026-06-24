"""Generate a compact release health report for the project.

The report is a read-only summary of setup diagnostics intended for maintainers,
new users, and CI artifacts. It does not run detection, prediction, ingestion, or
network workflows.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from app.cli import doctor


DEFAULT_MARKDOWN_PATH = Path("ci_artifacts/release_health.md")
DEFAULT_JSON_PATH = Path("ci_artifacts/release_health.json")


def _status_icon(status: str) -> str:
    return {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "•")


def _escape_table_cell(value: str) -> str:
    """Escape text for a Markdown table cell."""

    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(results: Sequence[doctor.CheckResult], generated_at: datetime | None = None) -> str:
    """Render doctor results as a maintainer-friendly Markdown report."""

    generated_at = generated_at or datetime.now(timezone.utc)
    ok, warn, fail = doctor.summarize(results)
    lines = [
        "# Release Health",
        "",
        f"Generated: {generated_at.isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        f"- OK: {ok}",
        f"- Warnings: {warn}",
        f"- Failures: {fail}",
        "",
        "## Checks",
        "",
        "| Status | Check | Detail | Remediation |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        remediation = result.remediation or "—"
        detail = _escape_table_cell(result.detail)
        remediation = _escape_table_cell(remediation)
        lines.append(
            "| "
            f"{_status_icon(result.status)} {result.status.upper()} | "
            f"`{result.name}` | "
            f"{detail} | "
            f"{remediation} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Failures indicate required setup problems that should block a release or first run.",
            "- Warnings identify optional capabilities that may be intentionally disabled locally or in CI.",
            "- The report is generated from `python -m app.cli.doctor` checks and is safe to publish as a CI artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(
    markdown_path: Path = DEFAULT_MARKDOWN_PATH,
    json_path: Path | None = DEFAULT_JSON_PATH,
    include_optional: bool = False,
    check_mongo: bool = False,
) -> tuple[Path, Path | None, int]:
    """Run release-safe checks and write Markdown plus optional JSON reports."""

    results = doctor.run_checks(include_optional=include_optional, check_mongo=check_mongo)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(results), encoding="utf-8")

    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps([asdict(result) for result in results], indent=2) + "\n",
            encoding="utf-8",
        )

    _, _, failures = doctor.summarize(results)
    return markdown_path, json_path, failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Markdown/JSON release health reports.")
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=DEFAULT_MARKDOWN_PATH,
        help="where to write the Markdown health report",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="where to write the JSON health report",
    )
    parser.add_argument("--no-json", action="store_true", help="only write the Markdown report")
    parser.add_argument(
        "--check-optional",
        action="store_true",
        help="include optional ML/dashboard/GIS dependency checks",
    )
    parser.add_argument(
        "--check-mongo",
        action="store_true",
        help="include MongoDB socket connectivity checks",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    markdown_path, json_path, failures = write_reports(
        markdown_path=args.markdown_path,
        json_path=None if args.no_json else args.json_path,
        include_optional=args.check_optional,
        check_mongo=args.check_mongo,
    )
    print(f"Wrote release health report: {markdown_path}")
    if json_path is not None:
        print(f"Wrote release health JSON: {json_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
