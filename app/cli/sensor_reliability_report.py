"""Display configured sensor reliability weights."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from app.config import settings


def run_sensor_reliability_report() -> None:
    table = Table(title="Sensor Reliability")
    table.add_column("Sensor")
    table.add_column("Weight", justify="right")
    table.add_row("camera", f"{settings.CAMERA_WEIGHT:.2f}")
    table.add_row("lidar", f"{settings.LIDAR_WEIGHT:.2f}")
    table.add_row("bluetooth", f"{settings.BLUETOOTH_WEIGHT:.2f}")
    Console().print(table)


if __name__ == "__main__":  # pragma: no cover
    run_sensor_reliability_report()
