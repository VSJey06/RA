"""InheritanceNode — OOP AST node (reserved for future use).

RA currently supports flat classes without inheritance.  This module
provides a placeholder ``InheritanceNode`` so that the AST extraction
is complete and downstream code can reference it.
"""

from __future__ import annotations

from dataclasses import dataclass

from parser.ast_core import Node


@dataclass
class InheritanceNode(Node):
    """Placeholder for future class inheritance support.

    At present, the RA language does not implement class inheritance
    (no ``inherit``, ``extends``, or ``super`` constructs exist).
    This node exists for forward compatibility.
    """

    child_class_name: str = ""
    parent_class_name: str = ""

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"InheritanceNode(child={self.child_class_name!r}, "
            f"parent={self.parent_class_name!r}, line={self.line})"
        )
