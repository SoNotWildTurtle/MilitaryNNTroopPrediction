"""Audit generated handoff artifacts for analytical framing risks.

This module performs a deterministic, offline text scan over local diagnostic
artifacts. It helps reviewers find overconfident wording, missing analytical
scope language, and operationally framed phrases before a bundle is shared. It
never runs collection, prediction, training, database, deployment, or network
workflows.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "analytical-framing-audit.md"
DEFAULT_JSON_NAME = "analytical-framing-audit.json"

SAFE_SCOPE = (
    "Offline diagnostic text audit for lawful defensive analysis handoffs. It "
    "flags language that may imply certainty, live operational use, or missing "
    "analytical caveats; it does not validate ground truth, run prediction, or "
    "provide operational direction."
)

DEFAULT_INCLUDE_PATTERNS = ("*.md", "*.txt", "*.json")
SKIP_FILENAMES = {
    DEFAULT_MARKDOWN_NAME,
    DEFAULT_JSON_NAME,
    "artifact-manifest.json",
    "pip-freeze.txt",
}

REQUIRED_SCOPE_TERMS = (
    "analytical",
    "estimate",
    "uncertainty",
    "synthetic",
    "not operational",
    "safe",
)

RISK_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "certainty_language",
        "warn",
        r"\b(?:guaranteed|certainly|definitely|proves?|confirmed truth|ground truth|will happen)\b",
    ),
    (
        "operational_framing",
        "warn",
        r"\b(?:actionable target|target package|strike|engage|interdict|fire mission|kill chain)\b",
    ),
    (
        "authority_overclaim",
        "warn",
        r"\b(?:validated as real|official intelligence|live operational feed|production intelligence)\b",
    ),
    (
        "missing_uncertainty_caveat",
        "info",
        r"\b(?:prediction|forecast|estimate|assessment)\b",
    ),
)


@dataclass(frozen=True)
class Finding:
    """A single language framing finding from one artifact line."""

    severity: str
    rule: str
    path: str
    line: int
    excerpt: str
    recommendation: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "rule": self.rule,
            "path": self.path,
            "line": self.line,
            "excerpt": self.excerpt,
            "recommendation": self.recommendation,
        }


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _iter_candidate_files(artifact_dir: Path, include_patterns: Sequence[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in include_patterns:
        for path in artifact_dir.rglob(pattern):
            if path in seen or not path.is_file() or path.name in SKIP_FILENAMES:
                continue
            if any(part.startswith(".") for part in path.relative_to(artifact_dir).parts):
                continue
            seen.add(path)
            yield path


def _line_excerpt(line: str, limit: int = 180) -> str:
    compact = " ".join(line.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _recommendation(rule: str) -> str:
    recommendations = {
        "certainty_language": "Use estimate-oriented wording and include uncertainty or validation limits.",
        "operational_framing": "Reframe as defensive analytical review; avoid operational direction or targeting language.",
        "authority_overclaim": "State data provenance and validation status without implying official or live truth.",
        "missing_uncertainty_caveat": "Pair predictive terms with uncertainty, assumptions, or synthetic-data caveats.",
    }
    return recommendations.get(rule, "Review wording for safe analytical framing.")


def _scope_term_hits(text: str) -> Dict[str, bool]:
    lowered = text.lower()
    return {term: term in lowered for term in REQUIRED_SCOPE_TERMS}


def _scan_file(path: Path, artifact_dir: Path) -> List[Finding]:
    findings: List[Finding] = []
    text = _load_text(path)
    rel_path = path.relative_to(artifact_dir).as_posix()
    scope_hits = _scope_term_hits(text)
    has_uncertainty_language = scope_hits["uncertainty"] or scope_hits["estimate"]

    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule, severity, pattern in RISK_RULES:
            if rule == "missing_uncertainty_caveat" and has_uncertainty_language:
                continue
            if re.search(pattern, line, flags=re.IGNORECASE):
                findings.append(
                    Finding(
                        severity=severity,
                        rule=rule,
                        path=rel_path,
                        line=line_number,
                        excerpt=_line_excerpt(line),
                        recommendation=_recommendation(rule),
                    )
                )
    if not any(scope_hits.values()) and text.strip():
        findings.append(
            Finding(
                severity="info",
                rule="missing_safe_scope_terms",
                path=rel_path,
                line=1,
                excerpt="No standard safe-scope terms detected in this artifact.",
                recommendation="Add analytical, uncertainty, synthetic, estimate, or not-operational scope language where appropriate.",
            )
        )
    return findings


def _severity_counts(findings: Sequence[Finding]) -> Dict[str, int]:
    counts = {"warn": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def build_analytical_framing_audit(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
    include_patterns: Sequence[str] = DEFAULT_INCLUDE_PATTERNS,
) -> Dict[str, Any]:
    """Build a deterministic offline audit of generated artifact language."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    files = sorted(_iter_candidate_files(artifact_dir, include_patterns), key=lambda item: item.as_posix())
    findings: List[Finding] = []
    for path in files:
        findings.extend(_scan_file(path, artifact_dir))

    counts = _severity_counts(findings)
    status = "needs_review" if counts.get("warn", 0) else "ready"
    next_action = (
        "Review warning findings, revise overconfident or operational wording, then regenerate the bundle."
        if status == "needs_review"
        else "Attach this audit with the diagnostics bundle and rerun make verify before handoff."
    )
    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "next_action": next_action,
        "artifact_dir": artifact_dir.as_posix(),
        "scanned_files": [path.relative_to(artifact_dir).as_posix() for path in files],
        "scanned_file_count": len(files),
        "include_patterns": list(include_patterns),
        "severity_counts": counts,
        "findings": [finding.as_dict() for finding in findings],
        "safe_scope": SAFE_SCOPE,
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(report: Mapping[str, Any]) -> Iterable[str]:
    yield "# Analytical Framing Audit"
    yield ""
    yield "A deterministic offline scan for wording that could overstate certainty or blur safe analytical scope."
    yield ""
    yield f"Generated: `{report['generated_at']}`"
    yield f"Status: **{str(report['status']).upper()}**"
    yield f"Next action: {report['next_action']}"
    yield ""
    yield "## Summary"
    yield ""
    yield f"- Artifact directory: `{report['artifact_dir']}`"
    yield f"- Scanned files: `{report['scanned_file_count']}`"
    counts = report.get("severity_counts", {})
    yield f"- Warnings: `{counts.get('warn', 0)}`"
    yield f"- Informational findings: `{counts.get('info', 0)}`"
    yield ""
    yield "## Findings"
    yield ""
    findings = list(report.get("findings", []))
    if not findings:
        yield "No framing findings were detected in the scanned artifacts."
    else:
        yield "| Severity | Rule | Location | Excerpt | Recommendation |"
        yield "| --- | --- | --- | --- | --- |"
        for finding in findings:
            location = f"{finding.get('path', '')}:{finding.get('line', '')}"
            yield (
                f"| {_escape_table(str(finding.get('severity', '')).upper())} "
                f"| `{_escape_table(finding.get('rule', ''))}` "
                f"| `{_escape_table(location)}` "
                f"| {_escape_table(finding.get('excerpt', ''))} "
                f"| {_escape_table(finding.get('recommendation', ''))} |"
            )
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(report["safe_scope"])


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render an analytical framing audit as Markdown."""

    return "\n".join(_markdown_lines(report)).rstrip() + "\n"


def write_outputs(report: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested audit outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit generated diagnostics for safe analytical framing and uncertainty language."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated diagnostics. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--include-pattern",
        action="append",
        dest="include_patterns",
        default=None,
        help="Glob pattern to scan. Can be repeated. Defaults to Markdown, text, and JSON artifacts.",
    )
    parser.add_argument("--markdown-path", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=None, help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    include_patterns = tuple(args.include_patterns or DEFAULT_INCLUDE_PATTERNS)
    report = build_analytical_framing_audit(args.artifact_dir, include_patterns=include_patterns)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(report, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote analytical framing audit Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote analytical framing audit JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write audit files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
