"""OOPNode, ConstructorNode, EncapsulationNode — OOP AST nodes."""

from __future__ import annotations

from dataclasses import dataclass, field

from parser.ast_core import Node


@dataclass
class OOPNode(Node):
    """Activates the built-in OOP library: ``OOP``

    A single-word statement that enables constructor, encapsulation,
    and other OOP features in the runtime.
    """

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"OOPNode(line={self.line})"


@dataclass
class ConstructorNode(Node):
    """A constructor block: ``Con: ... con.close``

    ``auto_close=True`` means the parser injected an implicit close.

    Attributes
    ----------
    body : list[Node] — statements that execute during object creation.
    """

    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"ConstructorNode(stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class EncapsulationNode(Node):
    """An encapsulation block: ``En: ... en.close``

    ``auto_close=True`` means the parser injected an implicit close.

    Attributes
    ----------
    body : list[Node] — property declarations that are private.
    """

    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"EncapsulationNode(stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )
