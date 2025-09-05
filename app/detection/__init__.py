"""Detection utilities."""

from .yolo import detect_vehicles
from .ground_troop import detect_ground_troops
from .troop_identifier import load_classifier as load_troop_classifier, classify_troop
from .drone_identifier import classify_drone
from .vehicle_identifier import classify_vehicle
from .tactical_wrapper import detect_and_tag, tag_doctrine
from .camera_detector import (
    detect_camera_troops,
    detect_camera_vehicles,
    detect_camera_drones,
    detect_camera_objects,
)
from .lidar_detector import (
    detect_lidar_troops,
    detect_lidar_vehicles,
    detect_lidar_drones,
    detect_lidar_objects,
)
from .bluetooth_detector import (
    detect_bluetooth_troops,
    detect_bluetooth_vehicles,
    detect_bluetooth_drones,
)
from .sensor_fusion import fuse_sensor_detections, detect_fused_objects

__all__ = [
    "detect_vehicles",
    "detect_ground_troops",
    "load_troop_classifier",
    "classify_troop",
    "classify_drone",
    "classify_vehicle",
    "detect_and_tag",
    "tag_doctrine",
    "detect_camera_troops",
    "detect_camera_vehicles",
    "detect_camera_drones",
    "detect_camera_objects",
    "detect_lidar_troops",
    "detect_lidar_vehicles",
    "detect_lidar_drones",
    "detect_lidar_objects",
    "detect_bluetooth_troops",
    "detect_bluetooth_vehicles",
    "detect_bluetooth_drones",
    "fuse_sensor_detections",
    "detect_fused_objects",
]
