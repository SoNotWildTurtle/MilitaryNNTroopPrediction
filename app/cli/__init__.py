"""Interactive command-line dashboard utilities."""

from .dashboard import run_dashboard
from .configure import run_config_setup
from .self_reinforce import self_reinforce
from .train_wizard import run_train_wizard
from .report import run_detection_report
from .generate_demo_data import run_demo_data_generator
from .verify_dataset import run_verify_dataset
from .discover_sources import run_source_discovery
from .anomaly_report import run_anomaly_report
from .trend_report import run_trend_report
from .cooccurrence_report import run_cooccurrence_report
from .burst_report import run_burst_report
from .lag_report import run_lag_report
from .activity_report import run_activity_report
from .weekly_report import run_weekly_report
from .moving_report import run_moving_report
from .volatility_report import run_volatility_report
from .interarrival_report import run_interarrival_report
from .peak_report import run_peak_report
from .changepoint_report import run_changepoint_report
from .diversity_report import run_diversity_report
from .speed_report import run_speed_report
from .acceleration_report import run_acceleration_report
from .confidence_report import run_confidence_report
from .fusion_report import run_fusion_report
from .space_identification import run_space_identification
from .export_geojson import run_geojson_export
from .streak_report import run_streak_report
from .coanalysis_report import run_coanalysis_report
from .method_cohesion_report import run_method_cohesion_report
from .train_sensor import run_sensor_training
from .train_sensor_pointcloud import run_sensor_pointcloud_training
from .train_gaussian_pointcloud import run_gaussian_pointcloud_training
from .gaussian_match_report import run_gaussian_match_report
from .gaussian_mixture_report import run_gaussian_mixture_report
from .update_gaussian_model import run_gaussian_update
from .train_pointnet_gaussian import run_pointnet_gaussian_training
from .pointnet_gaussian_report import run_pointnet_gaussian_report
from .sensor_reliability_report import run_sensor_reliability_report
from .train_acoustic import run_acoustic_training
from .train_fused_gaussian import run_train_fused_gaussian
from .fused_gaussian_report import run_fused_gaussian_report
from .train_gaussian_nb import run_train_gaussian_nb
from .gaussian_nb_report import run_gaussian_nb_report
from .train_gaussian_kde import run_train_gaussian_kde
from .gaussian_kde_report import run_gaussian_kde_report
from .train_gaussian_process import run_train_gaussian_process
from .gaussian_process_report import run_gaussian_process_report
from .item_catalog import run_item_catalog
from .extend_unified_model import run_extend_unified_model
from .train_vit_identifier import run_train_vit_identifier
from .train_resnet_identifier import run_train_resnet_identifier
from .train_orb_bow import run_train_orb_bow
from .orb_bow_report import run_orb_bow_report
from .clip_classify import run_clip_classify
from .resnet_classify import run_resnet_classify
from .train_swin_identifier import run_train_swin_identifier
from .swin_classify import run_swin_classify
from .train_convnext_identifier import run_train_convnext_identifier
from .convnext_classify import run_convnext_classify
from .prediction_correlation_report import run_prediction_correlation_report
from .train_feature_fused_identifier import run_train_feature_fused_identifier
from .feature_fused_classify import run_feature_fused_classify
from .ensemble_classify import run_ensemble_classify
from .cohesion_report import run_cohesion_report
from .doctrine_movement_report import run_doctrine_movement_report
from .calibrate_confidence import run_confidence_calibration

__all__ = [
    "run_dashboard",
    "run_config_setup",
    "self_reinforce",
    "run_train_wizard",
    "run_detection_report",
    "run_demo_data_generator",
    "run_verify_dataset",
    "run_source_discovery",
    "run_anomaly_report",
    "run_trend_report",
    "run_cooccurrence_report",
    "run_burst_report",
    "run_lag_report",
    "run_activity_report",
    "run_weekly_report",
    "run_moving_report",
    "run_volatility_report",
    "run_interarrival_report",
    "run_peak_report",
    "run_changepoint_report",
    "run_diversity_report",
    "run_speed_report",
    "run_acceleration_report",
    "run_confidence_report",
    "run_confidence_calibration",
    "run_fusion_report",
    "run_space_identification",
    "run_geojson_export",
    "run_streak_report",
    "run_coanalysis_report",
    "run_method_cohesion_report",
    "run_sensor_training",
    "run_sensor_pointcloud_training",
    "run_gaussian_pointcloud_training",
    "run_gaussian_match_report",
    "run_gaussian_mixture_report",
    "run_gaussian_update",
    "run_pointnet_gaussian_training",
    "run_pointnet_gaussian_report",
    "run_sensor_reliability_report",
    "run_acoustic_training",
    "run_train_fused_gaussian",
    "run_fused_gaussian_report",
    "run_train_gaussian_nb",
    "run_gaussian_nb_report",
    "run_train_gaussian_kde",
    "run_gaussian_kde_report",
    "run_train_gaussian_process",
    "run_gaussian_process_report",
    "run_item_catalog",
    "run_extend_unified_model",
    "run_train_vit_identifier",
    "run_train_resnet_identifier",
    "run_train_orb_bow",
    "run_orb_bow_report",
    "run_clip_classify",
    "run_resnet_classify",
    "run_train_swin_identifier",
    "run_swin_classify",
    "run_train_convnext_identifier",
    "run_convnext_classify",
    "run_prediction_correlation_report",
    "run_train_feature_fused_identifier",
    "run_feature_fused_classify",
    "run_ensemble_classify",
    "run_cohesion_report",
    "run_doctrine_movement_report",
]
