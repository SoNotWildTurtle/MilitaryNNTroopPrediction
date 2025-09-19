from __future__ import annotations
"""Classify images using an ORB bag-of-visual-words model."""
from pathlib import Path
from typing import List, Tuple
import pickle
import numpy as np
from sklearn.cluster import MiniBatchKMeans


def _extract_descriptors(image_path: Path, max_keypoints: int = 500) -> np.ndarray:
    """Return ORB descriptors for an image."""
    try:  # lazy import to avoid hard dependency during compilation
        from skimage.io import imread
        from skimage.color import rgb2gray
        from skimage.feature import ORB
    except Exception as exc:  # pragma: no cover
        raise ImportError("scikit-image is required for ORB bag-of-words") from exc
    img = rgb2gray(imread(image_path))
    orb = ORB(n_keypoints=max_keypoints)
    orb.detect_and_extract(img)
    return orb.descriptors if orb.descriptors is not None else np.empty((0, 256), dtype=np.uint8)


def match_orb_bow(image: Path, model_path: Path) -> List[Tuple[str, float]]:
    """Rank classes for ``image`` using a saved ORB bag-of-words model."""
    with Path(model_path).open("rb") as f:
        vocab, clf = pickle.load(f)

    desc = _extract_descriptors(image)
    if desc.size == 0:
        return []
    words = vocab.predict(desc)
    hist, _ = np.histogram(words, bins=np.arange(vocab.n_clusters + 1), density=True)
    probs = clf.predict_proba([hist])[0]
    classes = clf.classes_
    return sorted(zip(classes, probs), key=lambda x: x[1], reverse=True)
