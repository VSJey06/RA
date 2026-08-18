"""MethodNode, MethodInvokeNode, MethodCallNode — OOP AST nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from parser.ast_core import Node


@dataclass
class MethodNode(Node):
    """A method definition: ``M.name: ... /``

    The body is terminated by a standalone ``/`` token.

    Attributes
    ----------
    name : str        — method name (identifier after ``M.``).
    body : list[Node] — statement nodes forming the method body.
    """

    name: str
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"MethodNode(name={self.name!r}, "
            f"body_stmts={len(self.body)}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class MethodCallNode(Node):
    """A method-invocation statement: ``identifier : argument``

    RC3-09A: Supports multiple comma-separated arguments after the
    colon (e.g. ``name.replace:"old","new"``).  Single-argument calls
    populate ``argument``; extra arguments go in ``arguments``.

    Attributes
    ----------
    method    : str       — callee identifier.
    argument  : Node      — first argument expression.
    arguments : list[Node] — additional arguments (RC3-09A).
    """

    method:   str
    argument: Node
    arguments: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return [self.argument, *self.arguments]

    def __repr__(self) -> str:
        parts = [f"method={self.method!r}", f"line={self.line}"]
        if self.arguments:
            parts.append(f"extra_args={len(self.arguments)}")
        parts.append(f"auto_close={self.auto_close}")
        return f"MethodCallNode({', '.join(parts)})"


@dataclass(slots=True)
class MethodInvokeNode(Node):
    """A method invocation statement: ``MethodName.run`` or ``Obj.MethodName.run``

    Attributes
    ----------
    method_name : str             — method to invoke.
    object_name : str | None      — object variable (``None`` for global method).
    """

    method_name: str
    object_name: Optional[str] = None

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"MethodInvokeNode(method={self.method_name!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )
