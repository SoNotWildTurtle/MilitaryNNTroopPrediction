"""Report classifier agreement on an image with weighted consensus."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, List

from rich.console import Console
from rich.table import Table

from ..analysis import analyze_cohesion
from ..detection import (
    classify_convnext,
    classify_feature_fused,
    classify_resnet,
    classify_swin,
    classify_vit,
)

# Build callable wrappers for each model with default components.


def _resnet_wrapper() -> Callable[[Path], Dict[str, float]]:
    clf = None
    model, transform = None, None
    try:
        from ..detection.resnet_identifier import (
            load_resnet_classifier,
            load_resnet_components,
        )

        model, transform = load_resnet_components()
        clf = load_resnet_classifier(None)
    except Exception:
        pass
    return lambda img: classify_resnet(img, clf, model, transform)


def _swin_wrapper() -> Callable[[Path], Dict[str, float]]:
    clf = None
    model = None
    processor = None
    try:
        from ..detection.swin_identifier import load_swin_components, load_swin_classifier

        model, processor = load_swin_components()
        clf = load_swin_classifier(None)
    except Exception:
        pass
    return lambda img: classify_swin(img, clf, model, processor)


def _vit_wrapper() -> Callable[[Path], Dict[str, float]]:
    clf = None
    model = None
    processor = None
    try:
        from ..detection.vit_identifier import load_vit_components, load_vit_classifier

        model, processor = load_vit_components()
        clf = load_vit_classifier(None)
    except Exception:
        pass
    return lambda img: classify_vit(img, clf, model, processor)


def _convnext_wrapper() -> Callable[[Path], Dict[str, float]]:
    clf = None
    model = None
    transform = None
    try:
        from ..detection.convnext_identifier import (
            load_convnext_classifier,
            load_convnext_components,
        )

        model, transform = load_convnext_components()
        clf = load_convnext_classifier(None)
    except Exception:
        pass
    return lambda img: classify_convnext(img, clf, model, transform)


def _feature_fused_wrapper() -> Callable[[Path], Dict[str, float]]:
    clf = None
    try:
        from ..detection.feature_fused_identifier import load_feature_fused_classifier

        clf = load_feature_fused_classifier(None)
    except Exception:
        pass
    return lambda img: classify_feature_fused(img, clf)


MODEL_BUILDERS = {
    "resnet": _resnet_wrapper,
    "swin": _swin_wrapper,
    "vit": _vit_wrapper,
    "convnext": _convnext_wrapper,
    "feature_fused": _feature_fused_wrapper,
}


def build_models(names: Iterable[str]) -> List[Callable[[Path], Dict[str, float]]]:
    models: List[Callable[[Path], Dict[str, float]]] = []
    for name in names:
        builder = MODEL_BUILDERS.get(name)
        if builder is None:
            continue
        try:
            models.append(builder())
        except Exception:
            pass
    return models


def main(image: str, models: Iterable[str]) -> None:
    console = Console()
    callables = build_models(models)
    result = analyze_cohesion(Path(image), callables)

    table = Table(title="Model Predictions")
    table.add_column("Model")
    table.add_column("Target")
    table.add_column("Confidence")
    for name, pred in zip(models, result["predictions"]):
        table.add_row(name, pred["target"], f"{pred['confidence']:.2f}")
    console.print(table)
    console.print(
        f"Consensus: [bold]{result['consensus']}[/bold]",
        f"Agreement: {result['agreement']:.2%}",
        f"Weighted consensus: [bold]{result['weighted_consensus']}[/bold]",
        f"Weighted agreement: {result['weighted_agreement']:.2%}",
        sep="\n",
    )


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Path to image")
    parser.add_argument(
        "--models",
        nargs="*",
        default=list(MODEL_BUILDERS.keys()),
        help="Classifier models to include",
    )
    args = parser.parse_args()
    main(args.image, args.models)


def run_cohesion_report(image: str, models: Iterable[str] | None = None) -> None:
    if models is None:
        models = list(MODEL_BUILDERS.keys())
    main(image, models)


__all__ = ["run_cohesion_report"]
