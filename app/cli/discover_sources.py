"""CLI to query ChatGPT for imagery sources and store them."""
from __future__ import annotations

import argparse

from ..info_gathering.source_finder import _ask_chatgpt
from ..info_gathering.source_catalog import SourceCatalog


def run_source_discovery() -> None:
    parser = argparse.ArgumentParser(description="Discover imagery sources via ChatGPT")
    parser.add_argument("prompt", help="Prompt describing desired imagery feeds")
    parser.add_argument("--verify", action="store_true", help="Verify URLs before storing")
    args = parser.parse_args()

    catalog = SourceCatalog()
    sources = _ask_chatgpt(args.prompt)
    if not sources:
        print("No sources discovered")
        return
    added = catalog.add(sources, verify=args.verify)
    if added:
        print("Stored sources:")
        for src in added:
            print(src)
    else:
        print("No new sources added")


if __name__ == "__main__":
    run_source_discovery()
