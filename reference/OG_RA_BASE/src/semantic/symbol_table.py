"""SymbolTable — the top-level container for all symbols in a program."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from semantic.scope import GlobalScope


@dataclass
class SymbolTable:
    """Collects every symbol defined in a program.

    Provides flat accessors for each symbol kind as well as a scope
    hierarchy rooted at *global_scope*.

    Attributes
    ----------
    global_scope : GlobalScope — the root scope.
    """

    global_scope: GlobalScope = field(default_factory=GlobalScope)

    # ── Flattened accessors ────────────────────────────────────────────

    @property
    def classes(self) -> list[Any]:
        """All ClassSymbols."""
        return self._collect(self.global_scope, "ClassSymbol")

    @property
    def methods(self) -> list[Any]:
        """All MethodSymbols."""
        return self._collect(self.global_scope, "MethodSymbol")

    @property
    def variables(self) -> list[Any]:
        """All VariableSymbols."""
        return self._collect(self.global_scope, "VariableSymbol")

    @property
    def objects(self) -> list[Any]:
        """All ObjectSymbols."""
        return self._collect(self.global_scope, "ObjectSymbol")

    @property
    def databases(self) -> list[Any]:
        """All DatabaseSymbols."""
        return self._collect(self.global_scope, "DatabaseSymbol")

    # ── Lookup ─────────────────────────────────────────────────────────

    def lookup(self, name: str) -> Any | None:
        """Resolve *name* across all scopes (global walk)."""
        return self.global_scope.lookup(name)

    # ── Display ────────────────────────────────────────────────────────

    def dump(self) -> str:
        """Human-readable table dump."""
        lines: list[str] = []
        lines.append("Classes:")
        for c in self.classes:
            lines.append(f"  {c.name}")
            for v in c.variables:
                lines.append(f"    {v.name}")
            for m in c.methods:
                lines.append(f"    {m.name}")
                for lv in m.variables:
                    lines.append(f"      {lv.name}")
        lines.append("")
        lines.append("Methods:")
        for m in self.methods:
            lines.append(f"  {m.name}")
        lines.append("")
        lines.append("Variables:")
        for v in self.variables:
            lines.append(f"  {v.name}")
        lines.append("")
        lines.append("Objects:")
        for o in self.objects:
            lines.append(f"  {o.name} : {o.class_name}")
        lines.append("")
        lines.append("Databases:")
        for d in self.databases:
            lines.append(f"  {d.name}")
        return "\n".join(lines)

    # ── Internal ───────────────────────────────────────────────────────

    @staticmethod
    def _collect(scope: Any, type_name: str) -> list[Any]:
        """Recursively collect all symbols of *type_name* under *scope*."""
        result: list[Any] = []
        for sym in scope.symbols.values():
            if type(sym).__name__ == type_name:
                result.append(sym)
        for child in scope.children:
            result.extend(SymbolTable._collect(child, type_name))
        return result
