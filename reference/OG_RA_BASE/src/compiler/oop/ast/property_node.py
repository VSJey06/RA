"""PropertyAssignmentNode, PropertyAccessNode — OOP AST nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from parser.ast_core import Node


@dataclass
class PropertyAssignmentNode(Node):
    """An object property assignment: ``person.name = value``

    Attributes
    ----------
    object_name   : str  — name of the object variable.
    property_name : str  — name of the property to set.
    value         : Node — right-hand side expression.
    """

    object_name:   str
    property_name: str
    value:         Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return (
            f"PropertyAssignmentNode(obj={self.object_name!r}, "
            f"prop={self.property_name!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class PropertyAccessNode(Node):
    """A property-access chain: ``object.property``.

    Attributes
    ----------
    object   : Node — the left-hand side expression.
    property : str  — the property name (identifier after ``.``).
    """

    object:   Node
    property: str

    @property
    def children(self) -> list[Node]:
        return [self.object]

    def __repr__(self) -> str:
        return (
            f"PropertyAccessNode(prop={self.property!r}, line={self.line})"
        )
