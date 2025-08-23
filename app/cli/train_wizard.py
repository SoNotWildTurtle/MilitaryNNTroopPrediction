"""Interactive wizard for easy YOLO training."""
from pathlib import Path
from typing import List

from ..training.train_yolo import train_yolo
from ..training.train_with_augmentation import train_with_augmentation
from ..config import settings
from ..translation import translate_text

_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate static UI text."""
    return translate_text(text, target_lang=_LANG)


def _prompt_path(msg: str, default: Path) -> Path:
    val = input(f"{_t(msg)} [{default}]: ").strip()
    return Path(val) if val else default


def _prompt_int(msg: str, default: int) -> int:
    val = input(f"{_t(msg)} [{default}]: ").strip()
    return int(val) if val else default


def _prompt_bool(msg: str, default: bool = False) -> bool:
    val = input(f"{_t(msg)} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    if not val:
        return default
    return val[0] == 'y'


def run_train_wizard() -> None:
    """Guide the user through training a YOLO model with minimal inputs."""
    train_dir = _prompt_path("Training image directory", Path("data/train/images"))
    val_dir = _prompt_path("Validation image directory", Path("data/val/images"))
    classes_in = input(f"{_t('Class names (space separated)')} [troop vehicle]: ").strip()
    classes: List[str] = classes_in.split() if classes_in else ["troop", "vehicle"]
    out_model = _prompt_path("Output model file", Path("model.pt"))
    epochs = _prompt_int("Epochs", 25)
    use_aug = _prompt_bool("Augment images before training?", True)
    if use_aug:
        n_aug = _prompt_int("Augmentations per image", 3)
        train_with_augmentation(
            train_dir,
            val_dir,
            classes,
            out_model,
            augment=True,
            n_aug=n_aug,
            epochs=epochs,
        )
    else:
        train_yolo(train_dir, val_dir, classes, epochs, out_model)
    print(_t("Training complete. Model saved to"), out_model)


if __name__ == "__main__":
    run_train_wizard()
