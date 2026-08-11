"""Terminal presentation helpers.

Three different commands need to print aligned columns. Rendering tables here
rather than in each handler is the difference between one implementation and
three slightly inconsistent ones.
"""

from __future__ import annotations

from collections.abc import Sequence

BANNER = """
================================
        CHATTERBUDDY
 Your Personal Automation Tool
================================

Type 'help' to view available commands.
""".strip("\n")


def render_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Render rows as space-aligned columns sized to their widest cell."""
    text_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in text_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells: Sequence[str]) -> str:
        padded = (cell.ljust(widths[index]) for index, cell in enumerate(cells))
        return "  ".join(padded).rstrip()

    divider = "  ".join("-" * width for width in widths)
    return "\n".join([line(list(headers)), divider, *(line(row) for row in text_rows)])


def truncate(text: str, width: int) -> str:
    """Shorten text to ``width`` characters, marking the cut with an ellipsis."""
    if width <= 1 or len(text) <= width:
        return text
    return text[: width - 1] + "\u2026"
