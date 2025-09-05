"""Combine camera and LIDAR detections."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

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
    """Average confidences for classes seen by multiple sensors."""
    by_class: Dict[str, List[float]] = {}
    for det in image_dets:
        cls = det.get("class", "unknown")
        by_class.setdefault(cls, []).append(det.get("confidence", 0.0))
    for det in lidar_dets:
        cls = det.get("class", "unknown")
        by_class.setdefault(cls, []).append(det.get("confidence", 0.0))
    if bt_dets:
        for det in bt_dets:
            cls = det.get("class", "unknown")
            by_class.setdefault(cls, []).append(det.get("confidence", 0.0))
    fused: List[Dict[str, float]] = []
    for cls, scores in by_class.items():
        fused.append({"class": cls, "confidence": sum(scores) / len(scores)})
    return fused


def detect_fused_objects(
    image: Path, point_cloud: Path, bt_log: Path | None = None
) -> List[Dict[str, float]]:
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
