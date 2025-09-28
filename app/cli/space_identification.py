"""CLI to inspect built-in space-based imagery and known asset identifications."""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from ..config import settings
from ..detection import identify_scene_by_id
from ..satellite import iter_builtin_scenes
from ..translation import translate_text

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _render_scene(scene_id: str) -> None:
    results = identify_scene_by_id(scene_id)
    if not results:
        console.print(_t("No catalogued identifications"), style="yellow")
        return

    table = Table(title=_t("Built-in asset identifications"))
    table.add_column(_t("Scene"))
    table.add_column(_t("Asset type"))
    table.add_column(_t("Country"))
    table.add_column(_t("Label"))
    table.add_column(_t("Confidence"), justify="right")
    table.add_column(_t("Notes"))

    for record in results:
        label = record.get("model") or record.get("unit") or record.get("category")
        confidence = record.get("confidence")
        notes = record.get("notes", "")
        table.add_row(
            record["scene_id"],
            record["asset_type"],
            record["country"],
            str(label),
            f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "-",
            notes,
        )

    console.print(table)


def run_space_identification() -> None:
    parser = argparse.ArgumentParser(description=_t("Review bundled space imagery and identifications"))
    parser.add_argument("scene", nargs="?", help=_t("Specific scene identifier to inspect"))
    parser.add_argument("--asset", dest="asset", help=_t("Filter by asset type (troops, tanks, drones)"))
    parser.add_argument("--country", dest="country", help=_t("Filter by country"))
    args = parser.parse_args()

    if args.scene:
        _render_scene(args.scene)
        return

    scenes = list(iter_builtin_scenes(asset_type=args.asset, country=args.country))
    if not scenes:
        console.print(_t("No built-in scenes match the provided filters"), style="yellow")
        return

    table = Table(title=_t("Available built-in scenes"))
    table.add_column(_t("Scene"))
    table.add_column(_t("Asset type"))
    table.add_column(_t("Country"))
    table.add_column(_t("Description"))
    table.add_column(_t("Image path"))

    for scene in scenes:
        table.add_row(
            scene.scene_id,
            scene.asset_type,
            scene.country,
            scene.description,
            str(scene.image_path),
        )

    console.print(table)
    console.print(
        _t("Pass a scene identifier to view identifications, e.g. `python -m app.cli.space_identification ru_troops_kherson`"),
        style="cyan",
    )


if __name__ == "__main__":
    run_space_identification()
