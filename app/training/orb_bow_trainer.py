from __future__ import annotations
"""Train an ORB bag-of-visual-words image classifier."""
from pathlib import Path
from typing import Sequence
import pickle
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.linear_model import LogisticRegression

from ..analysis.orb_bow_match import _extract_descriptors


def train_orb_bow(
    image_files: Sequence[Path],
    labels: Sequence[str],
    model_out: Path,
    clusters: int = 64,
) -> Path:
    """Fit a bag-of-visual-words model and save to ``model_out``."""
    if len(image_files) != len(labels):
        raise ValueError("Images and labels must have equal length")

    all_desc = [d for img in image_files if (d := _extract_descriptors(img)).size]
    if not all_desc:
        raise ValueError("No descriptors found in images")
    vocab = MiniBatchKMeans(n_clusters=clusters, random_state=0)
    vocab.fit(np.vstack(all_desc))

    hists = []
    for img in image_files:
        desc = _extract_descriptors(img)
        if desc.size == 0:
            hist = np.zeros(clusters)
        else:
            words = vocab.predict(desc)
            hist, _ = np.histogram(words, bins=np.arange(clusters + 1), density=True)
        hists.append(hist)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(hists, labels)

    with Path(model_out).open("wb") as f:
        pickle.dump((vocab, clf), f)
    return Path(model_out)
