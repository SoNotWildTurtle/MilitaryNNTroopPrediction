"""CLI to highlight overlap between multiple analysis methods."""

from __future__ import annotations

from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from ..analysis import analysis_method_cohesion
from ..config import settings
from ..translation import translate_text

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


_KEY_LABELS = {
    "recent_per_hr": "Recent/hr",
    "baseline_per_hr": "Baseline/hr",
    "count": "Count",
    "z": "z",
    "bucket_start": "Bucket",
    "change": "Change",
    "date": "Date",
    "avg": "Avg",
    "std": "Std",
    "max_streak": "Max streak",
    "avg_hours": "Avg hours",
    "median_hours": "Median hours",
}

_SUMMARY_FIELDS = {
    "anomaly": ("recent_per_hr", "z"),
    "burst": ("count", "z"),
    "change": ("change", "z"),
    "volatility": ("avg", "std"),
    "streak": ("max_streak",),
    "interarrival": ("avg_hours", "median_hours"),
}


def _fmt_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _base_method_key(method_key: str) -> str:
    return method_key.split("_", 1)[0]


def _summarize_single(method_key: str, detail: Dict[str, Any]) -> str:
    if not detail:
        return ""
    keys = _SUMMARY_FIELDS.get(_base_method_key(method_key), ())
    parts = []
    for key in keys:
        if key in detail:
            label = _t(_KEY_LABELS.get(key, key))
            parts.append(f"{label}={_fmt_value(detail[key])}")
    if not parts:
        for key, value in list(detail.items())[:2]:
            label = _t(_KEY_LABELS.get(key, key))
            parts.append(f"{label}={_fmt_value(value)}")
    return ", ".join(parts)


def _summarize_detail(method_key: str, detail: Any) -> str:
    if isinstance(detail, list):
        snippets = [
            text for text in (_summarize_single(method_key, item) for item in detail)
            if text
        ]
        if not snippets:
            return ""
        if len(snippets) > 3:
            remainder = len(snippets) - 3
            snippets = snippets[:3]
            snippets.append(
                _t("...and {count} more").format(count=remainder)
            )
        return "; ".join(snippets)
    if isinstance(detail, dict):
        return _summarize_single(method_key, detail)
    return ""


def run_method_cohesion_report() -> None:
    """Prompt for parameters and display cross-analysis consensus."""

    hours = int(Prompt.ask(_t("Lookback hours"), default="24"))
    baseline_days = int(Prompt.ask(_t("Baseline days"), default="7"))
    bucket_minutes = int(Prompt.ask(_t("Bucket minutes"), default="60"))
    change_days = int(Prompt.ask(_t("Change-point days"), default="30"))
    volatility_days = int(Prompt.ask(_t("Volatility days"), default="30"))
    z_thresh = float(Prompt.ask(_t("Z-score threshold"), default="2.0"))
    min_methods = int(Prompt.ask(_t("Minimum agreeing methods"), default="2"))

    result = analysis_method_cohesion(
        hours=hours,
        baseline_days=baseline_days,
        bucket_minutes=bucket_minutes,
        change_days=change_days,
        volatility_days=volatility_days,
        z_thresh=z_thresh,
        min_methods=min_methods,
    )

    methods = result["methods"]
    labels = {record["key"]: _t(record["label"]) for record in methods}

    overview = Table(title=_t("Method coverage"))
    overview.add_column(_t("Method"))
    overview.add_column(_t("Findings"), justify="right")
    overview.add_column(_t("Notes"))
    for record in methods:
        label = labels[record["key"]]
        note = ""
        if record.get("error"):
            note = _t("Error: {message}").format(message=record["error"])
        overview.add_row(label, str(record["count"]), note)
    console.print(overview)

    summary = result["summary"]
    if not summary:
        console.print(
            _t("No overlapping alerts found for the selected parameters."),
            style="green",
        )
    else:
        table = Table(title=_t("Cross-analysis consensus"))
        table.add_column(_t("Class"))
        table.add_column(_t("Hits"), justify="right")
        table.add_column(_t("Methods"))
        table.add_column(_t("Highlights"))
        for row in summary:
            methods_display = ", ".join(labels[m] for m in row["methods"])
            # TODO: Extend highlights with sensor reliability context and optional exports.
            highlights = "; ".join(
                filter(
                    None,
                    (
                        _summarize_detail(method_key, row["details"].get(method_key, {}))
                        for method_key in row["methods"]
                    ),
                )
            )
            table.add_row(
                row["class"],
                str(row["hit_count"]),
                methods_display,
                highlights or "-",
            )
        console.print(table)

    overlap = result.get("overlap", {})
    if overlap and methods:
        matrix = Table(title=_t("Method overlap"))
        matrix.add_column(_t("Method"))
        order = [record["key"] for record in methods]
        for key in order:
            matrix.add_column(labels[key], justify="right")
        for row_key in order:
            matrix.add_row(
                labels[row_key],
                *[str(overlap[row_key][col_key]) for col_key in order],
            )
        console.print(matrix)


if __name__ == "__main__":
    run_method_cohesion_report()
