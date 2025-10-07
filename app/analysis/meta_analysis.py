"""High-level meta analysis of detection and feedback logs."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..database import get_collection


def meta_analysis(
    hours: int = 24,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Aggregate detection counts, average confidences, feedback accuracy and
    movement cluster counts for a given timeframe."""
    if start or end:
        time_filter = {}
        if start:
            time_filter["$gte"] = start
        if end:
            time_filter["$lte"] = end
    else:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        time_filter = {"$gte": cutoff}

    # Detection stats
    det_coll = get_collection("detections")
    det_cursor = det_coll.find({"timestamp": time_filter})
    det_conf: Dict[str, List[float]] = defaultdict(list)
    for doc in det_cursor:
        cls = doc.get("class", "unknown")
        det_conf[cls].append(float(doc.get("confidence", 0.0)))

    det_summary = {
        cls: {
            "count": len(confs),
            "avg_conf": (sum(confs) / len(confs)) if confs else 0.0,
        }
        for cls, confs in det_conf.items()
    }

    # Human feedback accuracy
    fb_coll = get_collection("feedback")
    fb_cursor = fb_coll.find({"timestamp": time_filter})
    total_fb = 0
    correct_fb = 0
    for doc in fb_cursor:
        total_fb += 1
        if doc.get("correct"):
            correct_fb += 1
    fb_accuracy = (correct_fb / total_fb) if total_fb else None

    # Movement cluster count
    cluster_coll = get_collection("movement_clusters")
    cluster_count = cluster_coll.count_documents({"timestamp": time_filter})

    return {
        "detections": det_summary,
        "feedback_accuracy": fb_accuracy,
        "cluster_count": cluster_count,
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run meta analysis over logged data")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None
    report = meta_analysis(args.hours, start=start, end=end)
    print(json.dumps(report, indent=2, default=float))
