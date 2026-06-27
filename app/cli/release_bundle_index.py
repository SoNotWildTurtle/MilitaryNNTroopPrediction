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
    "reviewer-handoff.md": "Copyable reviewer handoff and review order",
    "reviewer-handoff.json": "Machine-readable reviewer handoff",
    "operator-next-steps.md": "Ranked next safe operator actions",
    "operator-next-steps.json": "Machine-readable operator next steps",
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

REVIEW_ORDER_STEPS: tuple[tuple[str, str, str], ...] = (
    (
        "Confirm bundle readiness",
        "release-health.md",
        "Start with the release health summary to decide whether the bundle is ready, warning-only, or blocked.",
    ),
    (
        "Use the reviewer handoff",
        "reviewer-handoff.md",
        "Copy the handoff into a PR, issue, or chat so another reviewer gets status, rerun command, and missing-artifact context.",
    ),
    (
        "Choose the next safe action",
        "operator-next-steps.md",
        "Use the ranked action plan to continue with the narrowest safe diagnostic, artifact, documentation, or reviewer-handoff task.",
    ),
    (
        "Triage failures next",
        "triage-summary.md",
        "When CI fails or artifacts are absent, use the triage summary before opening lower-level logs.",
    ),
    (
        "Verify artifact inventory",
        "artifact-manifest.md",
        "Check expected outputs, sizes, and SHA-256 hashes before sharing the bundle.",
    ),
    (
        "Review user-facing contracts",
        "openapi-summary.md",
        "Inspect the API contract, synthetic examples, and dashboard mockup for interface drift.",
    ),
)

STATUS_CLASS_BY_VALUE: Mapping[str, str] = {
    "pass": "status-ready",
    "passed": "status-ready",
    "ready": "status-ready",
    "present": "status-ready",
    "ok": "status-ready",
    "success": "status-ready",
    "review_warnings": "status-warning",
    "warnings": "status-warning",
    "warning": "status-warning",
    "needs_review": "status-warning",
    "needs_attention": "status-attention",
    "attention": "status-attention",
    "missing": "status-attention",
    "fail": "status-attention",
    "failed": "status-attention",
    "error": "status-attention",
}


def _format_bytes(size_bytes: int) -> str:
    """Return a compact human-friendly file size."""

    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    return f"{size_bytes / (1024 * 1024):.1f} MiB"


def _load_json(path: Path) -> Any | None:
    """Best-effort JSON loader used for richer index summaries."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _as_mapping(value: Any) -> Mapping[str, Any]:
    """Return mapping-shaped payloads while tolerating schema-compatible lists."""

    return value if isinstance(value, Mapping) else {}


def _check_items(value: Any) -> list[Mapping[str, Any]]:
    """Normalize diagnostics checks from either aggregate objects or raw check lists."""

    if isinstance(value, Mapping):
        checks = value.get("checks", [])
    else:
        checks = value
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, Mapping)]


def _aggregate_status(value: Any, default: str = "unknown") -> str:
    """Return a stable overall status for object- or list-shaped diagnostics payloads."""

    if isinstance(value, Mapping):
        return str(value.get("status", default))
    checks = _check_items(value)
    statuses = {str(check.get("status", "unknown")).lower() for check in checks}
    if not statuses:
        return default
    if statuses & {"fail", "failed", "error"}:
        return "fail"
    if statuses & {"warning", "warnings", "review_warnings", "needs_review", "needs_attention"}:
        return "review_warnings"
    if statuses <= {"pass", "passed", "ok", "success", "ready"}:
        return "pass"
    return default


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


def _status_class(value: str) -> str:
    """Return a stable CSS class for status/severity values."""

    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return STATUS_CLASS_BY_VALUE.get(normalized, "status-unknown")


def _status_badge(value: str) -> str:
    """Return an accessible visual badge for a status/severity value."""

    normalized = value.strip().replace("_", " ").upper() or "UNKNOWN"
    badge_class = _status_class(value)
    return f'<span class="badge {badge_class}">{html.escape(normalized)}</span>'


def _status_card(title: str, value: str, detail: str) -> str:
    return (
        f'<section class="card {_status_class(value)}-card">'
        f"<h2>{html.escape(title)}</h2>"
        f'<p class="metric">{_status_badge(value)}</p>'
        f"<p>{html.escape(detail)}</p>"
        "</section>"
    )


def _artifact_link(path: str, label: str) -> str:
    safe_path = html.escape(path, quote=True)
    safe_label = html.escape(label)
    return f'<a href="{safe_path}">{safe_label}</a>'


def _artifact_status(path: str, entries_by_path: Mapping[str, Dict[str, Any]]) -> str:
    return "present" if path in entries_by_path else "missing"


def _review_order_html(entries_by_path: Mapping[str, Dict[str, Any]]) -> str:
    """Render the recommended review sequence for the bundle landing page."""

    rows: List[str] = []
    for index, (action, artifact_path, detail) in enumerate(REVIEW_ORDER_STEPS, start=1):
        status = _artifact_status(artifact_path, entries_by_path)
        rows.append(
            "<tr>"
            f"<td><strong>{index}</strong></td>"
            f"<td>{html.escape(action)}</td>"
            f"<td>{_artifact_link(artifact_path, artifact_path)}</td>"
            f"<td>{_status_badge(status)}</td>"
            f"<td>{html.escape(detail)}</td>"
            "</tr>"
        )
    return (
        "<section>"
        "<h2>Review order checklist</h2>"
        '<p class="muted">Follow this compact path when reviewing a bundle or reproducing a CI failure locally.</p>'
        "<table>"
        "<thead><tr><th>#</th><th>Action</th><th>Artifact</th><th>Status</th><th>Why it matters</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</section>"
    )


def _highlight_rows(entries_by_path: Mapping[str, Dict[str, Any]]) -> Iterable[str]:
    for path, label in HIGHLIGHTED_ARTIFACTS.items():
        entry = entries_by_path.get(path)
        if entry is None:
            yield (
                "<tr>"
                f"<td>{html.escape(label)}</td>"
                f"<td><code>{html.escape(path)}</code></td>"
                f'<td>{_status_badge("missing")}</td>'
                "<td>-</td>"
                "</tr>"
            )
            continue
        yield (
            "<tr>"
            f"<td>{_artifact_link(path, label)}</td>"
            f"<td><code>{html.escape(path)}</code></td>"
            f'<td>{_status_badge("present")}</td>'
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


def _count_list(value: Any) -> int:
    """Return a safe count for list-like JSON fields used in summaries."""

    return len(value) if isinstance(value, list) else 0


def _reviewer_handoff_card(handoff: Mapping[str, Any] | None) -> str:
    """Return a top-level status card for the reviewer handoff artifact."""

    if not handoff:
        return _status_card(
            "Reviewer handoff",
            "MISSING",
            "Generate reviewer-handoff.json so reviewers can see bundle readiness at a glance.",
        )
    review_status = str(handoff.get("review_status", "needs_review"))
    recommended_rerun = str(handoff.get("recommended_rerun", "make verify"))
    missing_expected = _count_list(handoff.get("missing_expected"))
    missing_key_artifacts = _count_list(handoff.get("missing_key_artifacts"))
    detail = (
        f"Rerun {recommended_rerun}; "
        f"{missing_expected} missing expected output(s), {missing_key_artifacts} missing key artifact(s)."
    )
    return _status_card("Reviewer handoff", review_status, detail)


def _triage_summary_html(artifact_dir: Path) -> str:
    """Render a compact CI triage summary preview when present."""

    triage_preview = _read_preview(artifact_dir / "triage-summary.md", max_chars=1100)
    if not triage_preview:
        return ""
    return (
        "<section>"
        "<h2>CI triage summary</h2>"
        '<p class="muted">Use this first when a hosted CI run fails or an expected artifact is missing.</p>'
        "<pre>" + html.escape(triage_preview) + "</pre>"
        "</section>"
    )


def _reviewer_handoff_summary(handoff: Mapping[str, Any] | None) -> str:
    """Render structured reviewer handoff status details when JSON is available."""

    if not handoff:
        return ""
    review_status = str(handoff.get("review_status", "needs_review"))
    release_status = str(handoff.get("release_status", "unknown"))
    recommended_rerun = str(handoff.get("recommended_rerun", "make verify"))
    copyable_summary = str(handoff.get("copyable_summary", ""))
    missing_expected = _count_list(handoff.get("missing_expected"))
    missing_key_artifacts = _count_list(handoff.get("missing_key_artifacts"))
    summary_block = f"<pre>{html.escape(copyable_summary)}</pre>" if copyable_summary else ""
    return (
        f'<div class="handoff-status {_status_class(review_status)}-panel">'
        "<h3>Handoff status</h3>"
        "<dl>"
        f"<dt>Review status</dt><dd>{_status_badge(review_status)}</dd>"
        f"<dt>Release status</dt><dd>{_status_badge(release_status)}</dd>"
        f"<dt>Recommended rerun</dt><dd><code>{html.escape(recommended_rerun)}</code></dd>"
        f"<dt>Missing expected outputs</dt><dd>{missing_expected}</dd>"
        f"<dt>Missing key artifacts</dt><dd>{missing_key_artifacts}</dd>"
        "</dl>"
        f"{summary_block}"
        "</div>"
    )


def _reviewer_handoff_html(artifact_dir: Path, handoff: Mapping[str, Any] | None = None) -> str:
    """Render a compact reviewer handoff preview when present."""

    handoff_preview = _read_preview(artifact_dir / "reviewer-handoff.md", max_chars=1100)
    handoff_summary = _reviewer_handoff_summary(handoff)
    if not handoff_preview and not handoff_summary:
        return ""
    preview_html = f"<pre>{html.escape(handoff_preview)}</pre>" if handoff_preview else ""
    return (
        "<section>"
        "<h2>Reviewer handoff</h2>"
        '<p class="muted">Copy this into an issue, PR, or chat when handing the bundle to another reviewer.</p>'
        f"{handoff_summary}"
        f"{preview_html}"
        "</section>"
    )


def render_html(artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> str:
    """Render the release bundle index as standalone HTML."""

    manifest = build_manifest(artifact_dir)
    entries_by_path = _artifact_lookup(manifest)
    release_health_payload = _load_json(artifact_dir / "release-health.json")
    release_health = _as_mapping(release_health_payload)
    reviewer_handoff = _as_mapping(_load_json(artifact_dir / "reviewer-handoff.json")) or None
    doctor_payload = _load_json(artifact_dir / "doctor-minimal.json")
    summary_preview = _read_preview(artifact_dir / "summary.txt")

    status = _aggregate_status(release_health_payload)
    checks = _check_items(release_health_payload)
    passed_checks = sum(1 for check in checks if str(check.get("status", "")).lower() == "pass")
    total_checks = len(checks)
    doctor_checks = _check_items(doctor_payload)
    doctor_failures = sum(1 for check in doctor_checks if str(check.get("status", "")).lower() in {"fail", "failed", "error"})
    missing = manifest.get("missing_expected", [])

    cards = [
        _status_card("Release health", status, f"{passed_checks}/{total_checks} readiness checks passed."),
        _reviewer_handoff_card(reviewer_handoff),
        _status_card("Doctor failures", "fail" if doctor_failures else "pass", "Core setup diagnostics from the minimal CI doctor run."),
        _status_card("Artifacts indexed", str(manifest["file_count"]), f"Total size {_format_bytes(int(manifest['total_size_bytes']))}."),
        _status_card("Missing expected", "missing" if missing else "pass", "Expected files absent from this bundle."),
    ]

    missing_html = ""
    if missing:
        items = "".join(f"<li><code>{html.escape(str(name))}</code></li>" for name in missing)
        missing_html = f"<section><h2>Missing expected files</h2><ul>{items}</ul></section>"

    summary_html = ""
    if summary_preview:
        summary_html = "<section><h2>Bundle summary</h2><pre>" + html.escape(summary_preview) + "</pre></section>"

    review_order_html = _review_order_html(entries_by_path)
    reviewer_handoff_html = _reviewer_handoff_html(artifact_dir, reviewer_handoff)
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
    .metric {{ font-size: 1rem; font-weight: 800; margin: .25rem 0; }}
    .badge {{ display: inline-block; border-radius: 999px; border: 1px solid currentColor; padding: .25rem .65rem; font-size: .78rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }}
    .status-ready {{ color: #86efac; background: rgba(22, 101, 52, .22); }}
    .status-warning {{ color: #fde68a; background: rgba(146, 64, 14, .22); }}
    .status-attention {{ color: #fca5a5; background: rgba(153, 27, 27, .24); }}
    .status-unknown {{ color: #cbd5e1; background: rgba(71, 85, 105, .26); }}
    .status-ready-card {{ border-color: rgba(134, 239, 172, .45); }}
    .status-warning-card {{ border-color: rgba(253, 230, 138, .48); }}
    .status-attention-card {{ border-color: rgba(252, 165, 165, .5); }}
    .handoff-status {{ border: 1px solid #334155; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; background: #0b1220; }}
    .status-ready-panel {{ border-color: rgba(134, 239, 172, .45); }}
    .status-warning-panel {{ border-color: rgba(253, 230, 138, .48); }}
    .status-attention-panel {{ border-color: rgba(252, 165, 165, .5); }}
    .handoff-status dl {{ display: grid; grid-template-columns: minmax(160px, max-content) 1fr; gap: .4rem 1rem; margin: 0 0 1rem; }}
    .handoff-status dt {{ color: #cbd5e1; font-weight: 700; }}
    .handoff-status dd {{ margin: 0; }}
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
      <p class="muted">Self-contained reviewer landing page for generated diagnostics, API contracts, examples, dashboard previews, reviewer handoffs, operator next steps, and CI triage artifacts.</p>
      <p class="muted">Generated at <code>{html.escape(str(manifest['generated_at']))}</code> from <code>{html.escape(str(manifest['artifact_dir']))}</code>.</p>
    </header>

    <div class="grid">
      {''.join(cards)}
    </div>

    {review_order_html}

    <section>
      <h2>Start here</h2>
      <table>
        <thead><tr><th>Artifact</th><th>Path</th><th>Status</th><th>Size</th></tr></thead>
        <tbody>{''.join(_highlight_rows(entries_by_path))}</tbody>
      </table>
    </section>

    {reviewer_handoff_html}
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
