"""Interactive wizard for easy YOLO training."""
from argparse import ArgumentParser
from pathlib import Path
from typing import List, Optional

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


def run_train_wizard(argv: Optional[List[str]] = None) -> None:
    """Guide the user through training a YOLO model with minimal inputs."""
    parser = ArgumentParser(description=_t("Interactive wizard for easy YOLO training."))
    parser.add_argument("--train-dir", type=Path, help=_t("Training image directory"))
    parser.add_argument("--val-dir", type=Path, help=_t("Validation image directory"))
    parser.add_argument("--classes", nargs="*", help=_t("Class names (space separated)"))
    parser.add_argument("--out-model", type=Path, help=_t("Output model file"))
    parser.add_argument("--epochs", type=int, help=_t("Epochs"))
    parser.add_argument("--augment", dest="augment", action="store_true", help=_t("Augment images before training"))
    parser.add_argument("--no-augment", dest="augment", action="store_false", help=_t("Do not augment images"))
    parser.add_argument("--n-aug", type=int, help=_t("Augmentations per image"))
    parser.set_defaults(augment=None)
    args = parser.parse_args(argv)

    train_dir = args.train_dir or _prompt_path("Training image directory", Path("data/train/images"))
    val_dir = args.val_dir or _prompt_path("Validation image directory", Path("data/val/images"))
    if args.classes:
        classes = args.classes
    else:
        classes_in = input(f"{_t('Class names (space separated)')} [troop vehicle]: ").strip()
        classes = classes_in.split() if classes_in else ["troop", "vehicle"]
    out_model = args.out_model or _prompt_path("Output model file", Path("model.pt"))
    epochs = args.epochs or _prompt_int("Epochs", 25)

    if args.augment is None:
        use_aug = _prompt_bool("Augment images before training?", True)
    else:
        use_aug = args.augment

    if use_aug:
        n_aug = args.n_aug or _prompt_int("Augmentations per image", 3)
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
