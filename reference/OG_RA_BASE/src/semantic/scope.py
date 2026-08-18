"""Scope hierarchy for the RA language Symbol Table."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Scope:
    """A scope in the symbol hierarchy.

    Attributes
    ----------
    parent   : Scope | None     — enclosing scope (None for global).
    children : list[Scope]      — nested scopes.
    symbols  : dict[str, Any]   — name → Symbol mapping.
    """

    parent: Optional[Scope] = None
    children: list[Scope] = field(default_factory=list)
    symbols: dict[str, Any] = field(default_factory=dict)

    def define(self, symbol: Any) -> None:
        """Register *symbol* in this scope by its name."""
        self.symbols[symbol.name] = symbol

    def lookup(self, name: str) -> Any | None:
        """Resolve *name* starting from this scope, walking up to parent."""
        if name in self.symbols:
            return self.symbols[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        return None

    def lookup_local(self, name: str) -> Any | None:
        """Resolve *name* only in this scope (no parent walk)."""
        return self.symbols.get(name)

    def dump(self, indent: int = 0) -> str:
        prefix = "  " * indent
        lines = [f"{prefix}Scope ({type(self).__name__})"]
        for sym_name, sym in self.symbols.items():
            lines.append(f"{prefix}  {sym!r}")
        for child in self.children:
            lines.append(child.dump(indent + 1))
        return "\n".join(lines)


class GlobalScope(Scope):
    """The top-most scope of a program."""

    def __init__(self) -> None:
        super().__init__(parent=None)


class ClassScope(Scope):
    """Scope introduced by a class definition (@Cls.Name:)."""

    def __init__(self, class_symbol: Any) -> None:
        super().__init__()
        self.class_symbol = class_symbol


class MethodScope(Scope):
    """Scope introduced by a method definition (M.name:)."""

    def __init__(self, method_symbol: Any) -> None:
        super().__init__()
        self.method_symbol = method_symbol


class FunctionScope(Scope):
    """Scope introduced by a function declaration or legacy .fun block."""

    def __init__(self, function_node: Any) -> None:
        super().__init__()
        self.function_node = function_node


class DatabaseScope(Scope):
    """Scope introduced by a database block (Db:)."""

    def __init__(self, db_symbol: Any) -> None:
        super().__init__()
        self.db_symbol = db_symbol
