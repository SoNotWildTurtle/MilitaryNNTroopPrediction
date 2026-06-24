"""Tests for static HTML artifact preview export."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.export_html_previews import export_previews, render_markdown, render_svg, summarize_html


class ExportHtmlPreviewsTests(unittest.TestCase):
    """Verify reviewer preview artifacts are deterministic and useful."""

    def test_summarize_html_extracts_title_heading_and_metrics(self) -> None:
        with TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "dashboard-mockup.html"
            html_path.write_text(
                """<!doctype html><html><head><title>Dashboard</title></head>
                <body><h1>Operational overview</h1><section><table><tr><td>Area</td></tr></table>
                <a href=\"openapi-summary.md\">OpenAPI</a></section></body></html>""",
                encoding="utf-8",
            )

            summary = summarize_html(html_path, "Fallback")

        self.assertEqual(summary["title"], "Dashboard")
        self.assertEqual(summary["heading"], "Operational overview")
        self.assertEqual(summary["links"], 1)
        self.assertEqual(summary["sections"], 1)
        self.assertEqual(summary["tables"], 1)
        self.assertGreater(summary["size_bytes"], 0)

    def test_render_svg_escapes_content(self) -> None:
        svg = render_svg(
            {
                "path": "unsafe.html",
                "title": "Unsafe <Title>",
                "heading": "Heading <script>",
                "excerpt": "Example & details",
                "links": 0,
                "sections": 0,
                "tables": 0,
                "size_bytes": 10,
            }
        )

        self.assertIn("Unsafe &lt;Title&gt;", svg)
        self.assertIn("Heading &lt;script&gt;", svg)
        self.assertIn("Example &amp; details", svg)

    def test_export_previews_writes_svg_and_markdown_index(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "dashboard-mockup.html").write_text(
                "<html><head><title>Dashboard</title></head><body><h1>Dashboard</h1></body></html>",
                encoding="utf-8",
            )
            summaries = export_previews(artifact_dir)
            markdown = render_markdown(summaries)
            svg_path = artifact_dir / "previews" / "dashboard-mockup.svg"

            svg_text = svg_path.read_text(encoding="utf-8")

        self.assertEqual(len(summaries), 1)
        self.assertIn("dashboard-mockup.html", markdown)
        self.assertIn("previews/dashboard-mockup.svg", markdown)
        self.assertIn("<svg", svg_text)
        self.assertIn("Dashboard", svg_text)


if __name__ == "__main__":
    unittest.main()
