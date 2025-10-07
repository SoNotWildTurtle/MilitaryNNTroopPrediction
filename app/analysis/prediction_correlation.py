"""Compute correlations between model predictions."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
from typing import Dict

import numpy as np


def prediction_correlations(predictions_file: Path) -> Dict[str, Dict[str, float]]:
    """Return a correlation matrix between models.

    The JSON file must contain objects with ``image``, ``model``, and ``confidence``.
    Only images scored by both models are included in pairwise correlations.
    """
    data = json.loads(Path(predictions_file).read_text())
    by_model: Dict[str, Dict[str, float]] = defaultdict(dict)
    for rec in data:
        img = rec.get("image")
        model = rec.get("model")
        if img and model:
            by_model[model][img] = float(rec.get("confidence", 0.0))
    models = sorted(by_model)
    matrix: Dict[str, Dict[str, float]] = {m: {} for m in models}
    for m1 in models:
        for m2 in models:
            common = set(by_model[m1]) & set(by_model[m2])
            if len(common) < 2:
                matrix[m1][m2] = float("nan")
            else:
                a = [by_model[m1][i] for i in common]
                b = [by_model[m2][i] for i in common]
                matrix[m1][m2] = float(np.corrcoef(a, b)[0, 1])
    return matrix
