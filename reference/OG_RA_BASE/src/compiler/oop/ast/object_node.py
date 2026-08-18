"""ObjectDeclarationNode — OOP AST node for object instantiation."""

from __future__ import annotations

from dataclasses import dataclass, field

from parser.ast_core import Node


@dataclass
class ObjectDeclarationNode(Node):
    """Object declaration: ``Obj.ClassName.ObjectName``

    Attributes
    ----------
    object_name : str        — name of the object variable.
    class_name  : str        — name of the class to instantiate.
    args        : list[Node] — constructor argument expressions.
    """

    object_name: str
    class_name:  str
    args:        list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.args

    def __repr__(self) -> str:
        return (
            f"ObjectDeclarationNode(obj={self.object_name!r}, cls={self.class_name!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )
