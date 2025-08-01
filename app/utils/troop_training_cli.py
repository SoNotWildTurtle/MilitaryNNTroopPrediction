"""CLI to label troop images and train a simple classifier."""
from pathlib import Path
from typing import List, Dict, Optional
import csv
import tensorflow as tf
import numpy as np
from PIL import Image


def load_dataset(img_dir: Path, csv_path: Optional[Path] = None, troop_type: str = "", uniform: str = ""):
    """Load images and corresponding labels.

    Parameters
    ----------
    img_dir : Path
        Directory containing training images.
    csv_path : Optional[Path]
        CSV file with columns `filename`, `troop_type`, `uniform`.
    troop_type : str
        Single troop type to assign if CSV is not provided.
    uniform : str
        Uniform label used when CSV is not provided.
    """
    images: List[np.ndarray] = []
    labels: List[Dict[str, str]] = []

    if csv_path:
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            meta = {row["filename"]: row for row in reader}
    else:
        meta = None

    for img_path in sorted(img_dir.glob("*.jpg")):
        img = Image.open(img_path).convert("RGB").resize((128, 128))
        images.append(np.array(img) / 255.0)
        if meta and img_path.name in meta:
            labels.append({"troop_type": meta[img_path.name]["troop_type"], "uniform": meta[img_path.name]["uniform"]})
        else:
            labels.append({"troop_type": troop_type, "uniform": uniform})

    return np.stack(images), labels


def _encode_labels(labels: List[Dict[str, str]]):
    types = sorted({l["troop_type"] for l in labels})
    uniforms = sorted({l["uniform"] for l in labels})
    type_map = {t: i for i, t in enumerate(types)}
    uniform_map = {u: i for i, u in enumerate(uniforms)}

    y_type = tf.keras.utils.to_categorical([type_map[l["troop_type"]] for l in labels])
    y_uniform = tf.keras.utils.to_categorical([uniform_map[l["uniform"]] for l in labels])

    return y_type, y_uniform, len(types), len(uniforms)


def train_classifier(img_dir: Path, csv_path: Optional[Path], troop_type: str, uniform: str, out_model: Path):
    X, labels = load_dataset(img_dir, csv_path, troop_type, uniform)
    y_type, y_uniform, n_types, n_uniforms = _encode_labels(labels)

    inputs = tf.keras.Input(shape=(128, 128, 3))
    x = tf.keras.layers.Conv2D(16, 3, activation="relu")(inputs)
    x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.Conv2D(32, 3, activation="relu")(x)
    x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.Flatten()(x)

    out_type = tf.keras.layers.Dense(n_types, activation="softmax", name="type")(x)
    out_uniform = tf.keras.layers.Dense(n_uniforms, activation="softmax", name="uniform")(x)

    model = tf.keras.Model(inputs=inputs, outputs=[out_type, out_uniform])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])

    model.fit(X, [y_type, y_uniform], epochs=3, verbose=1)
    model.save(out_model)
    print(f"Model saved to {out_model}")


def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Train troop classifier from images")
    parser.add_argument("img_dir", type=Path, help="Directory of training images")
    parser.add_argument("model_out", type=Path, help="Output path for trained model")
    parser.add_argument("--csv", type=Path, default=None, help="CSV mapping images to attributes")
    parser.add_argument("--troop-type", default="", help="Troop type label if no CSV")
    parser.add_argument("--uniform", default="", help="Uniform label if no CSV")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    train_classifier(args.img_dir, args.csv, args.troop_type, args.uniform, args.model_out)


if __name__ == "__main__":
    main()
