"""Capture video frames from a drone and run detection."""

from pathlib import Path
from typing import Optional

import cv2

from ..detection import (
    ground_troop,
    load_troop_classifier,
    classify_troop,
    classify_drone,
    classify_vehicle,
)
from ..analysis import fuse_confidences
from ..models import trajectory_model
from ..pipeline import realtime
from ..utils import image_utils


def stream(
    source: int | str,
    model_path: Optional[str] = None,
    area: str = "unknown",
    troop_model_path: Optional[str] = None,
    classify_drones: bool = False,
    classify_vehicles: bool = False,
) -> None:
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video source: {source}")

    model = trajectory_model.load_model(model_path) if model_path else None
    troop_clf = load_troop_classifier(troop_model_path) if troop_model_path else None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        tmp_path = Path("frame.jpg")
        cv2.imwrite(str(tmp_path), frame)
        tmp_path = image_utils.enhance_image(tmp_path)
        detections = ground_troop.detect_ground_troops(tmp_path)
        for det in detections:
            det["det_conf"] = det.pop("confidence", 0.0)

        if troop_clf:
            for det in detections:
                det.update(classify_troop(tmp_path, troop_clf))

        if classify_drones:
            for det in detections:
                res = classify_drone(tmp_path)
                det.update({"drone_type": res["drone_type"], "drone_conf": res["confidence"]})

        if classify_vehicles:
            for det in detections:
                res = classify_vehicle(tmp_path)
                det.update({"vehicle_type": res["vehicle_type"], "vehicle_conf": res["confidence"]})

        fuse_confidences(detections)

        realtime.store_detections(area, detections)

        if model and detections:
            coords = [[d.get("lat"), d.get("lon")] for d in detections if "lat" in d and "lon" in d]
            if coords:
                import tensorflow as tf

                sequence = tf.expand_dims(tf.constant(coords, dtype=tf.float32), 0)
                pred = model(sequence, training=False)[0, -1]
                realtime.store_prediction(area, pred)

        cv2.imshow("drone", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Stream drone feed and run detection")
    parser.add_argument("source", help="Camera index or video path")
    parser.add_argument("--model", dest="model", help="Trajectory model path", default=None)
    parser.add_argument("--troop-model", dest="troop_model", help="Troop classifier path", default=None)
    parser.add_argument("--area", default="unknown", help="Area identifier")
    parser.add_argument("--classify-drones", action="store_true", help="Identify drone type")
    parser.add_argument("--classify-vehicles", action="store_true", help="Identify vehicle type")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    stream(
        args.source,
        model_path=args.model,
        area=args.area,
        troop_model_path=args.troop_model,
        classify_drones=args.classify_drones,
        classify_vehicles=args.classify_vehicles,
    )


if __name__ == "__main__":
    main()
