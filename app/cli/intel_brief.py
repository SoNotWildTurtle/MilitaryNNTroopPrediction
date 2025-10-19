"""CLI to render a consolidated intelligence brief."""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from ..analysis.intel_brief import gather_intelligence_brief
from ..config import settings
from ..translation import translate_text

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate static UI text when localisation is enabled."""
    return translate_text(text, target_lang=_LANG)


def _render_detection_summary(meta: Dict[str, Any]) -> None:
    detections = meta.get("detections") if meta else None
    if not detections:
        console.print(_t("No detection statistics available."), style="yellow")
        return
    table = Table(title=_t("Detection overview"))
    table.add_column(_t("Class"))
    table.add_column(_t("Count"), justify="right")
    table.add_column(_t("Avg confidence"), justify="right")
    for cls, stats in sorted(detections.items(), key=lambda item: item[0]):
        count = stats.get("count", 0)
        avg_conf = stats.get("avg_conf", 0.0)
        table.add_row(cls, str(count), f"{avg_conf:.2f}")
    console.print(table)


def _render_detection_quality(quality: Optional[Dict[str, Any]]) -> None:
    if not quality:
        return

    console.print(_t("Detection quality"), style="bold")
    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    table.add_row(
        _t("Total detections"),
        str(quality.get("total_detections", 0)),
    )
    table.add_row(
        _t("Active classes"),
        str(quality.get("active_classes", 0)),
    )

    weighted = quality.get("weighted_avg_confidence")
    table.add_row(
        _t("Weighted confidence"),
        f"{float(weighted):.3f}" if isinstance(weighted, (float, int)) else "-",
    )

    ratio = quality.get("active_class_ratio")
    table.add_row(
        _t("Active class ratio"),
        f"{float(ratio):.3f}" if isinstance(ratio, (float, int)) else "-",
    )

    console.print(table)

    if quality.get("low_confidence_classes"):
        console.print(_t("Low confidence classes:"), style="bold")
        for cls in quality["low_confidence_classes"]:
            console.print(f"- {cls}", style="yellow")

    if quality.get("sparse_class_coverage"):
        console.print(_t("Sparse coverage classes:"), style="bold")
        for cls in quality["sparse_class_coverage"]:
            console.print(f"- {cls}")

    if quality.get("notes"):
        console.print(_t("Quality notes:"), style="bold")
        for note in quality["notes"]:
            console.print(f"- {note}")


def _render_cluster_threats(threats: Optional[Any]) -> None:
    if not threats:
        console.print(_t("No clusters scored within the selected window."), style="yellow")
        return
    table = Table(title=_t("Cluster threat levels"))
    table.add_column(_t("Label"))
    table.add_column(_t("Threat level"))
    table.add_column(_t("Score"), justify="right")
    table.add_column(_t("Nearest site"))
    table.add_column(_t("ETA (min)"), justify="right")
    for idx, cluster in enumerate(threats, start=1):
        label = str(cluster.get("label", idx))
        table.add_row(
            label,
            str(cluster.get("threat_level", _t("unknown"))),
            f"{cluster.get('threat_score', 0.0):.2f}",
            str(cluster.get("nearest_site", "-")),
            f"{cluster.get('eta_minutes', 0.0):.1f}" if cluster.get("eta_minutes") else "-",
        )
    console.print(table)


def _render_activity(activity: Dict[str, Any]) -> None:
    detections = activity.get("detections", [])
    predictions = activity.get("predictions", [])
    console.print(_t("Recent detections:"), style="bold")
    if detections:
        console.print_json(data=json.dumps(detections, default=str))
    else:
        console.print(_t("No detections returned."), style="yellow")
    console.print()
    console.print(_t("Recent predictions:"), style="bold")
    if predictions:
        console.print_json(data=json.dumps(predictions, default=str))
    else:
        console.print(_t("No predictions returned."), style="yellow")


def _render_activity_summary(summary: Optional[Dict[str, Any]]) -> None:
    if not summary:
        return

    table = Table(title=_t("Operational tempo"))
    table.add_column(_t("Detections"), justify="right")
    table.add_column(_t("Predictions"), justify="right")
    table.add_column(_t("Tempo"))
    table.add_column(_t("Coverage"), justify="right")
    table.add_column(_t("Detections/hr"), justify="right")
    coverage = summary.get("prediction_coverage")
    detection_rate = summary.get("detection_rate_per_hour")
    table.add_row(
        str(summary.get("detections", 0)),
        str(summary.get("predictions", 0)),
        str(summary.get("tempo", _t("unknown"))),
        f"{coverage:.2f}" if isinstance(coverage, (float, int)) else "-",
        f"{detection_rate:.2f}" if isinstance(detection_rate, (float, int)) else "-",
    )
    console.print(table)
    for note in summary.get("notes", []):
        console.print(f"- {note}", style="yellow")


def _render_data_freshness(freshness: Optional[Dict[str, Any]]) -> None:
    if not freshness:
        return

    feeds = freshness.get("feeds", {})
    if not feeds:
        return

    table = Table(title=_t("Data freshness"))
    table.add_column(_t("Feed"))
    table.add_column(_t("Status"))
    table.add_column(_t("Age (min)"), justify="right")
    table.add_column(_t("Latest timestamp"))

    for feed_name, info in feeds.items():
        status = str(info.get("status", _t("unknown")))
        age = info.get("age_minutes")
        timestamp = info.get("latest_timestamp", "-")
        table.add_row(
            feed_name,
            status,
            f"{age:.2f}" if isinstance(age, (float, int)) else "-",
            timestamp,
        )

    console.print(table)

    stalest_feed = freshness.get("stalest_feed")
    if stalest_feed:
        worst_case = freshness.get("worst_case_minutes")
        console.print(
            _t(
                f"Stalest feed: {stalest_feed} (age {worst_case:.1f} minutes)"
                if isinstance(worst_case, (float, int))
                else f"Stalest feed: {stalest_feed}"
            ),
            style="yellow",
        )


def _render_health(health: Optional[Dict[str, Any]]) -> None:
    if not health:
        return

    console.print(_t("Brief health assessment"), style="bold")

    summary = health.get("summary")
    if summary:
        console.print(summary, style="cyan")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))
    table.add_row(_t("Risk level"), str(health.get("risk_level", _t("unknown"))))
    table.add_row(_t("Confidence"), str(health.get("confidence", _t("unknown"))))
    if health.get("highest_threat_level"):
        table.add_row(
            _t("Highest threat"),
            str(health.get("highest_threat_level", _t("unknown"))),
        )
    console.print(table)

    if health.get("drivers"):
        console.print(_t("Key drivers:"), style="bold")
        for driver in health["drivers"]:
            console.print(f"- {driver}")

    if health.get("recommended_actions"):
        console.print(_t("Health actions:"), style="bold")
        for action in health["recommended_actions"]:
            console.print(f"- {action}")


def _render_operational_posture(posture: Optional[Dict[str, Any]]) -> None:
    if not posture:
        return

    console.print(_t("Operational posture"), style="bold")
    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))
    table.add_row(_t("Status"), str(posture.get("status", _t("unknown"))))
    table.add_row(_t("Focus"), str(posture.get("focus", _t("unknown"))))
    horizon = posture.get("horizon_hours")
    table.add_row(
        _t("Planning horizon"),
        f"{float(horizon):.1f}h" if isinstance(horizon, (float, int)) else "-",
    )
    table.add_row(_t("Confidence"), str(posture.get("confidence", _t("unknown"))))
    console.print(table)

    if posture.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in posture["drivers"]:
            console.print(f"- {driver}")


def _render_response_readiness(readiness: Optional[Dict[str, Any]]) -> None:
    if not readiness:
        return

    console.print(_t("Response readiness"), style="bold")
    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))
    table.add_row(_t("Level"), str(readiness.get("level", _t("unknown"))))
    staffing = readiness.get("recommended_staffing")
    table.add_row(
        _t("Recommended staffing"),
        str(int(staffing)) if isinstance(staffing, (float, int)) else "-",
    )
    window = readiness.get("support_window_hours")
    table.add_row(
        _t("Support window"),
        f"{float(window):.1f}h" if isinstance(window, (float, int)) else "-",
    )
    table.add_row(_t("Risk level"), str(readiness.get("risk_level", _t("unknown"))))
    if readiness.get("tempo"):
        table.add_row(_t("Tempo"), str(readiness.get("tempo")))
    console.print(table)

    if readiness.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in readiness["drivers"]:
            console.print(f"- {driver}")

    if readiness.get("priority_actions"):
        console.print(_t("Priority actions:"), style="bold")
        for action in readiness["priority_actions"]:
            console.print(f"- {action}")


def _render_response_pressure(pressure: Optional[Dict[str, Any]]) -> None:
    if not pressure:
        return

    console.print(_t("Analyst response pressure"), style="bold")
    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    table.add_row(_t("Status"), str(pressure.get("status", _t("unknown"))))
    table.add_row(
        _t("Pending predictions"),
        str(pressure.get("pending_predictions", 0)),
    )
    table.add_row(
        _t("Unmatched detections"),
        str(pressure.get("unmatched_detections", 0)),
    )

    ratio = pressure.get("inbox_ratio")
    table.add_row(
        _t("Inbox ratio"),
        f"{float(ratio):.2f}" if isinstance(ratio, (float, int)) else "-",
    )

    clearance = pressure.get("estimated_clearance_hours")
    table.add_row(
        _t("Clearance horizon"),
        f"{float(clearance):.1f}h" if isinstance(clearance, (float, int)) else "-",
    )

    console.print(table)

    if pressure.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in pressure["drivers"]:
            console.print(f"- {driver}")

    if pressure.get("recommended_actions"):
        console.print(_t("Recommended actions:"), style="bold")
        for action in pressure["recommended_actions"]:
            console.print(f"- {action}")


def _render_support_priorities(support: Optional[Dict[str, Any]]) -> None:
    if not support:
        return

    console.print(_t("Support priorities"), style="bold")

    summary = Table(show_header=False)
    summary.add_column(_t("Metric"))
    summary.add_column(_t("Value"))
    summary.add_row(_t("Status"), str(support.get("status", _t("unknown"))))

    severity = support.get("severity")
    if isinstance(severity, (int, float)):
        summary.add_row(_t("Severity"), str(int(severity)))

    teams = support.get("teams")
    if teams:
        summary.add_row(_t("Teams"), ", ".join(teams))

    console.print(summary)

    priority_rows = support.get("priorities") or []
    if priority_rows:
        table = Table(title=_t("Cross-team coordination queue"))
        table.add_column(_t("Team"))
        table.add_column(_t("Urgency"))
        table.add_column(_t("Reason"))
        table.add_column(_t("Window"), justify="right")
        for row in priority_rows:
            window = row.get("support_window_hours")
            table.add_row(
                str(row.get("team", "-")),
                str(row.get("urgency", "-")),
                str(row.get("reason", "-")),
                f"{float(window):.1f}h" if isinstance(window, (float, int)) else "-",
            )
        console.print(table)

    if support.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in support["drivers"]:
            console.print(f"- {driver}")

    if support.get("recommended_actions"):
        console.print(_t("Recommended actions:"), style="bold")
        for action in support["recommended_actions"]:
            console.print(f"- {action}")


def _render_intelligence_confidence(confidence: Optional[Dict[str, Any]]) -> None:
    if not confidence:
        return

    console.print(_t("Intelligence confidence"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    table.add_row(_t("Level"), str(confidence.get("level", _t("unknown"))))
    score = confidence.get("score")
    table.add_row(
        _t("Score"),
        f"{float(score):.1f}" if isinstance(score, (float, int)) else "-",
    )
    if confidence.get("status"):
        table.add_row(_t("Status"), str(confidence.get("status")))

    components = confidence.get("components") or {}
    if isinstance(components, dict):
        feedback = components.get("feedback_accuracy")
        if isinstance(feedback, (float, int)):
            table.add_row(_t("Feedback accuracy"), f"{feedback:.3f}")
        weighted = components.get("weighted_confidence")
        if isinstance(weighted, (float, int)):
            table.add_row(_t("Weighted confidence"), f"{weighted:.3f}")
        ratio = components.get("active_class_ratio")
        if isinstance(ratio, (float, int)):
            table.add_row(_t("Active class ratio"), f"{ratio:.3f}")
        telemetry = components.get("telemetry")
        if isinstance(telemetry, dict):
            stale = telemetry.get("stale_feeds")
            warn = telemetry.get("warning_feeds")
            tracked = telemetry.get("feeds_tracked")
            if tracked == 0:
                table.add_row(_t("Feeds tracked"), "0")
            if stale:
                table.add_row(
                    _t("Stale feeds"),
                    ", ".join(str(name) for name in stale),
                )
            if warn:
                table.add_row(
                    _t("Warning feeds"),
                    ", ".join(str(name) for name in warn),
                )
        gaps = components.get("gap_summary")
        if isinstance(gaps, dict):
            table.add_row(
                _t("Critical gaps"),
                str(gaps.get("critical", 0)),
            )
            table.add_row(
                _t("Major gaps"),
                str(gaps.get("major", 0)),
            )

    console.print(table)

    if confidence.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in confidence["drivers"]:
            console.print(f"- {driver}")

    if confidence.get("recommended_actions"):
        console.print(_t("Confidence actions:"), style="bold")
        for action in confidence["recommended_actions"]:
            console.print(f"- {action}")


def _render_operational_outlook(outlook: Optional[Dict[str, Any]]) -> None:
    if not outlook:
        return

    console.print(_t("Operational outlook"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    table.add_row(_t("Status"), str(outlook.get("status", _t("unknown"))))
    severity = outlook.get("severity_score")
    if isinstance(severity, (int, float)):
        table.add_row(_t("Severity score"), str(int(severity)))
    horizon = outlook.get("planning_horizon_hours")
    if isinstance(horizon, (float, int)):
        table.add_row(_t("Planning horizon"), f"{float(horizon):.1f}h")
    confidence_level = outlook.get("intelligence_confidence")
    if confidence_level:
        table.add_row(_t("Intelligence confidence"), str(confidence_level))
    dominant = outlook.get("dominant_threat_level")
    if dominant:
        table.add_row(_t("Dominant threat"), str(dominant))
    gap_summary = outlook.get("gap_summary")
    if isinstance(gap_summary, dict) and gap_summary:
        table.add_row(
            _t("Critical gaps"),
            str(gap_summary.get("critical", 0)),
        )
        table.add_row(
            _t("Major gaps"),
            str(gap_summary.get("major", 0)),
        )
    pending = outlook.get("pending_predictions")
    if isinstance(pending, (int, float)):
        table.add_row(_t("Pending predictions"), str(int(pending)))
    unmatched = outlook.get("unmatched_detections")
    if isinstance(unmatched, (int, float)):
        table.add_row(_t("Unmatched detections"), str(int(unmatched)))

    console.print(table)

    focus_areas = outlook.get("focus_areas")
    if isinstance(focus_areas, list) and focus_areas:
        console.print(_t("Focus areas:"), style="bold")
        for area in focus_areas:
            console.print(f"- {area}")

    if outlook.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in outlook["drivers"]:
            console.print(f"- {driver}")

    if outlook.get("recommended_actions"):
        console.print(_t("Outlook actions:"), style="bold")
        for action in outlook["recommended_actions"]:
            console.print(f"- {action}")


def _render_intelligence_gaps(gaps: Optional[List[Dict[str, Any]]]) -> None:
    if not gaps:
        return

    table = Table(title=_t("Intelligence gaps"))
    table.add_column(_t("Gap"))
    table.add_column(_t("Severity"))
    table.add_column(_t("Detail"))
    table.add_column(_t("Action"))

    for gap in gaps:
        action = gap.get("recommended_action")
        table.add_row(
            str(gap.get("gap", "-")),
            str(gap.get("severity", _t("unknown"))),
            str(gap.get("detail", "-")),
            action if action else "-",
        )

    console.print(table)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=_t("Generate an intelligence brief"))
    parser.add_argument("--area", type=str, help=_t("Optional area filter"))
    parser.add_argument("--hours", type=int, default=24, help=_t("Lookback window in hours"))
    parser.add_argument("--limit", type=int, default=20, help=_t("Maximum records per section"))
    parser.add_argument(
        "--raw", action="store_true", help=_t("Print the raw JSON payload instead of tables")
    )
    return parser


def main(area: Optional[str], hours: int, limit: int, raw: bool) -> None:
    try:
        brief = gather_intelligence_brief(area=area, hours=hours, activity_limit=limit)
    except ValueError as exc:
        console.print(f"{_t('Invalid parameters')}: {exc}", style="bold red")
        raise SystemExit(1) from exc
    if raw:
        console.print_json(data=json.dumps(brief, default=str))
        return

    console.print(_t("Intelligence brief"), style="bold underline")
    console.print(f"{_t('Generated at')}: {brief.get('generated_at')}")
    if brief.get("area"):
        console.print(f"{_t('Area')}: {brief['area']}")
    if brief.get("errors"):
        console.print(_t("Warnings:"), style="bold red")
        for err in brief["errors"]:
            console.print(f"- {err}", style="red")
    if brief.get("meta"):
        _render_detection_summary(brief["meta"])
    if brief.get("detection_quality"):
        _render_detection_quality(brief["detection_quality"])
    if brief.get("cluster_threats"):
        _render_cluster_threats(brief["cluster_threats"])
    if brief.get("recent_activity"):
        _render_activity(brief["recent_activity"])
    if brief.get("activity_summary"):
        _render_activity_summary(brief["activity_summary"])
    if brief.get("data_freshness"):
        _render_data_freshness(brief["data_freshness"])
    if brief.get("health"):
        _render_health(brief["health"])
    if brief.get("operational_posture"):
        _render_operational_posture(brief["operational_posture"])
    if brief.get("response_readiness"):
        _render_response_readiness(brief["response_readiness"])
    if brief.get("response_pressure"):
        _render_response_pressure(brief["response_pressure"])
    if brief.get("support_priorities"):
        _render_support_priorities(brief["support_priorities"])
    if brief.get("intelligence_confidence"):
        _render_intelligence_confidence(brief["intelligence_confidence"])
    if brief.get("operational_outlook"):
        _render_operational_outlook(brief["operational_outlook"])
    if brief.get("intelligence_gaps"):
        _render_intelligence_gaps(brief["intelligence_gaps"])
    if brief.get("insights"):
        console.print(_t("Key insights:"), style="bold")
        console.print_json(data=json.dumps(brief["insights"], default=str))
    if brief.get("recommendations"):
        console.print(_t("Recommendations:"), style="bold")
        for rec in brief["recommendations"]:
            console.print(f"- {rec}")


if __name__ == "__main__":
    args = _build_parser().parse_args()
    main(args.area, args.hours, args.limit, args.raw)
