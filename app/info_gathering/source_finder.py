"""Background thread that queries ChatGPT for new input sources."""

from __future__ import annotations

import os
import threading
from typing import Callable, List, Optional

import openai

from .source_catalog import SourceCatalog

openai.api_key = os.getenv("OPENAI_API_KEY", "")


def _ask_chatgpt(prompt: str) -> List[str]:
    """Request candidate input sources from ChatGPT."""
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message["content"]
        return [line.strip() for line in text.splitlines() if line.strip()]
    except Exception as exc:  # pragma: no cover - network errors
        print(f"ChatGPT request failed: {exc}")
        return []


class SourceFinder(threading.Thread):
    """Thread that periodically asks ChatGPT for input sources."""

    def __init__(
        self,
        prompt: str,
        interval: int = 3600,
        on_result: Optional[Callable[[List[str]], None]] = None,
        catalog: Optional[SourceCatalog] = None,
        verify: bool = True,
    ) -> None:
        super().__init__(daemon=True)
        self.prompt = prompt
        self.interval = interval
        self.on_result = on_result or (lambda sources: None)
        self.catalog = catalog
        self.verify = verify
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            sources = _ask_chatgpt(self.prompt)
            if sources:
                if self.catalog:
                    self.catalog.add(sources, verify=self.verify)
                self.on_result(sources)
            self._stop.wait(self.interval)

    def stop(self) -> None:
        """Stop the background thread."""
        self._stop.set()


def start_source_finder(
    prompt: str,
    interval: int = 3600,
    callback: Optional[Callable[[List[str]], None]] = None,
    catalog: Optional[SourceCatalog] = None,
    verify: bool = True,
) -> SourceFinder:
    """Start the source finder in a new thread and return it."""
    finder = SourceFinder(prompt, interval, callback, catalog or SourceCatalog(), verify)
    finder.start()
    return finder
