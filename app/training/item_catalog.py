import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

CATALOG_PATH = Path(os.getenv("ITEM_CATALOG", "items.csv"))

def register_item(
    item_id: str,
    class_label: str,
    score: float,
    path: Path = CATALOG_PATH,
) -> None:
    """Append an item identifier, class and score to the catalog CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["item_id", "class", "score"])
        writer.writerow([item_id, class_label, f"{score:.4f}"])

def load_items(path: Path = CATALOG_PATH) -> List[Dict[str, str]]:
    """Return all catalog entries as dictionaries."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open() as f:
        reader = csv.DictReader(f)
        return list(reader)

def items_by_class(path: Path = CATALOG_PATH) -> Dict[str, List[Dict[str, str]]]:
    """Group catalog entries by class label."""
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in load_items(path):
        grouped[row["class"]].append(row)
    return grouped
