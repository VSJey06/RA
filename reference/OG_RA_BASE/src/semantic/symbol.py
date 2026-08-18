"""Symbol type definitions for the RA language Symbol Table."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Symbol:
    """Base for all symbol entries.

    Attributes
    ----------
    name  : str          — canonical name of the symbol.
    node  : Any | None   — the AST node that defined this symbol.
    scope : Scope | None — the scope this symbol belongs to.
    rid   : str | None   — Runtime Identifier assigned by the RID bridge.
    """

    name: str
    node: Any = field(default=None, kw_only=True)
    scope: Any = field(default=None, kw_only=True)  # Scope reference (avoid circular import)
    rid: Optional[str] = field(default=None, kw_only=True)  # RID value set by SemanticRegistryBridge

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name})"


@dataclass
class ClassSymbol(Symbol):
    """A class definition (@Cls.Name:).

    Attributes
    ----------
    methods   : list[MethodSymbol]   — methods declared in this class.
    variables : list[VariableSymbol] — fields declared in this class.
    """

    methods: list[MethodSymbol] = field(default_factory=list)
    variables: list[VariableSymbol] = field(default_factory=list)


@dataclass
class MethodSymbol(Symbol):
    """A method definition (M.name:).

    Attributes
    ----------
    variables : list[VariableSymbol] — local variables in this method.
    """

    variables: list[VariableSymbol] = field(default_factory=list)


@dataclass
class VariableSymbol(Symbol):
    """A typed or plain variable declaration (S name / I age / L items / x = …).

    Attributes
    ----------
    var_type : str | None — type keyword ("S", "I", "L") or None for plain.
    """

    var_type: Optional[str] = field(default=None, kw_only=True)


@dataclass
class ObjectSymbol(Symbol):
    """An object instantiation (Obj.ClassName.VariableName).

    Attributes
    ----------
    class_name : str — name of the class being instantiated.
    """

    class_name: str = field(kw_only=True)


@dataclass
class DatabaseSymbol(Symbol):
    """A database block declaration (Db: or Db.Name:)."""


@dataclass
class PackageSymbol(Symbol):
    """A PAC package command exposed to RA source code.

    ``PackageSymbol`` instances are injected into the global scope by
    ``PackageRegistry`` so that ``Stack.Users`` resolves without errors.

    Attributes
    ----------
    target_class : type — the Python class that implements operations.
    members      : dict[str, str] — operation name → description.
    description  : str — one-line summary of the package command.
    """

    target_class: type = field(kw_only=True)
    members: dict[str, str] = field(default_factory=dict)
    description: str = field(default="", kw_only=True)
