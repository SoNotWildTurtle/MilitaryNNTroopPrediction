"""Export synthetic API response examples for dashboard and client builders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable

from app.api.examples import sample_payload_bundle

DEFAULT_JSON_PATH = Path("api-response-examples.json")
DEFAULT_MARKDOWN_PATH = Path("api-response-examples.md")


def write_json(payload: Dict[str, Any], path: Path) -> None:
    """Write pretty JSON examples to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown_sections(payload: Dict[str, Any]) -> Iterable[str]:
    yield "# API response examples"
    yield ""
    yield payload["metadata"]["description"]
    yield ""
    yield "These examples are synthetic and safe for UI, docs, and client tests."
    yield "They do not require MongoDB, Sentinel Hub, TensorFlow, YOLO, or live imagery."
    yield ""
    for endpoint, example in payload["endpoints"].items():
        yield f"## `{endpoint}`"
        yield ""
        yield "```json"
        yield json.dumps(example, indent=2, sort_keys=True)
        yield "```"
        yield ""


def write_markdown(payload: Dict[str, Any], path: Path) -> None:
    """Write Markdown examples to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_markdown_sections(payload)).rstrip() + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Export synthetic API response examples for docs, dashboards, and client tests."
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help=f"Path for JSON output. Default: {DEFAULT_JSON_PATH}",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=DEFAULT_MARKDOWN_PATH,
        help=f"Path for Markdown output. Default: {DEFAULT_MARKDOWN_PATH}",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip JSON output.",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Skip Markdown output.",
    )
    return parser


def main() -> int:
    """CLI entry point."""

    args = build_parser().parse_args()
    payload = sample_payload_bundle()

    if not args.no_json:
        write_json(payload, args.json_path)
        print(f"Wrote JSON examples to {args.json_path}")
    if not args.no_markdown:
        write_markdown(payload, args.markdown_path)
        print(f"Wrote Markdown examples to {args.markdown_path}")
    if args.no_json and args.no_markdown:
        print("No outputs requested; use --json-path or --markdown-path without skip flags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
