"""Export the FastAPI OpenAPI schema for CI artifacts and integrators.

This command imports the lightweight API app and writes its generated OpenAPI
contract without starting a server, connecting to MongoDB, or running the ML
prediction pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from app.api.main import app


DEFAULT_JSON_PATH = Path("ci_artifacts/openapi.json")
DEFAULT_MARKDOWN_PATH = Path("ci_artifacts/openapi-summary.md")


def _sorted_paths(schema: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """Return API paths with stable, upper-case HTTP method lists."""

    paths = schema.get("paths", {})
    rows: list[tuple[str, list[str]]] = []
    for path, methods in sorted(paths.items()):
        if not isinstance(methods, dict):
            continue
        verbs = sorted(method.upper() for method in methods if method.lower() != "parameters")
        rows.append((path, verbs))
    return rows


def render_markdown(schema: dict[str, Any]) -> str:
    """Render a compact human-readable summary of the OpenAPI schema."""

    info = schema.get("info", {})
    title = info.get("title", "API")
    version = info.get("version", "unknown")
    lines = [
        "# OpenAPI Contract Summary",
        "",
        f"- Title: {title}",
        f"- Version: {version}",
        f"- OpenAPI: {schema.get('openapi', 'unknown')}",
        "",
        "## Paths",
        "",
        "| Method | Path |",
        "| --- | --- |",
    ]

    for path, verbs in _sorted_paths(schema):
        lines.append(f"| {', '.join(verbs) or '—'} | `{path}` |")

    lines.extend(
        [
            "",
            "## Usage",
            "",
            "- `openapi.json` is the machine-readable API contract generated directly from the FastAPI app.",
            "- This summary is safe to attach to CI artifacts and review without launching the API server.",
            "- Regenerate locally with `python -m app.cli.export_openapi`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_openapi(
    json_path: Path = DEFAULT_JSON_PATH,
    markdown_path: Path | None = DEFAULT_MARKDOWN_PATH,
) -> tuple[Path, Path | None, dict[str, Any]]:
    """Write OpenAPI JSON plus an optional Markdown summary."""

    schema = app.openapi()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(schema), encoding="utf-8")

    return json_path, markdown_path, schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export the FastAPI OpenAPI contract without starting the server."
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="where to write the OpenAPI JSON schema",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=DEFAULT_MARKDOWN_PATH,
        help="where to write the Markdown schema summary",
    )
    parser.add_argument("--no-markdown", action="store_true", help="only write the JSON schema")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    json_path, markdown_path, schema = write_openapi(
        json_path=args.json_path,
        markdown_path=None if args.no_markdown else args.markdown_path,
    )
    print(f"Wrote OpenAPI JSON: {json_path}")
    if markdown_path is not None:
        print(f"Wrote OpenAPI summary: {markdown_path}")
    print(f"Exported {len(schema.get('paths', {}))} API paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
