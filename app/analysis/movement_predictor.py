"""Predict future positions from recent movement points."""

from typing import List, Dict, Tuple, Any
from datetime import datetime
import math
import numpy as np


EARTH_RADIUS_M = 6_371_000


def _degree_scales(lat: float) -> Tuple[float, float]:
    """Return approximate metres per degree for latitude and longitude."""

    lat_scale = 2 * math.pi * EARTH_RADIUS_M / 360.0
    lon_scale = lat_scale * math.cos(math.radians(lat))
    return lat_scale, max(lon_scale, 1.0)


def _as_datetime(value, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return fallback
    return fallback


def _evaluate_surety(
    times: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    residuals_m: np.ndarray,
    speed_mps: float,
) -> Tuple[float, List[Dict[str, Any]]]:
    """Return a surety score (0-1) and supporting check details."""

    checks: List[Dict[str, Any]] = []
    scores: List[float] = []

    def record(name: str, score: float, detail: str) -> None:
        score_clamped = float(max(0.0, min(score, 1.0)))
        checks.append({"check": name, "score": round(score_clamped, 3), "detail": detail})
        scores.append(score_clamped)

    point_count = len(times)
    if point_count <= 1:
        record("history_points", 0.0, "Only one timestamp available; prediction unreliable.")
        return 0.0, checks

    count_score = min((point_count - 1) / 4.0, 1.0)
    record("history_points", count_score, f"{point_count} positions provided.")

    duration = float(times[-1] - times[0])
    duration_score = 0.0 if duration <= 0 else min(duration / 600.0, 1.0)
    record("history_span", duration_score, f"History covers {duration:.1f} seconds.")

    gaps = np.diff(times)
    valid_gaps = gaps[gaps > 0]
    if valid_gaps.size:
        max_gap = float(valid_gaps.max())
        gap_score = 1.0 if max_gap <= 120 else max(0.0, 1.0 - (max_gap - 120.0) / 600.0)
        record("timestamp_gaps", gap_score, f"Largest gap is {max_gap:.1f} seconds.")
    else:
        record("timestamp_gaps", 0.2, "Timestamps are identical; treated as low surety.")

    residual_rms = float(np.sqrt(np.mean(residuals_m ** 2))) if residuals_m.size else 0.0
    residual_score = max(0.0, 1.0 - min(residual_rms / 500.0, 1.0))
    record("trajectory_fit", residual_score, f"Trajectory RMSE is {residual_rms:.1f} m.")

    if valid_gaps.size:
        lat_mid = (lats[:-1] + lats[1:]) / 2.0
        scales = np.array([_degree_scales(float(lat)) for lat in lat_mid])
        lat_scales = scales[:, 0]
        lon_scales = scales[:, 1]
        delta_lat = np.diff(lats)
        delta_lon = np.diff(lons)
        meters_lat = delta_lat * lat_scales
        meters_lon = delta_lon * lon_scales
        speeds = np.sqrt(meters_lat ** 2 + meters_lon ** 2) / valid_gaps
        if speeds.size:
            mean_speed = float(np.mean(speeds))
            std_speed = float(np.std(speeds))
            ratio = std_speed / (mean_speed + 1e-6)
            speed_consistency = max(0.0, 1.0 - min(ratio, 3.0) / 3.0)
            record(
                "speed_consistency",
                speed_consistency,
                f"Mean speed {mean_speed:.1f} m/s with std {std_speed:.1f} m/s.",
            )

            headings = np.degrees(np.arctan2(meters_lon, meters_lat))
            if headings.size > 1:
                heading_delta = np.diff(headings)
                heading_delta = (heading_delta + 180.0) % 360.0 - 180.0
                mean_turn = float(np.mean(np.abs(heading_delta)))
                direction_score = max(0.0, 1.0 - min(mean_turn, 180.0) / 180.0)
                record(
                    "direction_stability",
                    direction_score,
                    f"Mean heading change {mean_turn:.1f}°.",
                )
            else:
                record("direction_stability", 0.8, "Only one segment; direction assumed stable.")
        else:
            record("speed_consistency", 0.2, "Unable to compute speeds (zero deltas).")
            record("direction_stability", 0.2, "Unable to compute headings (zero deltas).")
    else:
        record("speed_consistency", 0.1, "Timestamp gaps missing; speeds not evaluated.")
        record("direction_stability", 0.1, "Timestamp gaps missing; headings not evaluated.")

    # Penalise extremely high speeds that likely indicate noisy data
    speed_limit = 60.0  # ~216 km/h, above typical ground unit speeds
    if speed_mps <= speed_limit:
        limit_score = 1.0
        detail = f"Predicted speed {speed_mps:.1f} m/s within typical range."
    else:
        excess = speed_mps - speed_limit
        limit_score = max(0.0, 1.0 - min(excess / 80.0, 1.0))
        detail = f"Predicted speed {speed_mps:.1f} m/s exceeds ground threshold."
    record("speed_plausibility", limit_score, detail)

    surety_score = float(np.mean(scores)) if scores else 0.0
    return surety_score, checks


def predict_next_position(positions: List[Dict], dt_seconds: float = 60.0) -> Dict[str, Any]:
    """Predict next lat/lon with regression-based velocity and confidence metrics.

    Parameters
    ----------
    positions: list of dict
        Each dict should contain ``lat``, ``lon`` and ``timestamp`` (datetime).
    dt_seconds: float
        Seconds ahead to predict.
    """

    if len(positions) < 2:
        print("Need at least two positions for prediction")
        return {}

    pts = sorted(positions, key=lambda p: p.get("timestamp", datetime.utcnow()))

    base_time = _as_datetime(pts[0].get("timestamp"), datetime.utcnow())
    times = np.array([
        max((_as_datetime(p.get("timestamp"), base_time) - base_time).total_seconds(), 0.0)
        for p in pts
    ])

    lats = np.array([p["lat"] for p in pts], dtype=float)
    lons = np.array([p["lon"] for p in pts], dtype=float)

    if np.all(times == times[0]):
        # Fall back to simple two-point extrapolation
        last, prev = pts[-1], pts[-2]
        t_last = (last.get("timestamp") or base_time)
        t_prev = (prev.get("timestamp") or base_time)
        dt = max((t_last - t_prev).total_seconds(), 1e-6)
        v_lat = (last["lat"] - prev["lat"]) / dt
        v_lon = (last["lon"] - prev["lon"]) / dt
        lat_scale, lon_scale = _degree_scales(last["lat"])
        speed_mps = float(math.sqrt((v_lat * lat_scale) ** 2 + (v_lon * lon_scale) ** 2))
        span_score = min(dt / 600.0, 1.0)
        surety_checks = [
            {
                "check": "history_points",
                "score": 0.5,
                "detail": "Only two positions available; used simple extrapolation.",
            },
            {
                "check": "history_span",
                "score": span_score,
                "detail": f"History span {dt:.1f} seconds.",
            },
        ]
        surety_score = float(np.mean([c["score"] for c in surety_checks]))
        base_conf = 0.6
        combined_conf = float(max(0.0, min(base_conf * surety_score, 1.0)))
        return {
            "lat": last["lat"] + v_lat * dt_seconds,
            "lon": last["lon"] + v_lon * dt_seconds,
            "speed_mps": speed_mps,
            "confidence": combined_conf,
            "radius_m": 500.0,
            "surety": {
                "base_confidence": base_conf,
                "surety_score": surety_score,
                "checks": surety_checks,
            },
        }

    lat_coeff = np.polyfit(times, lats, 1)
    lon_coeff = np.polyfit(times, lons, 1)

    t_future = times[-1] + dt_seconds
    lat_pred = float(np.polyval(lat_coeff, t_future))
    lon_pred = float(np.polyval(lon_coeff, t_future))

    lat_fit = np.polyval(lat_coeff, times)
    lon_fit = np.polyval(lon_coeff, times)

    lat_scale, lon_scale = _degree_scales(lats[-1])
    residuals_m = np.sqrt(((lats - lat_fit) * lat_scale) ** 2 + ((lons - lon_fit) * lon_scale) ** 2)
    rmse_m = float(np.sqrt(np.mean(residuals_m ** 2)))

    speed_lat = lat_coeff[0] * lat_scale
    speed_lon = lon_coeff[0] * lon_scale
    speed_mps = float(math.hypot(speed_lat, speed_lon))

    # Convert RMSE into a baseline confidence score (higher RMSE -> lower confidence)
    base_confidence = float(np.exp(-rmse_m / 300.0))  # ~0.72 at 100 m error, ~0.37 at 300 m
    radius_m = float(max(rmse_m * 1.96, 50.0))

    surety_score, surety_checks = _evaluate_surety(times, lats, lons, residuals_m, speed_mps)
    combined_confidence = float(max(0.0, min(base_confidence * max(surety_score, 1e-3), 1.0)))

    return {
        "lat": lat_pred,
        "lon": lon_pred,
        "speed_mps": speed_mps,
        "confidence": combined_confidence,
        "radius_m": radius_m,
        "surety": {
            "base_confidence": base_confidence,
            "surety_score": surety_score,
            "checks": surety_checks,
        },
    }


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Predict next position from JSON list")
    p.add_argument("positions", help="JSON array of {'lat','lon','timestamp'}")
    p.add_argument("--dt", type=float, default=60.0, help="Seconds ahead to predict")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        import json
        pts = json.loads(args.positions)
        for p in pts:
            ts = p.get("timestamp")
            if isinstance(ts, str):
                p["timestamp"] = datetime.fromisoformat(ts)
    except Exception as e:
        print(f"Failed to parse positions: {e}")
        return
    pred = predict_next_position(pts, args.dt)
    if pred:
        print(pred)


if __name__ == "__main__":
    main()
