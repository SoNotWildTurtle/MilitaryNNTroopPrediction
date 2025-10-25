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


def _render_command_directives(directives: Optional[Dict[str, Any]]) -> None:
    if not directives:
        return

    console.print(_t("Command directives"), style="bold")

    status = str(directives.get("status", "monitor"))
    severity = directives.get("severity")
    status_label = status.replace("_", " ").title()
    status_line = f"{_t('Status')}: {status_label}"
    if isinstance(severity, (int, float)):
        status_line += f" ({_t('Severity')}: {int(severity)})"
    console.print(status_line)

    window = directives.get("planning_window_hours")
    if isinstance(window, (float, int)):
        console.print(f"{_t('Planning window (hrs)')}: {float(window):.2f}")

    teams = directives.get("coordination_teams", [])
    if teams:
        console.print(_t("Coordination teams:"), style="bold")
        for team in teams:
            console.print(f"- {team}")

    focus = directives.get("focus_areas", [])
    if focus:
        console.print(_t("Focus areas:"), style="bold")
        for area in focus:
            console.print(f"- {area}")

    drivers = directives.get("drivers", [])
    if drivers:
        console.print(_t("Drivers:"), style="bold")
        for driver in drivers:
            console.print(f"- {driver}")

    counts = directives.get("directive_counts", {})
    if counts:
        console.print(_t("Directive mix:"), style="bold")
        for key, label in (
            ("immediate", _t("Immediate")),
            ("next_shift", _t("Next shift")),
            ("monitor", _t("Monitor")),
        ):
            if counts.get(key):
                console.print(f"- {label}: {counts[key]}")

    queue = directives.get("directives", [])
    if queue:
        table = Table(title=_t("Directive queue"))
        table.add_column(_t("Priority"))
        table.add_column(_t("Action"))
        table.add_column(_t("Source"))
        table.add_column(_t("Context"))
        table.add_column(_t("Window (hrs)"), justify="right")

        for entry in queue:
            priority = str(entry.get("priority", "monitor"))
            label = {
                "immediate": _t("Immediate"),
                "next_shift": _t("Next shift"),
                "monitor": _t("Monitor"),
            }.get(priority, priority.replace("_", " ").title())
            window_value = entry.get("window_hours")
            table.add_row(
                label,
                str(entry.get("action", "-")),
                str(entry.get("source", "-")),
                str(entry.get("context", "-")) if entry.get("context") else "-",
                f"{float(window_value):.2f}" if isinstance(window_value, (float, int)) else "-",
            )

        console.print(table)


def _render_command_alignment(alignment: Optional[Dict[str, Any]]) -> None:
    if not alignment:
        return

    console.print(_t("Command alignment"), style="bold")

    status = str(alignment.get("status", "aligned"))
    score = alignment.get("alignment_score")
    status_line = f"{_t('Status')}: {status.replace('_', ' ').title()}"
    if isinstance(score, (int, float)):
        status_line += f" ({_t('Score')}: {int(round(float(score)))})"
    console.print(status_line)

    next_sync = alignment.get("next_sync_hours")
    if isinstance(next_sync, (int, float)):
        console.print(
            f"{_t('Next sync window')}: {round(float(next_sync), 2)} {_t('hours')}"
        )

    if alignment.get("coordination_gaps"):
        console.print(_t("Coordination gaps:"), style="bold red")
        for gap in alignment["coordination_gaps"]:
            console.print(f"- {gap}")

    if alignment.get("focus_areas"):
        console.print(_t("Focus areas:"), style="bold")
        for area in alignment["focus_areas"]:
            console.print(f"- {area}")

    if alignment.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in alignment["drivers"]:
            console.print(f"- {driver}")

    if alignment.get("recommended_actions"):
        console.print(_t("Alignment actions:"), style="bold")
        for action in alignment["recommended_actions"]:
            console.print(f"- {action}")


def _render_mission_assurance(assurance: Optional[Dict[str, Any]]) -> None:
    if not assurance:
        return

    console.print(_t("Mission assurance"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    table.add_row(_t("Status"), str(assurance.get("status", _t("unknown"))).replace("_", " ").title())
    score = assurance.get("assurance_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Assurance score"), str(int(round(float(score)))))
    checkpoint = assurance.get("next_checkpoint_hours")
    if isinstance(checkpoint, (float, int)):
        table.add_row(_t("Next checkpoint"), f"{float(checkpoint):.2f}h")
    blockers = assurance.get("blockers")
    if isinstance(blockers, list) and blockers:
        table.add_row(_t("Blockers"), str(len(blockers)))

    console.print(table)

    if blockers:
        console.print(_t("Blockers:"), style="bold red")
        for blocker in blockers:
            console.print(f"- {blocker}", style="red")

    focus = assurance.get("focus_areas")
    if isinstance(focus, list) and focus:
        console.print(_t("Focus areas:"), style="bold")
        for area in focus:
            console.print(f"- {area}")

    if assurance.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in assurance["drivers"]:
            console.print(f"- {driver}")

    deps = assurance.get("dependency_windows")
    if isinstance(deps, list) and deps:
        dep_table = Table(title=_t("Dependency windows"))
        dep_table.add_column(_t("Dependency"))
        dep_table.add_column(_t("Window (h)"), justify="right")
        for entry in deps:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "-"))
            window = entry.get("window_hours")
            dep_table.add_row(
                name,
                f"{float(window):.2f}" if isinstance(window, (float, int)) else "-",
            )
        console.print(dep_table)

    if assurance.get("recommended_actions"):
        console.print(_t("Assurance actions:"), style="bold")
        for action in assurance["recommended_actions"]:
            console.print(f"- {action}")


def _render_operational_resilience(resilience: Optional[Dict[str, Any]]) -> None:
    if not resilience:
        return

    console.print(_t("Operational resilience"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(resilience.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = resilience.get("resilience_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Resilience score"), str(int(round(float(score)))))

    window = resilience.get("stability_window_hours")
    if isinstance(window, (float, int)):
        table.add_row(_t("Stability window"), f"{float(window):.2f}h")

    reinforcements = resilience.get("reinforcing_factors")
    if isinstance(reinforcements, list) and reinforcements:
        table.add_row(_t("Reinforcements"), str(len(reinforcements)))

    weak = resilience.get("weak_spots")
    if isinstance(weak, list) and weak:
        table.add_row(_t("Weak spots"), str(len(weak)))

    console.print(table)

    if isinstance(reinforcements, list) and reinforcements:
        console.print(_t("Reinforcing factors:"), style="bold")
        for item in reinforcements:
            console.print(f"- {item}")

    if isinstance(weak, list) and weak:
        console.print(_t("Weak spots:"), style="bold red")
        for item in weak:
            console.print(f"- {item}", style="red")

    if resilience.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in resilience["drivers"]:
            console.print(f"- {driver}")

    if resilience.get("recommended_actions"):
        console.print(_t("Resilience actions:"), style="bold")
        for action in resilience["recommended_actions"]:
            console.print(f"- {action}")


def _render_operational_continuity(continuity: Optional[Dict[str, Any]]) -> None:
    if not continuity:
        return

    console.print(_t("Operational continuity"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(continuity.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = continuity.get("continuity_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Continuity score"), str(int(round(float(score)))))

    horizon = continuity.get("continuity_horizon_hours")
    if isinstance(horizon, (float, int)):
        table.add_row(_t("Continuity horizon"), f"{float(horizon):.2f}h")

    constraints = continuity.get("primary_constraints")
    if isinstance(constraints, list) and constraints:
        table.add_row(_t("Primary constraints"), str(len(constraints)))

    risks = continuity.get("continuity_risks")
    if isinstance(risks, list) and risks:
        table.add_row(_t("Continuity risks"), str(len(risks)))

    stability = continuity.get("stability_factors")
    if isinstance(stability, list) and stability:
        table.add_row(_t("Stability factors"), str(len(stability)))

    console.print(table)

    if isinstance(constraints, list) and constraints:
        console.print(_t("Constraints:"), style="bold red")
        for item in constraints:
            console.print(f"- {item}", style="red")

    if isinstance(risks, list) and risks:
        risk_table = Table(title=_t("Continuity risks"))
        risk_table.add_column(_t("Name"))
        risk_table.add_column(_t("Severity"))
        risk_table.add_column(_t("Detail"))
        for entry in risks:
            if not isinstance(entry, dict):
                continue
            risk_table.add_row(
                str(entry.get("name", "-")),
                str(entry.get("severity", _t("unknown"))).title(),
                str(entry.get("detail", "")),
            )
        console.print(risk_table)

    if isinstance(stability, list) and stability:
        console.print(_t("Stability factors:"), style="bold")
        for item in stability:
            console.print(f"- {item}")

    if continuity.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in continuity["drivers"]:
            console.print(f"- {driver}")

    watch_items = continuity.get("watch_items")
    if isinstance(watch_items, list) and watch_items:
        console.print(_t("Watch items:"), style="bold yellow")
        for item in watch_items:
            console.print(f"- {item}", style="yellow")

    if continuity.get("recommended_actions"):
        console.print(_t("Continuity actions:"), style="bold")
        for action in continuity["recommended_actions"]:
            console.print(f"- {action}")


def _render_escalation_readiness(matrix: Optional[Dict[str, Any]]) -> None:
    if not matrix:
        return

    console.print(_t("Escalation readiness"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(matrix.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = matrix.get("readiness_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Readiness score"), str(int(round(float(score)))))

    review = matrix.get("next_review_hours")
    if isinstance(review, (int, float)):
        table.add_row(_t("Next review"), f"{float(review):.2f}h")

    pathways = matrix.get("escalation_pathways")
    if isinstance(pathways, list) and pathways:
        table.add_row(_t("Pathways"), str(len(pathways)))

    signals = matrix.get("escalation_signals")
    if isinstance(signals, list) and signals:
        table.add_row(_t("Signals"), str(len(signals)))

    stability = matrix.get("stability_factors")
    if isinstance(stability, list) and stability:
        table.add_row(_t("Stability factors"), str(len(stability)))

    console.print(table)

    if isinstance(pathways, list) and pathways:
        pathway_table = Table(title=_t("Escalation pathways"))
        pathway_table.add_column(_t("Name"))
        pathway_table.add_column(_t("Priority"))
        pathway_table.add_column(_t("Triggers"))
        pathway_table.add_column(_t("Actions"))
        for entry in pathways:
            if not isinstance(entry, dict):
                continue
            triggers = "; ".join(entry.get("triggers", [])) if entry.get("triggers") else "-"
            actions = "; ".join(entry.get("actions", [])) if entry.get("actions") else "-"
            priority = str(entry.get("priority", "monitor")).replace("_", " ").title()
            pathway_table.add_row(
                str(entry.get("name", "-")),
                priority,
                triggers,
                actions,
            )
        console.print(pathway_table)

    if isinstance(signals, list) and signals:
        console.print(_t("Escalation signals:"), style="bold red")
        for signal in signals:
            console.print(f"- {signal}", style="red")

    if isinstance(stability, list) and stability:
        console.print(_t("Stability factors:"), style="bold")
        for factor in stability:
            console.print(f"- {factor}")

    drivers = matrix.get("drivers")
    if isinstance(drivers, list) and drivers:
        console.print(_t("Drivers:"), style="bold")
        for driver in drivers:
            console.print(f"- {driver}")

    watch_items = matrix.get("watch_items")
    if isinstance(watch_items, list) and watch_items:
        console.print(_t("Watch items:"), style="bold yellow")
        for item in watch_items:
            console.print(f"- {item}", style="yellow")

    actions = matrix.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Escalation actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_operational_recovery(plan: Optional[Dict[str, Any]]) -> None:
    if not plan:
        return

    console.print(_t("Operational recovery"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(plan.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = plan.get("recovery_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Recovery score"), str(int(round(float(score)))))

    phase = plan.get("recovery_phase")
    if phase:
        table.add_row(_t("Phase"), str(phase).title())

    dependencies = plan.get("critical_dependencies")
    if isinstance(dependencies, list) and dependencies:
        table.add_row(_t("Critical dependencies"), str(len(dependencies)))

    tracks = plan.get("recovery_tracks")
    if isinstance(tracks, list) and tracks:
        table.add_row(_t("Recovery tracks"), str(len(tracks)))

    window = plan.get("recovery_window_hours")
    if isinstance(window, (int, float)):
        table.add_row(_t("Recovery window"), f"{float(window):.2f}h")

    momentum = plan.get("momentum_factors")
    if isinstance(momentum, list) and momentum:
        table.add_row(_t("Momentum factors"), str(len(momentum)))

    console.print(table)

    if isinstance(dependencies, list) and dependencies:
        console.print(_t("Critical dependencies:"), style="bold red")
        for item in dependencies:
            console.print(f"- {item}", style="red")

    if isinstance(tracks, list) and tracks:
        track_table = Table(title=_t("Recovery tracks"))
        track_table.add_column(_t("Name"))
        track_table.add_column(_t("Status"))
        track_table.add_column(_t("Owner"))
        track_table.add_column(_t("Focus"))
        track_table.add_column(_t("Key actions"))
        for entry in tracks:
            if not isinstance(entry, dict):
                continue
            actions = entry.get("actions")
            action_text = "; ".join(actions) if isinstance(actions, list) and actions else "-"
            track_table.add_row(
                str(entry.get("name", "-")),
                str(entry.get("status", _t("unknown"))).replace("_", " ").title(),
                str(entry.get("owner", "-")),
                str(entry.get("focus", "-")),
                action_text,
            )
        console.print(track_table)

    stabilisation_actions = plan.get("stabilisation_actions")
    if isinstance(stabilisation_actions, list) and stabilisation_actions:
        console.print(_t("Stabilisation actions:"), style="bold")
        for action in stabilisation_actions:
            console.print(f"- {action}")

    recommended = plan.get("recommended_actions")
    if isinstance(recommended, list) and recommended:
        console.print(_t("Recovery actions:"), style="bold")
        for action in recommended:
            console.print(f"- {action}")

    drivers = plan.get("insight_drivers")
    if isinstance(drivers, list) and drivers:
        console.print(_t("Drivers:"), style="bold")
        for driver in drivers:
            console.print(f"- {driver}")

    momentum = plan.get("momentum_factors")
    if isinstance(momentum, list) and momentum:
        console.print(_t("Momentum factors:"), style="bold green")
        for item in momentum:
            console.print(f"- {item}", style="green")

    watch_items = plan.get("watch_items")
    if isinstance(watch_items, list) and watch_items:
        console.print(_t("Watch items:"), style="bold yellow")
        for item in watch_items:
            console.print(f"- {item}", style="yellow")


def _render_operational_transformation(plan: Optional[Dict[str, Any]]) -> None:
    if not plan:
        return

    console.print(_t("Operational transformation"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(plan.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = plan.get("transformation_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Transformation score"), str(int(round(float(score)))))

    stage = plan.get("maturity_stage")
    if stage:
        table.add_row(_t("Maturity stage"), str(stage).replace("_", " ").title())

    review = plan.get("next_review_hours")
    if isinstance(review, (int, float)):
        table.add_row(_t("Next review"), f"{float(review):.2f}h")

    quick_wins = plan.get("quick_wins")
    if isinstance(quick_wins, list) and quick_wins:
        table.add_row(_t("Quick wins"), str(len(quick_wins)))

    initiatives = plan.get("long_horizon_initiatives")
    if isinstance(initiatives, list) and initiatives:
        table.add_row(_t("Long-horizon initiatives"), str(len(initiatives)))

    console.print(table)

    tracks = plan.get("focus_tracks")
    if isinstance(tracks, list) and tracks:
        track_table = Table(title=_t("Focus tracks"))
        track_table.add_column(_t("Track"))
        track_table.add_column(_t("Status"))
        track_table.add_column(_t("Owner"))
        track_table.add_column(_t("Focus"))
        track_table.add_column(_t("Actions"))
        for entry in tracks:
            if not isinstance(entry, dict):
                continue
            actions = entry.get("actions")
            action_text = "; ".join(actions) if isinstance(actions, list) and actions else "-"
            track_table.add_row(
                str(entry.get("name", "-")),
                str(entry.get("status", "-")),
                str(entry.get("owner", "-")),
                str(entry.get("focus", "-")),
                action_text,
            )
        console.print(track_table)

    def _render_list(title: str, values: Optional[List[Any]], *, style: str = "bold") -> None:
        if not isinstance(values, list) or not values:
            return
        console.print(_t(title), style=style)
        for item in values:
            if style == "bold":
                console.print(f"- {item}")
            else:
                console.print(f"- {item}", style=style)

    _render_list("Quick wins:", plan.get("quick_wins"))
    _render_list("Long-horizon initiatives:", plan.get("long_horizon_initiatives"))
    _render_list("Enablers:", plan.get("enablers"))
    _render_list("Constraints:", plan.get("constraints"), style="yellow")
    _render_list("Watch indicators:", plan.get("watch_indicators"), style="yellow")
    _render_list("Metrics to watch:", plan.get("metrics_to_watch"))
    _render_list("Transformation focus:", plan.get("transformation_focus"))

    actions = plan.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Transformation actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_operational_governance(governance: Optional[Dict[str, Any]]) -> None:
    if not governance:
        return

    console.print(_t("Operational governance"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(governance.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = governance.get("governance_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Governance score"), str(int(round(float(score)))))

    review = governance.get("next_review_hours")
    if isinstance(review, (int, float)):
        table.add_row(_t("Next review"), f"{float(review):.2f}h")

    gaps = governance.get("compliance_gaps")
    if isinstance(gaps, list) and gaps:
        table.add_row(_t("Compliance gaps"), str(len(gaps)))

    councils = governance.get("oversight_councils")
    if isinstance(councils, list) and councils:
        table.add_row(_t("Oversight councils"), str(len(councils)))

    console.print(table)

    if isinstance(councils, list) and councils:
        council_table = Table(title=_t("Oversight councils"))
        council_table.add_column(_t("Council"))
        council_table.add_column(_t("Status"))
        council_table.add_column(_t("Focus"))
        council_table.add_column(_t("Next review"))
        council_table.add_column(_t("Actions"))
        for council in councils:
            if not isinstance(council, dict):
                continue
            review_value = council.get("next_review_hours")
            review_text = (
                f"{float(review_value):.2f}h"
                if isinstance(review_value, (int, float))
                else "-"
            )
            actions = council.get("actions")
            action_text = "; ".join(actions) if isinstance(actions, list) and actions else "-"
            council_table.add_row(
                str(council.get("name", "-")),
                str(council.get("status", "-")),
                str(council.get("focus", "-")),
                review_text,
                action_text,
            )
        console.print(council_table)

    def _render_list(title: str, values: Optional[List[Any]], *, style: str = "bold") -> None:
        if not isinstance(values, list) or not values:
            return
        console.print(_t(title), style=style)
        for item in values:
            if style == "bold":
                console.print(f"- {item}")
            else:
                console.print(f"- {item}", style=style)

    _render_list("Compliance gaps:", gaps, style="yellow")
    _render_list("Oversight focus:", governance.get("oversight_focus"))
    _render_list("Drivers:", governance.get("drivers"))
    _render_list("Watch items:", governance.get("watch_items"), style="yellow")
    _render_list("Governance metrics:", governance.get("governance_metrics"))

    actions = governance.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Governance actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_contingency_plans(plan: Optional[Dict[str, Any]]) -> None:
    if not plan:
        return

    console.print(_t("Contingency planning"), style="bold")

    status = str(plan.get("status", "observe"))
    severity = plan.get("severity")
    line = f"{_t('Status')}: {status.replace('_', ' ').title()}"
    if isinstance(severity, (int, float)):
        line += f" ({_t('Severity')}: {int(severity)})"
    window = plan.get("activation_window_hours")
    if isinstance(window, (int, float)):
        line += f" • {_t('Activation window')}: {float(window):.2f} {_t('hours')}"
    console.print(line)

    scenarios = plan.get("scenarios", []) if isinstance(plan, dict) else []
    if scenarios:
        table = Table(title=_t("Contingency scenarios"))
        table.add_column(_t("Scenario"))
        table.add_column(_t("Objective"))
        table.add_column(_t("Confidence"))
        table.add_column(_t("Owners"))
        table.add_column(_t("Triggers"))
        for entry in scenarios:
            owners = ", ".join(entry.get("owners", [])) if entry.get("owners") else "-"
            triggers = "; ".join(entry.get("triggers", [])) if entry.get("triggers") else "-"
            table.add_row(
                str(entry.get("name", "-")),
                str(entry.get("objective", "-")),
                str(entry.get("confidence", "-")),
                owners,
                triggers,
            )
        console.print(table)

    if plan.get("watch_items"):
        console.print(_t("Watch items:"), style="bold")
        for item in plan["watch_items"]:
            console.print(f"- {item}")

    if plan.get("recommended_actions"):
        console.print(_t("Contingency actions:"), style="bold")
        for action in plan["recommended_actions"]:
            console.print(f"- {action}")


def _render_resource_sustainment(plan: Optional[Dict[str, Any]]) -> None:
    if not plan:
        return

    console.print(_t("Resource sustainment"), style="bold")

    status = str(plan.get("status", "balanced"))
    severity = plan.get("severity")
    line = f"{_t('Status')}: {status.replace('_', ' ').title()}"
    if isinstance(severity, (int, float)):
        line += f" ({_t('Severity')}: {int(severity)})"
    window = plan.get("resupply_window_hours")
    if isinstance(window, (int, float)):
        line += f" • {_t('Resupply window')}: {float(window):.1f} {_t('hours')}"
    console.print(line)

    needs = plan.get("resource_needs")
    if isinstance(needs, list) and needs:
        console.print(_t("Resource needs:"), style="bold")
        for need in needs:
            console.print(f"- {need}")

    allocation = plan.get("allocation_plan")
    if isinstance(allocation, list) and allocation:
        table = Table(title=_t("Allocation plan"))
        table.add_column(_t("Resource"))
        table.add_column(_t("Priority"))
        table.add_column(_t("Focus"))
        table.add_column(_t("Quantity"), justify="right")
        table.add_column(_t("Window (hr)"), justify="right")
        for entry in allocation:
            quantity = entry.get("quantity")
            window_value = entry.get("window_hours")
            table.add_row(
                str(entry.get("resource", "-")),
                str(entry.get("priority", "-")),
                str(entry.get("focus", "-")),
                str(int(quantity)) if isinstance(quantity, (int, float)) else "-",
                f"{float(window_value):.1f}" if isinstance(window_value, (int, float)) else "-",
            )
        console.print(table)

    if plan.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in plan["drivers"]:
            console.print(f"- {driver}")

    if plan.get("recommended_actions"):
        console.print(_t("Sustainment actions:"), style="bold")
        for action in plan["recommended_actions"]:
            console.print(f"- {action}")


def _render_frontline_support(payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        return

    console.print(_t("Frontline support posture"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(payload.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = payload.get("support_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Support score"), str(int(round(float(score)))))

    window = payload.get("coordination_window_hours")
    if isinstance(window, (int, float)):
        table.add_row(
            _t("Coordination window"),
            f"{float(window):.2f} {_t('hours')}",
        )

    units = payload.get("priority_units")
    if isinstance(units, list) and units:
        table.add_row(_t("Priority units"), str(len(units)))

    corridors = payload.get("support_corridors")
    if isinstance(corridors, list) and corridors:
        table.add_row(_t("Support corridors"), str(len(corridors)))

    console.print(table)

    if isinstance(units, list) and units:
        console.print(_t("Priority units:"), style="bold")
        for unit in units:
            console.print(f"- {unit}")

    if isinstance(corridors, list) and corridors:
        console.print(_t("Support corridors:"), style="bold")
        for corridor in corridors:
            console.print(f"- {corridor}")

    brigade_support = payload.get("brigade_support")
    if isinstance(brigade_support, list) and brigade_support:
        support_table = Table(title=_t("Brigade support"))
        support_table.add_column(_t("Unit"))
        support_table.add_column(_t("Resource"))
        support_table.add_column(_t("Priority"))
        support_table.add_column(_t("Window (hr)"), justify="right")
        support_table.add_column(_t("Quantity"), justify="right")
        for entry in brigade_support:
            if not isinstance(entry, dict):
                continue
            window_hours = entry.get("window_hours")
            quantity = entry.get("quantity")
            support_table.add_row(
                str(entry.get("unit", "-")),
                str(entry.get("resource", "-")),
                str(entry.get("priority", "-")),
                f"{float(window_hours):.1f}" if isinstance(window_hours, (int, float)) else "-",
                str(int(quantity)) if isinstance(quantity, (int, float)) else "-",
            )
        console.print(support_table)

    signals = payload.get("signals")
    if isinstance(signals, list) and signals:
        console.print(_t("Signals:"), style="bold")
        for signal in signals:
            console.print(f"- {signal}")

    drivers = payload.get("drivers")
    if isinstance(drivers, list) and drivers:
        console.print(_t("Drivers:"), style="bold")
        for driver in drivers:
            console.print(f"- {driver}")

    operator_notes = payload.get("ukrainian_operator_notes")
    if isinstance(operator_notes, list) and operator_notes:
        console.print(_t("Notes for Ukrainian operators:"), style="bold blue")
        for note in operator_notes:
            console.print(f"- {note}", style="blue")

    actions = payload.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Frontline actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_automation_playbook(payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        return

    console.print(_t("Automation playbook"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(payload.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = payload.get("automation_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Automation score"), f"{float(score):.1f}")

    window = payload.get("automation_window_hours")
    if isinstance(window, (int, float)):
        table.add_row(
            _t("Automation window"),
            f"{float(window):.2f} {_t('hours')}",
        )

    task_count = payload.get("automation_tasks")
    if isinstance(task_count, list) and task_count:
        table.add_row(_t("Automation tasks"), str(len(task_count)))

    console.print(table)

    tasks = payload.get("automation_tasks")
    if isinstance(tasks, list) and tasks:
        tasks_table = Table(title=_t("Automation tasks"))
        tasks_table.add_column(_t("Task"))
        tasks_table.add_column(_t("Mode"))
        tasks_table.add_column(_t("Owner"))
        tasks_table.add_column(_t("Window (hr)"), justify="right")
        for entry in tasks:
            if not isinstance(entry, dict):
                continue
            window_hours = entry.get("window_hours")
            tasks_table.add_row(
                str(entry.get("task", "-")),
                str(entry.get("mode", "-")),
                str(entry.get("owner", "-")) if entry.get("owner") else "-",
                f"{float(window_hours):.2f}" if isinstance(window_hours, (int, float)) else "-",
            )
        console.print(tasks_table)

    for label, key in [
        (_t("Drivers:"), "drivers"),
        (_t("Blockers:"), "blockers"),
        (_t("Triggers:"), "triggers"),
        (_t("Automation tracks:"), "automation_tracks"),
        (_t("Monitoring channels:"), "monitoring_channels"),
    ]:
        values = payload.get(key)
        if isinstance(values, list) and values:
            console.print(label, style="bold")
            for value in values:
                console.print(f"- {value}")

    prompts = payload.get("ukrainian_operator_prompts")
    if isinstance(prompts, list) and prompts:
        console.print(
            _t("Prompts for Ukrainian operators:"),
            style="bold blue",
        )
        for prompt in prompts:
            console.print(f"- {prompt}", style="blue")

    actions = payload.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Automation actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_automation_guardrails(payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        return

    console.print(_t("Automation guardrails"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(payload.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = payload.get("autonomy_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Autonomy score"), f"{float(score):.1f}")

    review = payload.get("next_review_hours")
    if isinstance(review, (int, float)):
        table.add_row(_t("Next review"), f"{float(review):.2f} {_t('hours')}")

    guardrails = payload.get("guardrails")
    if isinstance(guardrails, list) and guardrails:
        table.add_row(_t("Guardrail count"), str(len(guardrails)))

    console.print(table)

    if isinstance(guardrails, list) and guardrails:
        console.print(_t("Guardrails:"), style="bold")
        for item in guardrails:
            console.print(f"- {item}")

    safety_checks = payload.get("safety_checks")
    if isinstance(safety_checks, list) and safety_checks:
        console.print(_t("Safety checks:"), style="bold")
        for check in safety_checks:
            console.print(f"- {check}")

    overrides = payload.get("operator_overrides")
    if isinstance(overrides, list) and overrides:
        console.print(_t("Operator overrides:"), style="bold")
        for override in overrides:
            console.print(f"- {override}")

    monitoring = payload.get("monitoring_channels")
    if isinstance(monitoring, list) and monitoring:
        console.print(_t("Monitoring channels:"), style="bold")
        for channel in monitoring:
            console.print(f"- {channel}")

    focus = payload.get("oversight_focus")
    if isinstance(focus, list) and focus:
        console.print(_t("Oversight focus:"), style="bold")
        for item in focus:
            console.print(f"- {item}")

    candidates = payload.get("automation_candidates")
    if isinstance(candidates, list) and candidates:
        console.print(_t("Automation candidates:"), style="bold")
        for entry in candidates:
            console.print(f"- {entry}")

    checklist = payload.get("ukrainian_checklist")
    if isinstance(checklist, list) and checklist:
        console.print(_t("Checklist for Ukrainian operators:"), style="bold blue")
        for item in checklist:
            console.print(f"- {item}", style="blue")

    actions = payload.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Automation guardrail actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_automation_mission_control(payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        return

    console.print(_t("Automation mission control"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(payload.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    supervision = payload.get("supervision_level")
    if supervision:
        table.add_row(
            _t("Supervision level"), str(supervision).replace("_", " ").title()
        )

    automation_mode = payload.get("automation_mode")
    if automation_mode:
        table.add_row(
            _t("Automation mode"), str(automation_mode).replace("_", " ").title()
        )

    guardrail_status = payload.get("guardrail_status")
    if guardrail_status:
        table.add_row(
            _t("Guardrail status"), str(guardrail_status).replace("_", " ").title()
        )

    score = payload.get("mission_control_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Mission control score"), f"{float(score):.1f}")

    severity = payload.get("severity_index")
    if isinstance(severity, (int, float)):
        table.add_row(_t("Severity index"), str(int(severity)))

    next_sync = payload.get("next_sync_hours")
    if isinstance(next_sync, (int, float)):
        table.add_row(_t("Next sync"), f"{float(next_sync):.2f} {_t('hours')}")

    console.print(table)

    for label, key in [
        (_t("Control focus:"), "control_focus"),
        (_t("Mission channels:"), "mission_channels"),
        (_t("Automation tracks:"), "automation_tracks"),
        (_t("Critical guardrails:"), "critical_guardrails"),
        (_t("Handoff requirements:"), "handoff_requirements"),
        (_t("Supervisor actions:"), "supervisor_actions"),
        (_t("Watch items:"), "watch_items"),
    ]:
        values = payload.get(key)
        if isinstance(values, list) and values:
            console.print(label, style="bold")
            for value in values:
                console.print(f"- {value}")

    prompts = payload.get("ukrainian_operator_prompts")
    if isinstance(prompts, list) and prompts:
        console.print(
            _t("Prompts for Ukrainian mission control:"),
            style="bold blue",
        )
        for prompt in prompts:
            console.print(f"- {prompt}", style="blue")

    actions = payload.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Mission control actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_automation_autonomy(payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        return

    console.print(_t("Automation autonomy posture"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(payload.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = payload.get("autonomy_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Autonomy score"), f"{float(score):.1f}")

    severity = payload.get("severity_index")
    if isinstance(severity, (int, float)):
        table.add_row(_t("Severity index"), str(int(severity)))

    supervision = payload.get("supervision_requirements")
    if supervision:
        table.add_row(_t("Supervision"), str(supervision))

    mode = payload.get("operational_mode")
    if mode:
        table.add_row(_t("Automation mode"), str(mode).replace("_", " ").title())

    mission_status = payload.get("mission_control_status")
    if mission_status:
        table.add_row(
            _t("Mission control"), str(mission_status).replace("_", " ").title()
        )

    window = payload.get("autonomy_window_hours")
    if isinstance(window, (int, float)):
        table.add_row(_t("Autonomy window"), f"{float(window):.2f} {_t('hours')}")

    console.print(table)

    for label, key in [
        (_t("Autonomy enablers:"), "autonomy_enablers"),
        (_t("Risk factors:"), "risk_factors"),
        (_t("Trusted automation tasks:"), "trusted_tasks"),
        (_t("Restricted automation tasks:"), "restricted_tasks"),
        (_t("Automation tracks:"), "automation_tracks"),
        (_t("Monitoring requirements:"), "monitoring_requirements"),
        (_t("Fallback protocols:"), "fallback_protocols"),
        (_t("Watch items:"), "watch_items"),
    ]:
        values = payload.get(key)
        if isinstance(values, list) and values:
            console.print(label, style="bold")
            for value in values:
                console.print(f"- {value}")

    safeguards = payload.get("ukrainian_safeguards")
    if isinstance(safeguards, list) and safeguards:
        console.print(_t("Safeguards for Ukrainian operators:"), style="bold blue")
        for safeguard in safeguards:
            console.print(f"- {safeguard}", style="blue")

    actions = payload.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Autonomy actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_automation_failsafes(payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        return

    console.print(_t("Automation failsafes"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(payload.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = payload.get("failsafe_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Failsafe score"), f"{float(score):.1f}")

    window = payload.get("failsafe_window_hours")
    if isinstance(window, (int, float)):
        table.add_row(_t("Failsafe window"), f"{float(window):.2f} {_t('hours')}")

    console.print(table)

    for label, key in [
        (_t("Failsafe measures:"), "failsafe_measures"),
        (_t("Fallback channels:"), "fallback_channels"),
        (_t("Recovery steps:"), "recovery_steps"),
        (_t("Failsafe tests:"), "failsafe_tests"),
        (_t("Coverage gaps:"), "coverage_gaps"),
        (_t("Watch items:"), "watch_items"),
    ]:
        values = payload.get(key)
        if isinstance(values, list) and values:
            console.print(label, style="bold")
            for value in values:
                console.print(f"- {value}")

    prompts = payload.get("ukrainian_operator_prompts")
    if isinstance(prompts, list) and prompts:
        console.print(_t("Prompts for Ukrainian operators:"), style="bold blue")
        for prompt in prompts:
            console.print(f"- {prompt}", style="blue")

    actions = payload.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Failsafe actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_automation_validation(payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        return

    console.print(_t("Automation validation"), style="bold")

    table = Table(show_header=False)
    table.add_column(_t("Metric"))
    table.add_column(_t("Value"))

    status = str(payload.get("status", _t("unknown"))).replace("_", " ").title()
    table.add_row(_t("Status"), status)

    score = payload.get("validation_score")
    if isinstance(score, (int, float)):
        table.add_row(_t("Validation score"), f"{float(score):.1f}")

    window = payload.get("validation_window_hours")
    if isinstance(window, (int, float)):
        table.add_row(_t("Validation window"), f"{float(window):.2f} {_t('hours')}")

    console.print(table)

    for label, key in [
        (_t("Validation tracks:"), "validation_tracks"),
        (_t("Test matrix:"), "test_matrix"),
        (_t("Training requirements:"), "training_requirements"),
        (_t("Validation evidence:"), "validation_evidence"),
        (_t("Watch items:"), "watch_items"),
    ]:
        values = payload.get(key)
        if isinstance(values, list) and values:
            console.print(label, style="bold")
            for value in values:
                console.print(f"- {value}")

    prompts = payload.get("ukrainian_operator_prompts")
    if isinstance(prompts, list) and prompts:
        console.print(_t("Prompts for Ukrainian operators:"), style="bold blue")
        for prompt in prompts:
            console.print(f"- {prompt}", style="blue")

    actions = payload.get("recommended_actions")
    if isinstance(actions, list) and actions:
        console.print(_t("Validation actions:"), style="bold")
        for action in actions:
            console.print(f"- {action}")


def _render_operational_risks(register: Optional[Dict[str, Any]]) -> None:
    if not register:
        return

    console.print(_t("Operational risk register"), style="bold")

    status = str(register.get("status", "stable"))
    severity = register.get("severity_score")
    risk_count = register.get("risk_count")
    line = f"{_t('Status')}: {status.replace('_', ' ').title()}"
    if isinstance(severity, (int, float)):
        line += f" • {_t('Severity score')}: {int(severity)}"
    if isinstance(risk_count, (int, float)):
        line += f" • {_t('Tracked risks')}: {int(risk_count)}"
    next_review = register.get("next_review_hours")
    if isinstance(next_review, (int, float)):
        line += f" • {_t('Next review in')}: {float(next_review):.1f} {_t('hours')}"
    console.print(line)

    focus = register.get("focus_areas")
    if isinstance(focus, list) and focus:
        console.print(_t("Focus areas:"), style="bold")
        for entry in focus:
            console.print(f"- {entry}")

    risks = register.get("risks")
    if isinstance(risks, list) and risks:
        table = Table(title=_t("Risk detail"))
        table.add_column(_t("Risk"))
        table.add_column(_t("Category"))
        table.add_column(_t("Severity"), justify="right")
        table.add_column(_t("Status"))
        table.add_column(_t("Detail"))
        table.add_column(_t("Review (hr)"), justify="right")
        for entry in risks:
            severity_value = entry.get("severity")
            review = entry.get("review_window_hours")
            table.add_row(
                str(entry.get("name", "-")),
                str(entry.get("category", "-")) if entry.get("category") else "-",
                str(int(severity_value)) if isinstance(severity_value, (int, float)) else "-",
                str(entry.get("status", "-")),
                str(entry.get("detail", "-")) if entry.get("detail") else "-",
                f"{float(review):.1f}" if isinstance(review, (int, float)) else "-",
            )
        console.print(table)

    if register.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in register["drivers"]:
            console.print(f"- {driver}")

    if register.get("recommended_actions"):
        console.print(_t("Risk actions:"), style="bold")
        for action in register["recommended_actions"]:
            console.print(f"- {action}")


def _render_communication_plan(plan: Optional[Dict[str, Any]]) -> None:
    if not plan:
        return

    console.print(_t("Communication plan"), style="bold")

    status = str(plan.get("status", "routine"))
    cadence = plan.get("update_cadence_minutes")
    status_line = f"{_t('Status')}: {status.replace('_', ' ').title()}"
    if isinstance(cadence, (int, float)):
        status_line += f" ({_t('Cadence')}: {int(cadence)} {_t('minutes')})"
    console.print(status_line)

    audiences = plan.get("audiences", []) if isinstance(plan, dict) else []
    if audiences:
        table = Table(title=_t("Audience cadence"))
        table.add_column(_t("Audience"))
        table.add_column(_t("Cadence (min)"), justify="right")
        table.add_column(_t("Focus"))
        table.add_column(_t("Channel"))
        for entry in audiences:
            cadence_value = entry.get("cadence_minutes")
            table.add_row(
                str(entry.get("audience", "-")),
                str(int(cadence_value)) if isinstance(cadence_value, (int, float)) else "-",
                str(entry.get("focus", "-")),
                str(entry.get("channel", "-")) if entry.get("channel") else "-",
            )
        console.print(table)

    if plan.get("key_messages"):
        console.print(_t("Key messages:"), style="bold")
        for msg in plan["key_messages"]:
            console.print(f"- {msg}")

    if plan.get("drivers"):
        console.print(_t("Drivers:"), style="bold")
        for driver in plan["drivers"]:
            console.print(f"- {driver}")

    if plan.get("recommended_actions"):
        console.print(_t("Communication actions:"), style="bold")
        for action in plan["recommended_actions"]:
            console.print(f"- {action}")


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
    if brief.get("command_directives"):
        _render_command_directives(brief["command_directives"])
    if brief.get("command_alignment"):
        _render_command_alignment(brief["command_alignment"])
    if brief.get("mission_assurance"):
        _render_mission_assurance(brief["mission_assurance"])
    if brief.get("operational_resilience"):
        _render_operational_resilience(brief["operational_resilience"])
    if brief.get("operational_continuity"):
        _render_operational_continuity(brief["operational_continuity"])
    if brief.get("escalation_readiness"):
        _render_escalation_readiness(brief["escalation_readiness"])
    if brief.get("operational_recovery"):
        _render_operational_recovery(brief["operational_recovery"])
    if brief.get("operational_transformation"):
        _render_operational_transformation(brief["operational_transformation"])
    if brief.get("operational_governance"):
        _render_operational_governance(brief["operational_governance"])
    if brief.get("contingency_plans"):
        _render_contingency_plans(brief["contingency_plans"])
    if brief.get("communication_plan"):
        _render_communication_plan(brief["communication_plan"])
    if brief.get("resource_sustainment"):
        _render_resource_sustainment(brief["resource_sustainment"])
    if brief.get("frontline_support"):
        _render_frontline_support(brief["frontline_support"])
    if brief.get("automation_playbook"):
        _render_automation_playbook(brief["automation_playbook"])
    if brief.get("automation_guardrails"):
        _render_automation_guardrails(brief["automation_guardrails"])
    if brief.get("automation_mission_control"):
        _render_automation_mission_control(brief["automation_mission_control"])
    if brief.get("automation_autonomy"):
        _render_automation_autonomy(brief["automation_autonomy"])
    if brief.get("automation_failsafes"):
        _render_automation_failsafes(brief["automation_failsafes"])

    if brief.get("automation_validation"):
        _render_automation_validation(brief["automation_validation"])
    if brief.get("operational_risks"):
        _render_operational_risks(brief["operational_risks"])
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
