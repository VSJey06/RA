"""
source_location.py — Source location tracking for the RA language.

Provides the ``SourceLocation`` dataclass used by tokens, AST nodes,
and diagnostics to pinpoint the exact source range of every construct.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    """A range in source text.

    All values are 1-based.  ``end_line`` / ``end_column`` point to the
    *last* character of the range (inclusive).
    """

    line: int
    column: int
    end_line: int
    end_column: int

    @property
    def start(self) -> tuple[int, int]:
        return (self.line, self.column)

    @property
    def end(self) -> tuple[int, int]:
        return (self.end_line, self.end_column)
