"""Generate a self-contained HTML index for release diagnostic bundles."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR, build_manifest

DEFAULT_HTML_NAME = "release-bundle-index.html"
HIGHLIGHTED_ARTIFACTS: Mapping[str, str] = {
    "release-health.md": "Release readiness summary",
    "triage-summary.md": "CI triage summary and rerun targets",
    "triage-summary.json": "Machine-readable CI triage summary",
    "openapi-summary.md": "Human-readable API contract",
    "openapi.json": "Machine-readable OpenAPI contract",
    "api-response-examples.md": "Synthetic API examples",
    "api-response-examples.json": "Machine-readable API examples",
    "dashboard-mockup.html": "Static dashboard preview",
    "artifact-manifest.md": "Human-readable artifact manifest",
    "artifact-manifest.json": "Machine-readable artifact manifest",
    "summary.txt": "Plain-language bundle summary",
}


def _format_bytes(size_bytes: int) -> str:
    """Return a compact human-friendly file size."""

    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    return f"{size_bytes / (1024 * 1024):.1f} MiB"


def _load_json(path: Path) -> Dict[str, Any] | None:
    """Best-effort JSON loader used for richer index summaries."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _read_preview(path: Path, max_chars: int = 700) -> str | None:
    """Read a small text preview without making the index too large."""

    try:
        text = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return None
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _artifact_lookup(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(entry["path"]): entry for entry in manifest.get("files", [])}


def _status_card(title: str, value: str, detail: str) -> str:
    return (
        '<section class="card">'
        f"<h2>{html.escape(title)}</h2>"
        f"<p class=\"metric\">{html.escape(value)}</p>"
        f"<p>{html.escape(detail)}</p>"
        "</section>"
    )


def _artifact_link(path: str, label: str) -> str:
    safe_path = html.escape(path, quote=True)
    safe_label = html.escape(label)
    return f'<a href="{safe_path}">{safe_label}</a>'


def _highlight_rows(entries_by_path: Mapping[str, Dict[str, Any]]) -> Iterable[str]:
    for path, label in HIGHLIGHTED_ARTIFACTS.items():
        entry = entries_by_path.get(path)
        if entry is None:
            yield (
                "<tr>"
                f"<td>{html.escape(label)}</td>"
                f"<td><code>{html.escape(path)}</code></td>"
                "<td class=\"missing\">Missing</td>"
                "<td>-</td>"
                "</tr>"
            )
            continue
        yield (
            "<tr>"
            f"<td>{_artifact_link(path, label)}</td>"
            f"<td><code>{html.escape(path)}</code></td>"
            "<td class=\"present\">Present</td>"
            f"<td>{_format_bytes(int(entry['size_bytes']))}</td>"
            "</tr>"
        )


def _all_file_rows(files: List[Dict[str, Any]]) -> Iterable[str]:
    for entry in files:
        path = str(entry["path"])
        yield (
            "<tr>"
            f"<td>{_artifact_link(path, path)}</td>"
            f"<td>{_format_bytes(int(entry['size_bytes']))}</td>"
            f"<td><code>{html.escape(str(entry['sha256']))}</code></td>"
            f"<td>{html.escape(str(entry.get('description', 'Generated artifact.')))}</td>"
            "</tr>"
        )


def _triage_summary_html(artifact_dir: Path) -> str:
    """Render a compact CI triage summary preview when present."""

    triage_preview = _read_preview(artifact_dir / "triage-summary.md", max_chars=1100)
    if not triage_preview:
        return ""
    return (
        "<section>"
        "<h2>CI triage summary</h2>"
        "<p class=\"muted\">Use this first when a hosted CI run fails or an expected artifact is missing.</p>"
        "<pre>" + html.escape(triage_preview) + "</pre>"
        "</section>"
    )


def render_html(artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> str:
    """Render the release bundle index as standalone HTML."""

    manifest = build_manifest(artifact_dir)
    entries_by_path = _artifact_lookup(manifest)
    release_health = _load_json(artifact_dir / "release-health.json") or {}
    doctor = _load_json(artifact_dir / "doctor-minimal.json") or {}
    summary_preview = _read_preview(artifact_dir / "summary.txt")

    status = str(release_health.get("status", "unknown"))
    checks = release_health.get("checks", [])
    passed_checks = sum(1 for check in checks if check.get("status") == "pass") if isinstance(checks, list) else 0
    total_checks = len(checks) if isinstance(checks, list) else 0
    doctor_checks = doctor.get("checks", [])
    doctor_failures = (
        sum(1 for check in doctor_checks if check.get("status") == "fail")
        if isinstance(doctor_checks, list)
        else 0
    )
    missing = manifest.get("missing_expected", [])

    cards = [
        _status_card("Release health", status.upper(), f"{passed_checks}/{total_checks} readiness checks passed."),
        _status_card("Doctor failures", str(doctor_failures), "Core setup diagnostics from the minimal CI doctor run."),
        _status_card("Artifacts indexed", str(manifest["file_count"]), f"Total size {_format_bytes(int(manifest['total_size_bytes']))}."),
        _status_card("Missing expected", str(len(missing)), "Expected files absent from this bundle."),
    ]

    missing_html = ""
    if missing:
        items = "".join(f"<li><code>{html.escape(str(name))}</code></li>" for name in missing)
        missing_html = f"<section><h2>Missing expected files</h2><ul>{items}</ul></section>"

    summary_html = ""
    if summary_preview:
        summary_html = "<section><h2>Bundle summary</h2><pre>" + html.escape(summary_preview) + "</pre></section>"

    triage_html = _triage_summary_html(artifact_dir)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MilitaryNNTroopPrediction release bundle</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #0f172a; color: #e2e8f0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 2rem; }}
    header {{ margin-bottom: 1.5rem; }}
    h1 {{ margin: 0 0 .5rem; font-size: clamp(2rem, 4vw, 3.25rem); }}
    h2 {{ margin-top: 0; }}
    a {{ color: #93c5fd; }}
    .muted {{ color: #94a3b8; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }}
    .card, section {{ background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 16px 40px rgba(0,0,0,.18); }}
    .metric {{ font-size: 2rem; font-weight: 800; margin: .25rem 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .95rem; }}
    th, td {{ border-bottom: 1px solid #334155; padding: .7rem; text-align: left; vertical-align: top; }}
    th {{ color: #cbd5e1; }}
    code, pre {{ background: #020617; border-radius: 8px; }}
    code {{ padding: .1rem .3rem; }}
    pre {{ padding: 1rem; overflow-x: auto; white-space: pre-wrap; }}
    .present {{ color: #86efac; font-weight: 700; }}
    .missing {{ color: #fca5a5; font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Release bundle index</h1>
      <p class="muted">Self-contained reviewer landing page for generated diagnostics, API contracts, examples, dashboard previews, and CI triage artifacts.</p>
      <p class="muted">Generated at <code>{html.escape(str(manifest['generated_at']))}</code> from <code>{html.escape(str(manifest['artifact_dir']))}</code>.</p>
    </header>

    <div class="grid">
      {''.join(cards)}
    </div>

    <section>
      <h2>Start here</h2>
      <table>
        <thead><tr><th>Artifact</th><th>Path</th><th>Status</th><th>Size</th></tr></thead>
        <tbody>{''.join(_highlight_rows(entries_by_path))}</tbody>
      </table>
    </section>

    {triage_html}
    {summary_html}
    {missing_html}

    <section>
      <h2>All indexed files</h2>
      <table>
        <thead><tr><th>Path</th><th>Size</th><th>SHA-256</th><th>Description</th></tr></thead>
        <tbody>{''.join(_all_file_rows(manifest.get('files', [])))}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def write_html(html_text: str, path: Path) -> None:
    """Write rendered HTML to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML landing page for diagnostic artifact bundles."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated artifacts. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--html-path",
        type=Path,
        default=None,
        help="Output HTML path. Default: <artifact-dir>/release-bundle-index.html",
    )
    return parser


def main() -> int:
    """CLI entry point."""

    args = build_parser().parse_args()
    html_text = render_html(args.artifact_dir)
    html_path = args.html_path or args.artifact_dir / DEFAULT_HTML_NAME
    write_html(html_text, html_path)
    print(f"Wrote release bundle index to {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
