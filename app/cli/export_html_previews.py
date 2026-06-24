"""Generate lightweight SVG previews for static HTML diagnostic artifacts."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR

DEFAULT_TARGETS: Mapping[str, str] = {
    "dashboard-mockup.html": "Dashboard mockup",
    "release-bundle-index.html": "Release bundle index",
}
DEFAULT_OUTPUT_DIR_NAME = "previews"

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)


def _strip_markup(text: str) -> str:
    """Collapse a small HTML fragment into safe plain text."""

    no_tags = _TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", html.unescape(no_tags)).strip()


def summarize_html(path: Path, fallback_title: str) -> Dict[str, object]:
    """Build a deterministic summary for a generated HTML artifact."""

    raw = path.read_text(encoding="utf-8")
    title_match = _TITLE_RE.search(raw)
    heading_match = _HEADING_RE.search(raw)
    title = _strip_markup(title_match.group(1)) if title_match else fallback_title
    heading = _strip_markup(heading_match.group(1)) if heading_match else title
    body_text = _strip_markup(raw)
    words = body_text.split()
    excerpt = " ".join(words[:42])
    if len(words) > 42:
        excerpt += "..."
    links = len(re.findall(r"<a\s+", raw, flags=re.IGNORECASE))
    sections = len(re.findall(r"<section\b", raw, flags=re.IGNORECASE))
    tables = len(re.findall(r"<table\b", raw, flags=re.IGNORECASE))
    return {
        "path": path.name,
        "title": title or fallback_title,
        "heading": heading or title or fallback_title,
        "excerpt": excerpt,
        "links": links,
        "sections": sections,
        "tables": tables,
        "size_bytes": path.stat().st_size,
    }


def render_svg(summary: Mapping[str, object]) -> str:
    """Render a compact SVG card preview for a static HTML artifact."""

    title = html.escape(str(summary["title"]))
    heading = html.escape(str(summary["heading"]))
    path = html.escape(str(summary["path"]))
    excerpt = html.escape(str(summary.get("excerpt", "")))
    metrics = (
        f"{summary.get('sections', 0)} sections · "
        f"{summary.get('tables', 0)} tables · "
        f"{summary.get('links', 0)} links · "
        f"{summary.get('size_bytes', 0)} bytes"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="Preview for {title}">
  <rect width="1200" height="630" rx="0" fill="#0f172a"/>
  <rect x="56" y="56" width="1088" height="518" rx="28" fill="#111827" stroke="#334155" stroke-width="3"/>
  <text x="92" y="122" fill="#93c5fd" font-family="Arial, sans-serif" font-size="30" font-weight="700">MilitaryNNTroopPrediction</text>
  <text x="92" y="187" fill="#f8fafc" font-family="Arial, sans-serif" font-size="52" font-weight="800">{heading}</text>
  <text x="92" y="238" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="28">{path}</text>
  <foreignObject x="92" y="282" width="1010" height="150">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: Arial, sans-serif; color: #e2e8f0; font-size: 28px; line-height: 1.35;">{excerpt}</div>
  </foreignObject>
  <rect x="92" y="470" width="1010" height="62" rx="18" fill="#020617" stroke="#334155"/>
  <text x="124" y="511" fill="#86efac" font-family="Arial, sans-serif" font-size="26" font-weight="700">{html.escape(metrics)}</text>
  <text x="92" y="552" fill="#94a3b8" font-family="Arial, sans-serif" font-size="20">Static browser-free preview generated from CI artifact HTML.</text>
</svg>
'''


def _target_slug(path_name: str) -> str:
    return path_name.rsplit(".", 1)[0] + ".svg"


def export_previews(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    output_dir: Path | None = None,
    targets: Mapping[str, str] = DEFAULT_TARGETS,
) -> List[Dict[str, object]]:
    """Create SVG previews for present target HTML artifacts."""

    destination = output_dir or artifact_dir / DEFAULT_OUTPUT_DIR_NAME
    destination.mkdir(parents=True, exist_ok=True)
    summaries: List[Dict[str, object]] = []
    for path_name, fallback_title in targets.items():
        html_path = artifact_dir / path_name
        if not html_path.exists():
            continue
        summary = summarize_html(html_path, fallback_title)
        svg_path = destination / _target_slug(path_name)
        svg_path.write_text(render_svg(summary), encoding="utf-8")
        summary["preview_path"] = str(svg_path.relative_to(artifact_dir)) if svg_path.is_relative_to(artifact_dir) else str(svg_path)
        summaries.append(summary)
    return summaries


def render_markdown(summaries: Iterable[Mapping[str, object]]) -> str:
    """Render a small Markdown index for generated previews."""

    rows = ["# HTML artifact previews", "", "| Artifact | Preview | Details |", "| --- | --- | --- |"]
    for summary in summaries:
        rows.append(
            "| "
            f"`{summary['path']}` | "
            f"[`{summary['preview_path']}`]({summary['preview_path']}) | "
            f"{summary.get('sections', 0)} sections, {summary.get('tables', 0)} tables, {summary.get('links', 0)} links |"
        )
    if len(rows) == 4:
        rows.append("| _No supported HTML artifacts were found._ | - | - |")
    return "\n".join(rows) + "\n"


def write_markdown(markdown: str, path: Path) -> None:
    """Write the preview Markdown index."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(
        description="Generate lightweight SVG previews for static HTML diagnostic artifacts."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated HTML artifacts. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for SVG previews. Default: <artifact-dir>/previews",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=None,
        help="Markdown preview index path. Default: <artifact-dir>/html-previews.md",
    )
    return parser


def main() -> int:
    """CLI entry point."""

    args = build_parser().parse_args()
    summaries = export_previews(args.artifact_dir, args.output_dir)
    markdown_path = args.markdown_path or args.artifact_dir / "html-previews.md"
    write_markdown(render_markdown(summaries), markdown_path)
    print(f"Wrote {len(summaries)} HTML previews and index to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
