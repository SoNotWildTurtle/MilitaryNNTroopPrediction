"""Compute statistics on detection confidences."""
from collections import defaultdict
from pathlib import Path
import json
from typing import Dict, List


def confidence_summary(detections_file: Path) -> Dict[str, Dict[str, float]]:
    """Return count and confidence metrics per class from a JSON list.

    The JSON file should contain a list of objects, each with ``class`` and
    ``confidence`` keys. Example entry::

        {"class": "tank", "confidence": 0.87}
    """
    data = json.loads(Path(detections_file).read_text())
    grouped: Dict[str, List[float]] = defaultdict(list)
    for det in data:
        cls = det.get("class", "unknown")
        grouped[cls].append(float(det.get("confidence", 0.0)))

    summary: Dict[str, Dict[str, float]] = {}
    for cls, values in grouped.items():
        if not values:
            continue
        summary[cls] = {
            "count": len(values),
            "avg_confidence": sum(values) / len(values),
            "min_confidence": min(values),
            "max_confidence": max(values),
        }
    return summary


if __name__ == "__main__":
    import argparse, pprint

    parser = argparse.ArgumentParser(description="Summarize detection confidences")
    parser.add_argument("json_file", type=Path, help="Path to detection JSON list")
    args = parser.parse_args()
    pprint.pprint(confidence_summary(args.json_file))
