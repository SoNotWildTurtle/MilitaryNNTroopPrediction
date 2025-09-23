"""Combine multiple analysis routines to highlight shared alerts."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from .anomaly_detector import detect_anomalies
from .burst_detector import detect_bursts
from .change_point import change_points
from .detection_volatility import detection_volatility
from .detection_streaks import detection_streaks
from .interarrival import interarrival_times

AnalysisFunction = Callable[..., List[Dict[str, Any]]]
AnalysisSpec = Tuple[str, str, AnalysisFunction, Dict[str, Any]]


def _default_specs(
    hours: int,
    baseline_days: int,
    bucket_minutes: int,
    change_days: int,
    volatility_days: int,
    streak_days: int,
    interarrival_days: int,
    z_thresh: float,
) -> Iterable[AnalysisSpec]:
    """Return the default set of analysis specifications."""

    return (
        (
            "anomaly",
            "Anomaly detection",
            detect_anomalies,
            {"hours": hours, "baseline_days": baseline_days, "z_thresh": z_thresh},
        ),
        (
            "burst",
            "Burst spikes",
            detect_bursts,
            {"hours": hours, "bucket_minutes": bucket_minutes, "z_thresh": z_thresh},
        ),
        (
            "change",
            "Change points",
            change_points,
            {"days": change_days, "z_thresh": z_thresh},
        ),
        (
            "volatility",
            "Volatility",
            detection_volatility,
            {"days": volatility_days},
        ),
        (
            "streak",
            "Detection streaks",
            detection_streaks,
            {"days": streak_days},
        ),
        (
            "interarrival",
            "Interarrival gaps",
            interarrival_times,
            {"days": interarrival_days},
        ),
    )


def analysis_method_cohesion(
    hours: int = 24,
    baseline_days: int = 7,
    bucket_minutes: int = 60,
    change_days: int = 30,
    volatility_days: int = 30,
    streak_days: int = 30,
    interarrival_days: int = 30,
    z_thresh: float = 2.0,
    min_methods: int = 2,
    method_specs: Sequence[AnalysisSpec] | None = None,
    extra_specs: Sequence[AnalysisSpec] | None = None,
) -> Dict[str, Any]:
    """Run several analysis pipelines and report where they agree.

    Parameters
    ----------
    hours:
        Lookback window in hours for time-based routines (anomaly, burst).
    baseline_days:
        Number of days used as a baseline for anomaly detection.
    bucket_minutes:
        Bucket size for burst detection.
    change_days:
        Lookback window in days for change-point detection.
    volatility_days:
        Lookback window in days for volatility computation.
    streak_days:
        Lookback window in days when computing detection streaks.
    interarrival_days:
        Lookback window in days when computing interarrival gaps.
    z_thresh:
        Z-score threshold shared by anomaly, burst, and change-point analyses.
    min_methods:
        Minimum number of agreeing analysis methods required for a class to
        appear in the summary.
    method_specs:
        Optional custom analysis specifications to run instead of the defaults.
        Each specification is a tuple ``(key, label, func, kwargs)``.
    extra_specs:
        Additional specifications that should be appended to the defaults or
        ``method_specs`` when provided.

    Returns
    -------
    dict
        ``{"summary": [...], "methods": [...], "overlap": {...}}`` where
        ``summary`` contains classes flagged by ``min_methods`` or more
        routines, ``methods`` enumerates individual analysis outputs, and
        ``overlap`` is a matrix counting method intersections. Each summary
        entry stores a mapping of method keys to the list of result records that
        produced the hit.
    """

    min_methods = max(1, int(min_methods))
    if method_specs is None:
        specs = list(
            _default_specs(
                hours,
                baseline_days,
                bucket_minutes,
                change_days,
                volatility_days,
                streak_days,
                interarrival_days,
                z_thresh,
            )
        )
    else:
        specs = list(method_specs)
    if extra_specs:
        specs.extend(extra_specs)

    normalized_specs: List[AnalysisSpec] = []
    key_counts: Dict[str, int] = {}
    for key, label, func, kwargs in specs:
        count = key_counts.get(key, 0)
        key_counts[key] = count + 1
        if count:
            suffix = count + 1
            new_key = f"{key}_{suffix}"
            new_label = f"{label} #{suffix}"
        else:
            new_key = key
            new_label = label
        normalized_specs.append((new_key, new_label, func, kwargs))

    specs = normalized_specs

    method_records: List[Dict[str, Any]] = []
    class_hits: Dict[str, Dict[str, Any]] = {}

    for key, label, func, kwargs in specs:
        try:
            results = func(**kwargs)
            error = None
        except Exception as exc:  # pragma: no cover - defensive guardrail
            results = []
            error = str(exc)
        method_records.append(
            {
                "key": key,
                "label": label,
                "results": results,
                "error": error,
                "count": len(results),
            }
        )
        if error:
            continue
        for entry in results:
            cls = entry.get("class")
            if not cls:
                continue
            info = class_hits.setdefault(
                cls, {"methods": set(), "details": {}},
            )
            info["methods"].add(key)
            info["details"].setdefault(key, []).append(entry)

    summary: List[Dict[str, Any]] = []
    for cls, info in class_hits.items():
        methods = sorted(info["methods"])
        if len(methods) < min_methods:
            continue
        summary.append(
            {
                "class": cls,
                "hit_count": len(methods),
                "methods": methods,
                "details": info["details"],
            }
        )
    summary.sort(key=lambda item: (-item["hit_count"], item["class"]))

    keys = [record["key"] for record in method_records]
    overlap: Dict[str, Dict[str, int]] = {k: {j: 0 for j in keys} for k in keys}
    for info in class_hits.values():
        methods = list(info["methods"])
        for i in methods:
            for j in methods:
                overlap[i][j] += 1

    return {
        "summary": summary,
        "methods": method_records,
        "overlap": overlap,
    }


__all__ = ["analysis_method_cohesion"]
