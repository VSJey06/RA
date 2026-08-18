"""class_validator.py — Class symbol building and semantic validation.

Extracted from ``symbol_builder.py`` (visit_ClassNode) and
``semantic_analyzer.py`` (visit_ClassNode, _current_class).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from parser.ra_ast import ClassNode
from semantic.scope import ClassScope
from semantic.symbol import ClassSymbol

if TYPE_CHECKING:
    from semantic.symbol_table import SymbolTable


class ClassValidatorMixin:
    """Mixin that adds class-related validation to ``SemanticAnalyzer``."""

    def visit_ClassNode(self, node: ClassNode) -> None:
        if node.name in self._seen_classes:
            self._error(f"Class '{node.name}' already defined", node)
        self._seen_classes.add(node.name)
        self._enter(node)
        self.generic_visit(node)
        self._leave()

    def _current_class(self) -> Optional[Any]:
        """Walk up scope chain to find enclosing ClassSymbol, if any."""
        scope = self._scope
        while scope is not None:
            if isinstance(scope, ClassScope):
                return scope.class_symbol
            scope = scope.parent
        return None


class ClassSymbolBuilderMixin:
    """Mixin that adds class-related symbol building to ``SymbolBuilder``."""

    def visit_ClassNode(self, node: ClassNode) -> None:
        sym = ClassSymbol(name=node.name, node=node)
        self._scope.define(sym)
        class_scope = ClassScope(class_symbol=sym)
        self._enter(class_scope)
        for member in node.members:
            self.visit(member)
        self._leave()
