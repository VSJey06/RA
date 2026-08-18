"""object_validator.py — Object symbol building and semantic validation.

Extracted from ``symbol_builder.py`` (visit_ObjectDeclarationNode) and
``semantic_analyzer.py`` (visit_ObjectDeclarationNode, visit_MethodInvokeNode).
"""

from __future__ import annotations

from parser.ra_ast import MethodInvokeNode, ObjectDeclarationNode
from semantic.symbol import ClassSymbol, ObjectSymbol


class ObjectValidatorMixin:
    """Mixin that adds object-related validation to ``SemanticAnalyzer``."""

    def visit_ObjectDeclarationNode(self, node: ObjectDeclarationNode) -> None:
        cls = self._table.global_scope.lookup(node.class_name)
        if cls is None or not isinstance(cls, ClassSymbol):
            self._error(f"Undefined class '{node.class_name}'", node)
        self.generic_visit(node)

    def visit_MethodInvokeNode(self, node: MethodInvokeNode) -> None:
        if node.object_name is not None:
            obj = self._scope.lookup(node.object_name)
            if obj is None:
                self._error(f"Undefined object '{node.object_name}'", node)
        self.generic_visit(node)


class ObjectSymbolBuilderMixin:
    """Mixin that adds object-related symbol building to ``SymbolBuilder``."""

    def visit_ObjectDeclarationNode(self, node: ObjectDeclarationNode) -> None:
        sym = ObjectSymbol(
            name=node.object_name,
            node=node,
            class_name=node.class_name,
        )
        self._scope.define(sym)
        self.generic_visit(node)
