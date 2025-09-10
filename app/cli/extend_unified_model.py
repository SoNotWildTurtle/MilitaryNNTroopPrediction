"""CLI to expand the unified classifier with a new target label."""
from pathlib import Path

from rich.prompt import Prompt

from ..detection.unified_identifier import load_unified_model, add_target_to_model


def run_extend_unified_model() -> None:
    """Prompt for a model path and label then append a neuron for that label."""
    model_path = Path(Prompt.ask("Model path", default="unified_model.h5"))
    label = Prompt.ask("New target label")
    model = load_unified_model(model_path if model_path.exists() else None)
    model = add_target_to_model(model, label)
    model.save(model_path)
    print(f"Added '{label}' to model at {model_path}")
