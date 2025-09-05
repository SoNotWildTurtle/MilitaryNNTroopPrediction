"""Train a PointNet-Gaussian model from labeled point clouds."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from torch import nn

from ..analysis.pointnet_model import PointNetEncoder


def _load_points(csv_path: Path) -> Tuple[np.ndarray, np.ndarray, Dict[int, str]]:
    points: List[List[float]] = []
    labels: List[int] = []
    label_map: Dict[str, int] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row["x"])
                y = float(row["y"])
                z = float(row["z"])
                label = row["label"]
            except KeyError as exc:
                raise ValueError("CSV must contain x,y,z,label columns") from exc
            if label not in label_map:
                label_map[label] = len(label_map)
            points.append([x, y, z])
            labels.append(label_map[label])
    idx_map = {v: k for k, v in label_map.items()}
    return np.asarray(points, dtype=float), np.asarray(labels, dtype=int), idx_map


def train_pointnet_gaussian_model(
    csv_path: str | Path,
    model_path: str | Path = "pointnet_encoder.pt",
    stats_path: str | Path = "pointnet_gaussian_model.json",
    epochs: int = 5,
    lr: float = 1e-3,
) -> Tuple[Path, Path]:
    """Train encoder and compute Gaussian stats per class."""
    csv_path = Path(csv_path)
    points, labels, idx_map = _load_points(csv_path)
    num_classes = len(idx_map)
    if num_classes < 2:
        raise ValueError("Need at least two classes to train")

    device = torch.device("cpu")
    pts = torch.tensor(points, dtype=torch.float32, device=device)
    lbls = torch.tensor(labels, dtype=torch.long, device=device)

    model = PointNetEncoder(feat_dim=32, num_classes=num_classes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    for _ in range(max(1, epochs)):
        optimizer.zero_grad()
        logits, _ = model(pts)
        loss = criterion(logits, lbls)
        loss.backward()
        optimizer.step()

    # Save encoder weights only
    torch.save(model.mlp.state_dict(), model_path)

    # Compute features for Gaussian stats
    model.classifier = None
    with torch.no_grad():
        feats = model(pts).cpu().numpy()
    stats: Dict[str, Dict[str, List[float]]] = {}
    for idx, label in idx_map.items():
        feat_arr = feats[lbls.cpu().numpy() == idx]
        if feat_arr.shape[0] < 2:
            continue
        mean = feat_arr.mean(axis=0)
        cov = np.cov(feat_arr, rowvar=False).tolist()
        stats[label] = {"mean": mean.tolist(), "cov": cov}
    if not stats:
        raise ValueError("No valid class statistics computed")
    with Path(stats_path).open("w", encoding="utf-8") as f:
        json.dump(stats, f)
    return Path(model_path), Path(stats_path)
