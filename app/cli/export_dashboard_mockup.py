"""Export a static dashboard mockup backed by synthetic API examples."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from app.api.examples import sample_payload_bundle

DEFAULT_HTML_PATH = Path("dashboard-mockup.html")


def _record_count(payload: Mapping[str, Any], endpoint: str) -> int:
    records = payload.get("endpoints", {}).get(endpoint, [])
    return len(records) if isinstance(records, list) else 0


def _prediction_points(payload: Mapping[str, Any]) -> str:
    predictions = payload.get("endpoints", {}).get("GET /predictions/{area}?limit=10", [])
    if not predictions:
        return "No sample trajectory points available."
    first = predictions[0]
    trajectory = first.get("trajectory", {}) if isinstance(first, Mapping) else {}
    current = trajectory.get("current_point", "unknown")
    next_point = trajectory.get("next_point", "unknown")
    return f"{current} → {next_point}"


def _endpoint_cards(payload: Mapping[str, Any]) -> Iterable[str]:
    endpoints = payload.get("endpoints", {})
    for name, example in endpoints.items():
        pretty = html.escape(json.dumps(example, indent=2, sort_keys=True))
        yield f"""
        <section class=\"card endpoint-card\">
          <div class=\"endpoint-title\">{html.escape(name)}</div>
          <pre>{pretty}</pre>
        </section>
        """


def render_dashboard_html(payload: Dict[str, Any]) -> str:
    """Render a self-contained HTML dashboard mockup from example payloads."""

    metadata = payload.get("metadata", {})
    area = html.escape(str(metadata.get("area", "unknown-area")))
    description = html.escape(str(metadata.get("description", "Synthetic API examples.")))
    detection_count = _record_count(payload, "GET /detections/{area}?limit=10")
    prediction_count = _record_count(payload, "GET /predictions/{area}?limit=10")
    trajectory = html.escape(_prediction_points(payload))
    endpoint_markup = "\n".join(_endpoint_cards(payload))
    raw_json = html.escape(json.dumps(payload, indent=2, sort_keys=True))

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>MilitaryNNTroopPrediction Dashboard Mockup</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f172a;
      --panel: #111827;
      --panel-soft: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --ok: #22c55e;
      --warn: #f59e0b;
      --border: #334155;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at top left, #1e3a8a 0, var(--bg) 38rem);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 2rem; }}
    header {{ display: flex; flex-wrap: wrap; gap: 1rem; justify-content: space-between; align-items: flex-start; }}
    h1 {{ margin: 0 0 0.5rem; font-size: clamp(2rem, 4vw, 3.8rem); letter-spacing: -0.06em; }}
    p {{ color: var(--muted); line-height: 1.6; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 0.45rem 0.7rem;
      background: rgba(15, 23, 42, 0.72);
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .badge::before {{ content: ""; width: 0.55rem; height: 0.55rem; border-radius: 50%; background: var(--ok); }}
    .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin: 1.5rem 0; }}
    .card {{
      background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(15, 23, 42, 0.96));
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
      padding: 1.25rem;
    }}
    .metric {{ font-size: 2.4rem; font-weight: 800; letter-spacing: -0.04em; }}
    .label {{ color: var(--muted); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .route-list {{ display: grid; gap: 0.75rem; }}
    .route {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      border: 1px solid var(--border);
      border-radius: 0.9rem;
      padding: 0.85rem;
      background: rgba(31, 41, 55, 0.68);
    }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }}
    pre {{
      overflow: auto;
      max-height: 22rem;
      background: #020617;
      border: 1px solid var(--border);
      border-radius: 0.9rem;
      padding: 1rem;
      color: #d1d5db;
    }}
    .endpoint-title {{ color: var(--accent); font-weight: 700; margin-bottom: 0.75rem; }}
    details {{ margin-top: 1rem; }}
    summary {{ cursor: pointer; color: var(--accent); font-weight: 700; }}
    footer {{ margin-top: 2rem; color: var(--muted); font-size: 0.9rem; }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <span class=\"badge\">Static mockup · safe synthetic data</span>
        <h1>Analytical API dashboard preview</h1>
        <p>{description}</p>
      </div>
      <div class=\"card\">
        <div class=\"label\">Sample area</div>
        <div class=\"metric\" style=\"font-size: 1.4rem;\">{area}</div>
      </div>
    </header>

    <section class=\"grid\" aria-label=\"summary metrics\">
      <div class=\"card\"><div class=\"label\">Detections</div><div class=\"metric\">{detection_count}</div></div>
      <div class=\"card\"><div class=\"label\">Predictions</div><div class=\"metric\">{prediction_count}</div></div>
      <div class=\"card\"><div class=\"label\">Readiness</div><div class=\"metric\">OK</div></div>
      <div class=\"card\"><div class=\"label\">Example trajectory</div><p>{trajectory}</p></div>
    </section>

    <section class=\"card\">
      <h2>Recommended integration flow</h2>
      <div class=\"route-list\">
        <div class=\"route\"><code>GET /healthz</code><span>Confirm service is alive.</span></div>
        <div class=\"route\"><code>GET /readyz</code><span>Check config and optional Sentinel status.</span></div>
        <div class=\"route\"><code>GET /detections/&lt;area&gt;</code><span>Render recent detection records.</span></div>
        <div class=\"route\"><code>GET /predictions/&lt;area&gt;</code><span>Render movement prediction records.</span></div>
      </div>
    </section>

    <section class=\"grid\">
      {endpoint_markup}
    </section>

    <details class=\"card\">
      <summary>Raw synthetic example bundle</summary>
      <pre>{raw_json}</pre>
    </details>

    <footer>
      Generated from <code>app.api.examples.sample_payload_bundle()</code>. This file is for UI prototyping, documentation, and client development; it does not perform live collection, detection, or prediction.
    </footer>
  </main>
</body>
</html>
"""


def write_dashboard_html(payload: Dict[str, Any], path: Path) -> None:
    """Write the rendered dashboard HTML to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard_html(payload), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Export a self-contained dashboard mockup from synthetic API examples."
    )
    parser.add_argument(
        "--html-path",
        type=Path,
        default=DEFAULT_HTML_PATH,
        help=f"Path for HTML output. Default: {DEFAULT_HTML_PATH}",
    )
    return parser


def main() -> int:
    """CLI entry point."""

    args = build_parser().parse_args()
    payload = sample_payload_bundle()
    write_dashboard_html(payload, args.html_path)
    print(f"Wrote dashboard mockup to {args.html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
