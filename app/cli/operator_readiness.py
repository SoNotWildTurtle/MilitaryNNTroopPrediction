"""Generate an operator-facing readiness checklist from local diagnostics.

The checklist is intentionally offline and read-only. It helps a reviewer or
first-time operator decide what to inspect before sharing a diagnostics bundle,
launching the API, or handing the project to a less technical user.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
EXPECTED_ARTIFACTS = {
    "release-bundle-index.html": "Open this first; it is the reviewer landing page.",
    "release-health.md": "Review readiness status and priority setup warnings.",
    "release-notes.md": "Share this manager-friendly summary with non-technical users.",
    "reviewer-handoff.md": "Use this as the copyable PR or handoff summary.",
    "triage-summary.md": "Use this when CI or local verification fails.",
    "artifact-manifest.md": "Confirm generated files, sizes, hashes, and omissions.",
    "dashboard-mockup.html": "Preview the user-facing dashboard without live services.",
    "openapi-summary.md": "Review the public API contract for client builders.",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _status_from_health(artifact_dir: Path) -> tuple[str, list[str]]:
    health = _read_json(artifact_dir / "release-health.json")
    results = health.get("results", [])
    if not isinstance(results, list):
        return "review", ["release-health.json did not contain a results list."]

    failures: list[str] = []
    warnings: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "unknown"))
        status = str(item.get("status", "review")).lower()
        detail = str(item.get("detail", "No detail provided."))
        if status == "fail":
            failures.append(f"{name}: {detail}")
        elif status == "warn":
            warnings.append(f"{name}: {detail}")

    if failures:
        return "blocked", failures[:5]
    if warnings:
        return "review", warnings[:5]
    if results:
        return "ready", ["No failing or warning health checks were reported."]
    return "review", ["No release health checks were found; run make ci-report."]


def build_checklist(artifact_dir: Path, generated_at: datetime | None = None) -> dict[str, Any]:
    """Build a deterministic readiness checklist for generated artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc)
    status, health_notes = _status_from_health(artifact_dir)

    artifacts = []
    missing = []
    for relative_path, purpose in EXPECTED_ARTIFACTS.items():
        path = artifact_dir / relative_path
        exists = path.exists()
        if not exists:
            missing.append(relative_path)
        artifacts.append(
            {
                "path": relative_path,
                "exists": exists,
                "purpose": purpose,
                "size_bytes": path.stat().st_size if exists else 0,
            }
        )

    if missing and status == "ready":
        status = "review"

    checks = [
        {
            "name": "Open reviewer landing page",
            "status": "ok" if (artifact_dir / "release-bundle-index.html").exists() else "todo",
            "instruction": "Open release-bundle-index.html before individual artifacts so reviewers have one safe entry point.",
        },
        {
            "name": "Confirm health and warnings",
            "status": "ok" if status == "ready" else "review",
            "instruction": "Read release-health.md and resolve any failures before treating the bundle as ready.",
        },
        {
            "name": "Check synthetic UX preview",
            "status": "ok" if (artifact_dir / "dashboard-mockup.html").exists() else "todo",
            "instruction": "Use the static dashboard mockup for onboarding and screenshots; it should not require live imagery or MongoDB.",
        },
        {
            "name": "Attach handoff notes",
            "status": "ok" if (artifact_dir / "reviewer-handoff.md").exists() else "todo",
            "instruction": "Copy reviewer-handoff.md into a PR, release note, or operator handoff message.",
        },
        {
            "name": "Use triage summary if blocked",
            "status": "ok" if (artifact_dir / "triage-summary.md").exists() else "todo",
            "instruction": "If any check fails, use triage-summary.md for narrow rerun targets instead of rerunning everything blindly.",
        },
    ]

    if missing:
        next_step = f"Run make ci-report, then regenerate the checklist. Missing: {', '.join(missing[:5])}."
    elif status == "blocked":
        next_step = "Resolve the listed release-health failures, rerun make verify, then refresh the checklist."
    elif status == "review":
        next_step = "Review warnings and confirm they are acceptable for the intended offline/demo handoff."
    else:
        next_step = "Share release-notes.md and reviewer-handoff.md with the PR or operator handoff."

    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": str(artifact_dir),
        "readiness": status,
        "health_notes": health_notes,
        "missing_artifacts": missing,
        "artifacts": artifacts,
        "checks": checks,
        "next_step": next_step,
    }


def render_markdown(checklist: dict[str, Any]) -> str:
    """Render a human-readable checklist."""

    lines = [
        "# Operator Readiness Checklist",
        "",
        f"Generated: {checklist['generated_at']}",
        f"Artifact directory: `{checklist['artifact_dir']}`",
        f"Readiness: **{checklist['readiness']}**",
        "",
        "## Health notes",
    ]
    for note in checklist["health_notes"]:
        lines.append(f"- {note}")

    lines.extend(["", "## Checklist"])
    for item in checklist["checks"]:
        marker = "[x]" if item["status"] == "ok" else "[ ]"
        lines.append(f"- {marker} **{item['name']}** ({item['status']}): {item['instruction']}")

    lines.extend(["", "## Key artifacts"])
    for artifact in checklist["artifacts"]:
        marker = "present" if artifact["exists"] else "missing"
        lines.append(f"- `{artifact['path']}` — {marker}; {artifact['purpose']}")

    lines.extend(["", "## Next step", "", str(checklist["next_step"]), ""])
    return "\n".join(lines)


def write_outputs(checklist: dict[str, Any], markdown_path: Path, json_path: Path) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(checklist), encoding="utf-8")
    json_path.write_text(json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an operator-facing readiness checklist from local CI artifacts.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR, help="Directory containing generated diagnostics artifacts.")
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_ARTIFACT_DIR / "operator-readiness.md", help="Markdown checklist output path.")
    parser.add_argument("--json-path", type=Path, default=DEFAULT_ARTIFACT_DIR / "operator-readiness.json", help="Machine-readable checklist output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checklist = build_checklist(args.artifact_dir)
    write_outputs(checklist, args.markdown_path, args.json_path)
    print(f"Wrote operator readiness checklist to {args.markdown_path} and {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
