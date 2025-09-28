"""Export recent detections to a GeoJSON file."""
from __future__ import annotations

import argparse
from rich.console import Console
from rich.prompt import Prompt

from ..movement_history import recent_detections
from ..analysis.geojson_export import write_geojson
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate static UI text if a non-English language is configured."""
    return translate_text(text, target_lang=_LANG)


def run_geojson_export(
    area: str | None = None, out: str | None = None, limit: int = 100
) -> None:
    """Fetch recent detections and write them to ``out`` in GeoJSON format."""
    if area is None:
        area = Prompt.ask(_t("Area name"))
    if out is None:
        out = Prompt.ask(_t("Output file"), default="detections.geojson")
    if limit is None:
        limit = int(Prompt.ask(_t("Number of records"), default=str(limit)))
    detections = recent_detections(area, limit=limit)
    if not detections:
        console.print(_t("No detections found"), style="yellow")
        return
    write_geojson(detections, out)
    console.print(_t("Wrote GeoJSON to {path}").format(path=out))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_t("Export detections to GeoJSON"), add_help=True
    )
    parser.add_argument("--area", type=str, help=_t("Area name"))
    parser.add_argument(
        "--out", type=str, default="detections.geojson", help=_t("Output file")
    )
    parser.add_argument(
        "--limit", type=int, default=100, help=_t("Number of records")
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_geojson_export(args.area, args.out, args.limit)
