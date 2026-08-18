"""ast_core.py — Core AST base classes for the RA language.

Contains ``Node`` and ``NodeVisitor`` used by all AST nodes across
the parser, semantic, and runtime layers.

Extracted from ``ra_ast.py`` so that OOP AST nodes in ``src/oop/ast/``
can inherit from ``Node`` without creating circular imports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from parser.source_location import SourceLocation


@dataclass
class Node(ABC):
    """Abstract base for every AST node in the RA language.

    Attributes
    ----------
    line       : 1-based line number of the opening token.
    col        : 1-based column number of the opening token (0 if unknown).
    end_line   : 1-based end line (inclusive; 0 if unknown).
    end_column : 1-based end column (inclusive; 0 if unknown).
    auto_close : True when the parser injected an implicit block terminator
                 (keyword-only to avoid clashing with positional fields).
    """

    line:       int
    col:        int = field(default=0, kw_only=True)
    end_line:   int = field(default=0, kw_only=True)
    end_column: int = field(default=0, kw_only=True)
    auto_close: bool = field(default=False, kw_only=True)

    @property
    def loc(self) -> SourceLocation | None:
        if self.col and self.end_line and self.end_column:
            return SourceLocation(
                line=self.line, column=self.col,
                end_line=self.end_line, end_column=self.end_column,
            )
        if self.col:
            return SourceLocation(
                line=self.line, column=self.col,
                end_line=self.line, end_column=self.col,
            )
        return None

    @property
    @abstractmethod
    def children(self) -> list[Node]:
        """Every direct child node for generic tree traversal."""
        ...

    def accept(self, visitor: NodeVisitor) -> Any:
        """Double-dispatch into *visitor*.

        Looks for ``visit_<ClassName>``; falls back to ``generic_visit``.
        """
        method = getattr(
            visitor,
            f"visit_{type(self).__name__}",
            visitor.generic_visit,
        )
        return method(self)

    def walk(self):
        """Depth-first generator yielding *self* and every descendant."""
        yield self
        for child in self.children:
            yield from child.walk()

    def __repr__(self) -> str:
        loc = f"line={self.line}"
        if self.col:
            loc += f",col={self.col}"
        if self.end_line:
            loc += f",end=({self.end_line},{self.end_column})"
        return f"{type(self).__name__}({loc}, auto_close={self.auto_close})"


class NodeVisitor(ABC):
    """Base class for AST visitors (Visitor pattern).

    Subclass and override ``visit_<NodeType>`` for the nodes you care
    about.  Unhandled nodes fall through to ``generic_visit``, which
    recurses into all children.
    """

    def visit(self, node: Node) -> Any:
        """Entry point -- dispatches to the appropriate ``visit_*``."""
        return node.accept(self)

    def generic_visit(self, node: Node) -> None:
        """Fallback: visit all children in order."""
        for child in node.children:
            self.visit(child)

    def visit_all(self, nodes: list[Node]) -> None:
        """Convenience: visit every node in a list."""
        for node in nodes:
            self.visit(node)
