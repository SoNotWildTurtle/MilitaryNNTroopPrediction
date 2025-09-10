"""Zero-shot image classification using CLIP."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

try:
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
except Exception:  # pragma: no cover - optional heavy deps
    CLIPModel = CLIPProcessor = None  # type: ignore
    torch = Image = None  # type: ignore

_MODEL_NAME = "openai/clip-vit-base-patch32"
_model = None
_processor = None


def load_clip_components(model_name: str = _MODEL_NAME):
    """Load and cache the CLIP model and processor."""
    global _model, _processor
    if CLIPModel is None or CLIPProcessor is None:
        raise RuntimeError("transformers not installed")
    if _model is None or _processor is None:
        _model = CLIPModel.from_pretrained(model_name)
        _processor = CLIPProcessor.from_pretrained(model_name)
    return _model, _processor


def classify_clip(image_path: Path, labels: Iterable[str]) -> List[Tuple[str, float]]:
    """Return labels ranked by CLIP similarity.

    Args:
        image_path: Path to the image file.
        labels: Iterable of candidate text labels.
    """
    model, processor = load_clip_components()
    image = Image.open(image_path)
    inputs = processor(text=list(labels), images=image, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits_per_image
        probs = logits.softmax(dim=1)[0].tolist()
    pairs = list(zip(list(labels), probs))
    return sorted(pairs, key=lambda x: x[1], reverse=True)
