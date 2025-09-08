"""Combine camera and LIDAR detections."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from app.config import settings
from app.analysis.sensor_certainty import fuse_sensor_confidences

from .camera_detector import (
    detect_camera_troops,
    detect_camera_vehicles,
    detect_camera_drones,
)
from .lidar_detector import (
    detect_lidar_troops,
    detect_lidar_vehicles,
    detect_lidar_drones,
)
from .bluetooth_detector import (
    detect_bluetooth_troops,
    detect_bluetooth_vehicles,
    detect_bluetooth_drones,
)


def fuse_sensor_detections(
    image_dets: List[Dict], lidar_dets: List[Dict], bt_dets: List[Dict] | None = None
) -> List[Dict]:
    """Combine sensor scores using reliability weights and report uncertainty.

    If LIDAR provides ``in_cover`` flags, the fused record will include an
    ``in_cover`` boolean indicating whether any sensor suggested the unit was
    under foliage or cover.
    """
    by_class: Dict[str, Dict[str, List[float]]] = {}
    cover_votes: Dict[str, List[bool]] = {}
    for det in image_dets:
        cls = det.get("class", "unknown")
        by_class.setdefault(cls, {}).setdefault("camera", []).append(
            det.get("confidence", 0.0)
        )
    for det in lidar_dets:
        cls = det.get("class", "unknown")
        by_class.setdefault(cls, {}).setdefault("lidar", []).append(
            det.get("confidence", 0.0)
        )
        if "in_cover" in det:
            cover_votes.setdefault(cls, []).append(bool(det["in_cover"]))
    if bt_dets:
        for det in bt_dets:
            cls = det.get("class", "unknown")
            by_class.setdefault(cls, {}).setdefault("bluetooth", []).append(
                det.get("confidence", 0.0)
            )
    weights = {
        "camera": settings.CAMERA_WEIGHT,
        "lidar": settings.LIDAR_WEIGHT,
        "bluetooth": settings.BLUETOOTH_WEIGHT,
    }
    fused: List[Dict[str, float | bool]] = []
    for cls, sensors in by_class.items():
        scores: List[float] = []
        wts: List[float] = []
        for sensor, confs in sensors.items():
            scores.append(sum(confs) / len(confs))
            wts.append(weights.get(sensor, 1.0))
        avg, uncert = fuse_sensor_confidences(scores, wts)
        item: Dict[str, float | bool] = {
            "class": cls,
            "confidence": avg,
            "uncertainty": uncert,
        }
        covers = cover_votes.get(cls)
        if covers:
            item["in_cover"] = any(covers)
        fused.append(item)
    return fused


def detect_fused_objects(
    image: Path, point_cloud: Path, bt_log: Path | None = None
) -> List[Dict]:
    """Run camera, LIDAR, and optional Bluetooth detectors and fuse results."""
    image_dets: List[Dict[str, float]] = []
    image_dets.extend(detect_camera_troops(image))
    image_dets.extend(detect_camera_vehicles(image))
    image_dets.extend(detect_camera_drones(image))

    lidar_dets: List[Dict[str, float]] = []
    lidar_dets.extend(detect_lidar_troops(point_cloud))
    lidar_dets.extend(detect_lidar_vehicles(point_cloud))
    lidar_dets.extend(detect_lidar_drones(point_cloud))

    bt_dets: List[Dict[str, float]] = []
    if bt_log is not None:
        bt_dets.extend(detect_bluetooth_troops(bt_log))
        bt_dets.extend(detect_bluetooth_vehicles(bt_log))
        bt_dets.extend(detect_bluetooth_drones(bt_log))

    return fuse_sensor_detections(image_dets, lidar_dets, bt_dets)
