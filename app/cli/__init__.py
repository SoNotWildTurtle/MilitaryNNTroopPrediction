"""Interactive command-line dashboard utilities."""

from .dashboard import run_dashboard
from .configure import run_config_setup
from .self_reinforce import self_reinforce
from .train_wizard import run_train_wizard
from .report import run_detection_report
from .generate_demo_data import run_demo_data_generator
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

__all__ = [
    "run_dashboard",
    "run_config_setup",
    "self_reinforce",
    "run_train_wizard",
    "run_detection_report",
    "run_demo_data_generator",
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
]
