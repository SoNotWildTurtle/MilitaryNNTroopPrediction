"""Analysis utilities for clustering troop movements."""

from .dbscan_cluster import cluster_recent_movements
from .heatmap import generate_heatmap
from .geo_mapper import map_detections
from .cluster_strategy_tracker import analyze_unit
from .threat_assessment import score_clusters
from .state_encoder import encode_state
from .image_stats import analyze_dataset
from .movement_stats import movement_stats
from .movement_predictor import predict_next_position
from .hog_features import extract_hog_features
from .feature_fusion import extract_feature_fusion
from .confidence_stats import confidence_summary
from .confidence_calibrator import calibrate_confidence
from .confidence_fusion import fuse_confidences
from .meta_analysis import meta_analysis
from .threat_model import predict_threat_level

__all__ = [
    "cluster_recent_movements",
    "generate_heatmap",
    "map_detections",
    "analyze_unit",
    "score_clusters",
    "encode_state",
    "analyze_dataset",
    "movement_stats",
    "predict_next_position",
    "extract_hog_features",
    "extract_feature_fusion",
    "confidence_summary",
    "calibrate_confidence",
    "fuse_confidences",
    "meta_analysis",
    "predict_threat_level",
]
