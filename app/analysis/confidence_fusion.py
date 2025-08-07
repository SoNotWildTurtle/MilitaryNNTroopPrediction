"""Fuse detection and classification confidences for higher trust."""
from __future__ import annotations

from typing import Dict, List


def fuse_confidences(detections: List[Dict]) -> List[Dict]:
    """Combine various confidence scores into a single ``fused_confidence``.

    Parameters
    ----------
    detections: list of detection dictionaries. Each detection may contain
        ``det_conf`` from the detector and optional classifier scores such as
        ``type_conf``, ``uniform_conf``, ``drone_conf`` or ``vehicle_conf``.

    Returns
    -------
    list of detections with a new ``fused_confidence`` key when scores are
    available.
    """
    for det in detections:
        scores = [det[key] for key in (
            "det_conf",
            "type_conf",
            "uniform_conf",
            "drone_conf",
            "vehicle_conf",
        ) if isinstance(det.get(key), (int, float))]
        if scores:
            det["fused_confidence"] = sum(scores) / len(scores)
    return detections
