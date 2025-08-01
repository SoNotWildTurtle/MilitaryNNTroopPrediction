"""Image utilities for preprocessing satellite imagery."""

from pathlib import Path
from PIL import Image, ImageEnhance


def enhance_image(path: Path) -> Path:
    """Enhance image contrast slightly to aid detection."""
    img = Image.open(path)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)
    img.save(path)
    return path


def prepare_ground_troop_image(path: Path) -> Path:
    """Denoise and normalize orientation for troop detection."""
    img = Image.open(path)
    # Convert to RGB in case of grayscale imagery
    img = img.convert("RGB")
    # Slightly enhance contrast and sharpness
    img = ImageEnhance.Contrast(img).enhance(1.3)
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    img.save(path)
    return path
