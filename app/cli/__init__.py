"""Interactive command-line dashboard utilities."""

from .dashboard import run_dashboard
from .configure import run_config_setup
from .self_reinforce import self_reinforce
from .train_wizard import run_train_wizard
from .report import run_detection_report
from .generate_demo_data import run_demo_data_generator

__all__ = [
    "run_dashboard",
    "run_config_setup",
    "self_reinforce",
    "run_train_wizard",
    "run_detection_report",
    "run_demo_data_generator",
]
