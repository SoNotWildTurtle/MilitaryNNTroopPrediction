"""Combine image and point cloud detections to cross-check results."""
from __future__ import annotations

from math import hypot
from typing import Iterable, Dict, List


Detection = Dict[str, float | str]


def coanalyze_pointcloud_and_images(
    image_dets: Iterable[Detection],
    pointcloud_dets: Iterable[Detection],
    threshold: float = 5.0,
) -> List[Detection]:
    """Return fused detections where image and point-cloud points are close.

    Each detection is a dictionary with ``x``, ``y``, ``class`` and optional
    ``conf`` fields. Matches are averaged and returned with a combined
    confidence value.
    """
    results: List[Detection] = []
    for img in image_dets:
        for cloud in pointcloud_dets:
            dist = hypot(float(img["x"]) - float(cloud["x"]), float(img["y"]) - float(cloud["y"]))
            if dist <= threshold:
                fused_conf = (
                    float(img.get("conf", 0.0)) + float(cloud.get("conf", 0.0))
                ) / 2.0
                results.append(
                    {
                        "x": (float(img["x"]) + float(cloud["x"])) / 2.0,
                        "y": (float(img["y"]) + float(cloud["y"])) / 2.0,
                        "class": f"{img.get('class', 'unknown')}/{cloud.get('class', 'unknown')}",
                        "conf": fused_conf,
                    }
                )
    return results
