"""Detection utilities."""

from .yolo import detect_vehicles
from .ground_troop import detect_ground_troops
from .troop_identifier import load_classifier as load_troop_classifier, classify_troop
from .drone_identifier import classify_drone
from .vehicle_identifier import classify_vehicle
from .unified_identifier import load_unified_model, classify_target, add_target_to_model
from .vit_identifier import (
    load_vit_components,
    load_vit_classifier,
    classify_vit,
)
from .resnet_identifier import (
    load_resnet_components,
    load_resnet_classifier,
    classify_resnet,
)
from .swin_identifier import (
    load_swin_components,
    load_swin_classifier,
    classify_swin,
)
from .convnext_identifier import (
    load_convnext_components,
    load_convnext_classifier,
    classify_convnext,
)
from .feature_fused_identifier import (
    load_feature_fused_classifier,
    classify_feature_fused,
)
from .ensemble_identifier import classify_ensemble
from .clip_identifier import load_clip_components, classify_clip
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
from .acoustic_detector import detect_acoustic
from .sensor_fusion import fuse_sensor_detections, detect_fused_objects

__all__ = [
    "detect_vehicles",
    "detect_ground_troops",
    "load_troop_classifier",
    "classify_troop",
    "classify_drone",
    "classify_vehicle",
    "load_unified_model",
    "classify_target",
    "add_target_to_model",
    "load_vit_components",
    "load_vit_classifier",
    "classify_vit",
    "load_resnet_components",
    "load_resnet_classifier",
    "classify_resnet",
    "load_swin_components",
    "load_swin_classifier",
    "classify_swin",
    "load_convnext_components",
    "load_convnext_classifier",
    "classify_convnext",
    "load_feature_fused_classifier",
    "classify_feature_fused",
    "classify_ensemble",
    "load_clip_components",
    "classify_clip",
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
    "detect_acoustic",
    "fuse_sensor_detections",
    "detect_fused_objects",
]
