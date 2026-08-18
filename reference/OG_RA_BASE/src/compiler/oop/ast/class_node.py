"""ClassNode — OOP AST node for class definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from parser.ast_core import Node


@dataclass
class ClassNode(Node):
    """A class definition: ``@Cls.Name: ... @``

    The body is terminated by a bare ``@`` token or an implicit boundary.

    Attributes
    ----------
    name    : str        — class name (identifier after ``@Cls.``).
    members : list[Node] — field declarations, methods, and nested blocks.
    """

    name:    str
    members: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.members

    def __repr__(self) -> str:
        return (
            f"ClassNode(name={self.name!r}, members={len(self.members)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )
