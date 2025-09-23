"""Identify known Russian and Iranian assets from built-in imagery."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..satellite.builtin_catalog import (
    BuiltinScene,
    find_scene_by_id,
    find_scene_by_image,
)


def _scene_results(scene: BuiltinScene) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for entry in scene.labels:
        record: Dict[str, object] = {
            "scene_id": scene.scene_id,
            "asset_type": scene.asset_type,
            "country": scene.country,
            "description": scene.description,
            "source": "builtin_space_catalog",
        }
        record.update(entry)
        results.append(record)
    return results


def identify_known_assets(image: Path) -> List[Dict[str, object]]:
    """Return catalogued identifications for a built-in scene."""
    scene = find_scene_by_image(Path(image))
    if not scene:
        return []
    return _scene_results(scene)


def identify_scene_by_id(scene_id: str) -> List[Dict[str, object]]:
    """Return catalogued identifications using a scene identifier."""
    scene = find_scene_by_id(scene_id)
    if not scene:
        return []
    return _scene_results(scene)


__all__ = ["identify_known_assets", "identify_scene_by_id"]
