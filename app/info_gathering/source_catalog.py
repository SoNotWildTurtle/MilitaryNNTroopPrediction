"""Persistent catalog for discovered imagery sources."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List

import requests


class SourceCatalog:
    """Store and deduplicate imagery sources on disk."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("SOURCE_CATALOG", "sources.json"))
        self.sources = set()  # type: set[str]
        if self.path.exists():
            try:
                self.sources = set(json.loads(self.path.read_text()))
            except Exception:
                # Corrupt file – start fresh
                self.sources = set()

    def add(self, sources: Iterable[str], verify: bool = True) -> List[str]:
        """Add new sources, optionally verifying the URL is reachable.

        Returns a list of sources that were successfully added.
        """
        added: List[str] = []
        for src in sources:
            if src in self.sources:
                continue
            if verify:
                try:  # pragma: no cover - network dependent
                    requests.head(src, timeout=5)
                except Exception:
                    continue
            self.sources.add(src)
            added.append(src)
        self.path.write_text(json.dumps(sorted(self.sources), indent=2))
        return added

    def all(self) -> List[str]:
        """Return all known sources."""
        return sorted(self.sources)
