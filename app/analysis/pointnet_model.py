"""Simple PointNet-style encoder for point cloud features."""
from __future__ import annotations

import torch
import torch.nn as nn


class PointNetEncoder(nn.Module):
    """Minimal PointNet-like encoder.

    The network maps 3-D points to a latent feature space. Optionally a
    classifier head can be included for supervised training.
    """

    def __init__(self, feat_dim: int = 32, num_classes: int = 0) -> None:
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(3, 64),
            nn.ReLU(),
            nn.Linear(64, feat_dim),
            nn.ReLU(),
        )
        self.classifier = nn.Linear(feat_dim, num_classes) if num_classes else None

    def forward(self, x: torch.Tensor):
        feat = self.mlp(x)
        if self.classifier:
            return self.classifier(feat), feat
        return feat
