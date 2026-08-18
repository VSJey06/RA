"""method_validator.py — Method symbol building and semantic validation.

Extracted from ``symbol_builder.py`` (visit_MethodNode) and
``semantic_analyzer.py`` (visit_MethodNode).
"""

from __future__ import annotations

from parser.ra_ast import MethodNode
from semantic.scope import ClassScope, MethodScope
from semantic.symbol import MethodSymbol


class MethodValidatorMixin:
    """Mixin that adds method-related validation to ``SemanticAnalyzer``."""

    def visit_MethodNode(self, node: MethodNode) -> None:
        current_class = self._current_class()
        if current_class is not None:
            seen = self._seen_methods.setdefault(current_class.name, set())
            if node.name in seen:
                self._error(f"Method '{node.name}' already defined", node)
            seen.add(node.name)
        self._enter(node)
        self.generic_visit(node)
        self._leave()


class MethodSymbolBuilderMixin:
    """Mixin that adds method-related symbol building to ``SymbolBuilder``."""

    def visit_MethodNode(self, node: MethodNode) -> None:
        sym = MethodSymbol(name=node.name, node=node)
        self._scope.define(sym)
        if isinstance(self._scope, ClassScope):
            self._scope.class_symbol.methods.append(sym)
        method_scope = MethodScope(method_symbol=sym)
        self._enter(method_scope)
        for stmt in node.body:
            self.visit(stmt)
        self._leave()
