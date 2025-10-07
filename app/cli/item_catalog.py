import argparse
from rich.console import Console
from rich.table import Table

from app.training.item_catalog import register_item, items_by_class
from app.translation import translator as _


def run_item_catalog() -> None:
    """Manage the training item catalog."""
    parser = argparse.ArgumentParser(description=_("Manage training items"))
    parser.add_argument(
        "--add",
        nargs=3,
        metavar=("ID", "CLASS", "SCORE"),
        help=_("Register an item identifier, class and score"),
    )
    parser.add_argument("--list", action="store_true", help=_("List items sorted by class"))
    args = parser.parse_args()

    if args.add:
        item_id, cls, score = args.add
        register_item(item_id, cls, float(score))

    if args.list:
        groups = items_by_class()
        console = Console()
        table = Table(_("Class"), _("Item ID"), _("Score"))
        for cls in sorted(groups):
            for item in groups[cls]:
                table.add_row(cls, item["item_id"], item.get("score", ""))
        console.print(table)
