"""Built-in catalog of sample space-based imagery."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Dict, Optional

from ..config import settings


@dataclass
class BuiltinScene:
    """Metadata for a bundled satellite scene."""

    scene_id: str
    asset_type: str
    country: str
    description: str
    image_path: Path
    labels: List[Dict[str, object]]

    def to_record(self) -> Dict[str, object]:
        """Return a serializable representation of the scene."""
        data = asdict(self)
        data["image_path"] = str(self.image_path)
        return data


_CATALOG_CACHE: List[BuiltinScene] = []


def _default_scene_definitions(base_dir: Path) -> List[Dict[str, object]]:
    """Return static definitions for bundled satellite scenes."""
    return [
        {
            "scene_id": "ru_troops_kherson",
            "asset_type": "troops",
            "country": "Russia",
            "description": "Battalion tactical group staging near Kherson",
            "filename": "ru_troops_kherson.png",
            "labels": [
                {
                    "category": "troops",
                    "faction": "Russian Ground Forces",
                    "unit": "76th Guards Air Assault Division",
                    "confidence": 0.92,
                    "notes": "Defensive berms and vehicle revetments visible",
                }
            ],
        },
        {
            "scene_id": "ru_tanks_t90",
            "asset_type": "tanks",
            "country": "Russia",
            "description": "Armour column featuring T-90M tanks outside Belgorod",
            "filename": "ru_tanks_t90.png",
            "labels": [
                {
                    "category": "vehicle",
                    "model": "T-90M",
                    "faction": "Russian Ground Forces",
                    "confidence": 0.9,
                    "notes": "Distinctive Relikt ERA layout and turret cage",
                }
            ],
        },
        {
            "scene_id": "ru_drone_orlan10",
            "asset_type": "drones",
            "country": "Russia",
            "description": "Orlan-10 UAV launch site with support trucks",
            "filename": "ru_drone_orlan10.png",
            "labels": [
                {
                    "category": "drone",
                    "model": "Orlan-10",
                    "faction": "Russian Aerospace Forces",
                    "confidence": 0.88,
                    "notes": "Launch catapult and control shelter identified",
                }
            ],
        },
        {
            "scene_id": "ir_drone_shahed136",
            "asset_type": "drones",
            "country": "Iran",
            "description": "Shahed-136 assembly area supporting Russian deployments",
            "filename": "ir_drone_shahed136.png",
            "labels": [
                {
                    "category": "drone",
                    "model": "Shahed-136",
                    "faction": "IRGC Aerospace Force",
                    "confidence": 0.89,
                    "notes": "Triangular wing profile with launch racks",
                }
            ],
        },
    ]


def _ensure_catalog() -> List[BuiltinScene]:
    """Load or build the cached catalog."""
    if _CATALOG_CACHE:
        return _CATALOG_CACHE
    base_dir = settings.DATA_DIR / "builtin_space"
    base_dir.mkdir(parents=True, exist_ok=True)
    scenes: List[BuiltinScene] = []
    for entry in _default_scene_definitions(base_dir):
        image_path = base_dir / entry["filename"]
        if not image_path.exists():
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b"")
        scenes.append(
            BuiltinScene(
                scene_id=entry["scene_id"],
                asset_type=entry["asset_type"],
                country=entry["country"],
                description=entry["description"],
                image_path=image_path,
                labels=entry["labels"],
            )
        )
    _CATALOG_CACHE.extend(scenes)
    return _CATALOG_CACHE


def list_builtin_scenes(
    asset_type: Optional[str] = None,
    country: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return catalog entries filtered by asset type or country."""
    asset_filter = asset_type.lower() if asset_type else None
    country_filter = country.lower() if country else None
    records: List[Dict[str, object]] = []
    for scene in _ensure_catalog():
        if asset_filter and scene.asset_type.lower() != asset_filter:
            continue
        if country_filter and scene.country.lower() != country_filter:
            continue
        records.append(scene.to_record())
    return records


def iter_builtin_scenes(
    asset_type: Optional[str] = None,
    country: Optional[str] = None,
) -> Iterable[BuiltinScene]:
    """Yield catalog scenes respecting optional filters."""
    asset_filter = asset_type.lower() if asset_type else None
    country_filter = country.lower() if country else None
    for scene in _ensure_catalog():
        if asset_filter and scene.asset_type.lower() != asset_filter:
            continue
        if country_filter and scene.country.lower() != country_filter:
            continue
        yield scene


def find_scene_by_id(scene_id: str) -> Optional[BuiltinScene]:
    """Return a built-in scene for the provided identifier."""
    scene_id_lower = scene_id.lower()
    for scene in _ensure_catalog():
        if scene.scene_id.lower() == scene_id_lower:
            return scene
    return None


def find_scene_by_image(image_path: Path) -> Optional[BuiltinScene]:
    """Match an on-disk image to a catalog scene."""
    target = image_path.resolve()
    for scene in _ensure_catalog():
        if scene.image_path.resolve() == target:
            return scene
    return None


__all__ = [
    "BuiltinScene",
    "list_builtin_scenes",
    "iter_builtin_scenes",
    "find_scene_by_id",
    "find_scene_by_image",
]
