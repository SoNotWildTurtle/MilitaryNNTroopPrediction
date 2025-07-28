"""Utility to log troop movements to MongoDB."""

from datetime import datetime
from typing import List, Dict
from pathlib import Path
import csv

from .database import get_collection


def log_movements(unit_id: str, movements: List[Dict]) -> None:
    """Store a list of movement records for later analysis."""
    coll = get_collection("movements")
    docs = []
    now = datetime.utcnow()
    for m in movements:
        doc = {
            "unit_id": unit_id,
            "lat": float(m.get("lat", 0)),
            "lon": float(m.get("lon", 0)),
            "timestamp": m.get("timestamp", now),
        }
        for k, v in m.items():
            if k not in doc:
                doc[k] = v
        docs.append(doc)
    if docs:
        coll.insert_many(docs)
        print(f"Inserted {len(docs)} movement records for {unit_id}")


def log_from_csv(unit_id: str, csv_path: Path) -> None:
    """Load movement rows from a CSV file and log them."""
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    log_movements(unit_id, rows)


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Log movement data from a CSV file")
    p.add_argument("unit_id", help="Unit identifier")
    p.add_argument("csv", type=Path, help="CSV file with lat,lon,timestamp")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    log_from_csv(args.unit_id, args.csv)


if __name__ == "__main__":
    main()
