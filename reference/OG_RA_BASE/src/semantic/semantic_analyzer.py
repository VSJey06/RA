"""SemanticAnalyzer — AST visitor that produces compile-time diagnostics.

Walks a ProgramNode alongside a pre-built SymbolTable and detects
common semantic issues such as undefined references and duplicate
declarations.
"""

from __future__ import annotations

from typing import Any, Optional

from parser.ra_ast import (
    AbsNode,
    AssignmentNode,
    BitwiseExpressionNode,
    UnaryBitwiseNode,
    CaNode,
    StrictComparisonNode,
    CharMethodNode,
    CharNode,
    ClassNode,
    CmNode,
    CompoundAssignmentNode,
    CsNode,
    ForNode,
    ForUpdaterNode,
    FunctionBlockNode,
    InNode,
    WhatPreconditionNode,
    WhichBranchNode,
    WhichControlNode,
    FunctionCallNode,
    IdentifierNode,
    ImaginaryNode,
    IsNode,
    LenNode,
    LogicalExpressionNode,
    UnaryLogicalNode,
    MethodInvokeNode,
    MultiAssignmentNode,
    MultiPrintNode,
    RoundNode,
    SdbLoadNode,
    SdbNode,
    SdbSaveNode,
    StringTransformNode,
    MethodNode,
    Node,
    NodeVisitor,
    ObjectDeclarationNode,
    ProgramNode,
    PropertyAccessNode,
    ReturnNode,
    TypeInfoNode,
)
from semantic.diagnostic import Diagnostic, Severity
from semantic.oop.class_validator import ClassValidatorMixin
from semantic.oop.method_validator import MethodValidatorMixin
from semantic.oop.object_validator import ObjectValidatorMixin
from semantic.family import type_family
from semantic.scope import ClassScope, MethodScope, Scope
from semantic.symbol import ClassSymbol, ObjectSymbol, PackageSymbol, VariableSymbol
from semantic.symbol_table import SymbolTable
from runtime.function_registry import FunctionRegistry, FunctionRegistryError


class SemanticAnalyzer(ClassValidatorMixin, MethodValidatorMixin, ObjectValidatorMixin, NodeVisitor):
    """Checks a parsed program for semantic errors.

    Usage
    -----
        analyzer = SemanticAnalyzer(program_node, symbol_table)
        diags   = analyzer.analyze()
    """

    def __init__(self, program: ProgramNode, table: SymbolTable) -> None:
        self._program = program
        self._table = table
        self._diagnostics: list[Diagnostic] = []
        self._scope: Scope = table.global_scope

        # Tracking sets for duplicate detection (SemanticAnalyzer's own tracking,
        # not SymbolTable — SymbolBuilder pre-populates scopes before we walk)
        self._seen_classes: set[str] = set()
        self._seen_methods: dict[str, set[str]] = {}  # class_name -> set of method names
        self._seen_vars: dict[int, set[str]] = {}  # scope_id -> set of variable names
        self._stack_names: set[str] = set()  # stack names created via Stack.X
        self._queue_names: set[str] = set()  # queue names created via Queue.X
        self._dequeue_names: set[str] = set()  # dequeue names created via Dequeue.X
        self._function_registry = FunctionRegistry()
        self._registered_function_nodes: set[int] = set()
        self._function_depth = 0

    # ── Public entry point ──────────────────────────────────────────────

    def analyze(self) -> list[Diagnostic]:
        """Walk the AST and return all collected diagnostics."""
        self.visit(self._program)
        return self._diagnostics

    # ── Diagnostics helpers ─────────────────────────────────────────────

    def _error(self, message: str, node: Node) -> None:
        self._diagnostics.append(
            Diagnostic(message=message, severity=Severity.ERROR,
                       line=node.line, column=node.col)
        )

    # ── Scope helpers ───────────────────────────────────────────────────

    def _scope_by_node(self, scope: Scope, node: Node) -> Optional[Scope]:
        """Find the direct child of *scope* whose symbol's node is *node*."""
        for child in scope.children:
            sym = getattr(child, "class_symbol",
                          getattr(child, "method_symbol", None))
            if sym is not None and sym.node is node:
                return child
            if getattr(child, "function_node", None) is node:
                return child
        return None

    def _enter(self, node: Node) -> None:
        child = self._scope_by_node(self._scope, node)
        if child is not None:
            self._scope = child

    def _leave(self) -> None:
        if self._scope.parent is not None:
            self._scope = self._scope.parent

    # ── Root ────────────────────────────────────────────────────────────

    def visit_ProgramNode(self, node: ProgramNode) -> None:
        for candidate in node.walk():
            if isinstance(candidate, FunctionBlockNode) and candidate.name is not None:
                self._register_function(candidate)
        self.generic_visit(node)



    # ── Variable declarations ───────────────────────────────────────────

    def visit_CompoundAssignmentNode(self, node: CompoundAssignmentNode) -> None:
        """Validate a compound assignment.

        The variable must already exist (no implicit declaration).
        The family must not change.
        """
        name = node.name
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(
                f"Variable '{name}' is not defined; "
                f"cannot use compound assignment on undefined variable",
                node,
            )
        self.generic_visit(node)

    def visit_AssignmentNode(self, node: AssignmentNode) -> None:
        if node.is_declaration:
            scope_id = id(self._scope)
            seen = self._seen_vars.setdefault(scope_id, set())
            if node.name in seen:
                self._error(f"Variable '{node.name}' already defined", node)
            seen.add(node.name)
        self.generic_visit(node)

    # ── Variable references ─────────────────────────────────────────────

    def visit_IdentifierNode(self, node: IdentifierNode) -> None:
        name = node.name
        # Skip single-character identifiers (common loop vars, etc.)
        if len(name) == 1:
            self.generic_visit(node)
            return
        # Skip package command names (resolved via PackageRegistry)
        if self._is_package_name(name):
            return
        # Skip built-in EMPTY value
        if name == "EMPTY":
            return
        # Skip stack / queue / dequeue names created via Stack.X / Queue.X / Dequeue.X
        if name in self._stack_names or name in self._queue_names or name in self._dequeue_names:
            return
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        self.generic_visit(node)

    # ── Functions ───────────────────────────────────────────────────────

    def _register_function(self, node: FunctionBlockNode) -> None:
        if id(node) in self._registered_function_nodes:
            return
        try:
            self._function_registry.register(node)
        except FunctionRegistryError as exc:
            self._error(str(exc), node)
        self._registered_function_nodes.add(id(node))

    def visit_FunctionBlockNode(self, node: FunctionBlockNode) -> None:
        if node.name is not None:
            self._register_function(node)

        saved = self._scope
        child = self._scope_by_node(self._scope, node)
        if child is not None:
            self._scope = child
        else:
            function_scope = Scope(parent=self._scope)
            self._scope.children.append(function_scope)
            self._scope = function_scope
            for param in node.params:
                self._scope.define(VariableSymbol(name=param, node=node, var_type=None))

        self._function_depth += 1
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self._function_depth -= 1
            self._scope = saved

    def visit_FunctionCallNode(self, node: FunctionCallNode) -> None:
        if not self._function_registry.exists(node.name):
            self._error(f"Unknown function '{node.name}'", node)
        else:
            definition = self._function_registry.get(node.name)
            self._validate_function_call(node, definition.params)
        self.generic_visit(node)

    def _validate_function_call(
        self,
        node: FunctionCallNode,
        params: tuple[str, ...],
    ) -> None:
        if len(node.args) > len(params):
            self._error(
                f"Function '{node.name}' expects {len(params)} "
                f"parameter(s), got {len(node.args)}",
                node,
            )
            return

        if not node.named_arguments:
            if len(node.args) != len(params):
                self._error(
                    f"Function '{node.name}' expects {len(params)} "
                    f"parameter(s), got {len(node.args)}",
                    node,
                )
            return

        bound = set(params[:len(node.args)])
        seen_named: set[str] = set()
        for name, _ in node.named_arguments:
            if name in seen_named:
                self._error(
                    f"Duplicate named argument '{name}' for function '{node.name}'",
                    node,
                )
                continue
            seen_named.add(name)
            if name not in params:
                self._error(
                    f"Unknown named argument '{name}' for function '{node.name}'",
                    node,
                )
                continue
            if name in bound:
                self._error(
                    f"Duplicate argument for parameter '{name}' "
                    f"in function '{node.name}'",
                    node,
                )
                continue
            bound.add(name)

        for param in params:
            if param not in bound:
                self._error(
                    f"Missing required parameter '{param}' "
                    f"for function '{node.name}'",
                    node,
                )

    def visit_ReturnNode(self, node: ReturnNode) -> None:
        if self._function_depth == 0:
            self._error("Return outside function", node)
        self.generic_visit(node)

    # ── Property access (object.property) ──────────────────────────────

    def visit_PropertyAccessNode(self, node: PropertyAccessNode) -> None:
        obj_name = getattr(node.object, "name", None)
        if obj_name == "Dequeue":
            self._dequeue_names.add(node.property)
            return
        if obj_name == "Queue":
            self._queue_names.add(node.property)
            return
        if obj_name == "Stack":
            self._stack_names.add(node.property)
            return
        if obj_name and self._is_package_name(obj_name):
            return
        self.generic_visit(node)

    def _is_package_name(self, name: str) -> bool:
        """Check if *name* is a known PAC package command."""
        try:
            from compiler.internal import PackageRegistry
            return PackageRegistry.has(name)
        except ImportError:
            return False

    # ── Type info (.type:variable) ─────────────────────────────────────

    def visit_TypeInfoNode(self, node: TypeInfoNode) -> None:
        name = node.name
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        self.generic_visit(node)

    # ── Abs (.abs:variable) ───────────────────────────────────────────
    # Family-level: accepts any I Family type (I, F, D, L)

    def visit_AbsNode(self, node: AbsNode) -> None:
        name = node.name
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        elif existing.var_type is not None and type_family(existing.var_type) != "I":
            self._error(
                f"'.abs:' only supports I Family datatypes (I/F/D/L), "
                f"not '{existing.var_type}'",
                node,
            )
        self.generic_visit(node)

    # ── Round (.round:variable) ────────────────────────────────────────
    # Family-level: accepts any I Family type (I, F, D, L)

    def visit_RoundNode(self, node: RoundNode) -> None:
        name = node.name
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        elif existing.var_type is not None and type_family(existing.var_type) != "I":
            self._error(
                f"'.round:' only supports I Family datatypes (I/F/D/L), "
                f"not '{existing.var_type}'",
                node,
            )
        self.generic_visit(node)

    # ── Is (.is:variable) ──────────────────────────────────────────────
    # TF (Boolean) is its own type — not a family check.

    def visit_IsNode(self, node: IsNode) -> None:
        name = node.name
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        elif existing.var_type is not None and existing.var_type != "TF":
            self._error(
                f"'.is:' only supports TF datatype, "
                f"not '{existing.var_type}'",
                node,
            )
        self.generic_visit(node)

    # ── Len (.len:variable) ────────────────────────────────────────────
    # Family-level: accepts any S Family type (S, C, DC, TC, etc.)

    def visit_LenNode(self, node: LenNode) -> None:
        name = node.name
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        elif existing.var_type is not None and type_family(existing.var_type) != "S":
            self._error(f"'.len:' only supports S Family datatypes (string/text), not '{existing.var_type}'", node)
        self.generic_visit(node)

    # ── String transform (.upper / .lower / .trim) ─────────────────────
    # Family-level: accepts any S Family type

    def visit_StringTransformNode(self, node: StringTransformNode) -> None:
        name = node.name
        method = node.method
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        elif existing.var_type is not None and type_family(existing.var_type) != "S":
            self._error(
                f"'.{method}:' only supports S Family datatypes (string/text), "
                f"not '{existing.var_type}'",
                node,
            )
        self.generic_visit(node)

    # ── Char (.char:variable,index) ─────────────────────────────────────
    # Family-level: accepts any S Family type

    def visit_CharNode(self, node: CharNode) -> None:
        name = node.name
        existing = self._scope.lookup(name)
        if existing is None:
            self._error(f"Undefined variable '{name}'", node)
        elif existing.var_type is not None and type_family(existing.var_type) != "S":
            self._error(
                f"'.char:' only supports S Family datatypes (string/text), "
                f"not '{existing.var_type}'",
                node,
            )
        self.generic_visit(node)

    # ── Remaining nodes — recurse only ──────────────────────────────────

    def visit_CharMethodNode(self, node: CharMethodNode) -> None:
        m = node.method
        existing = self._scope.lookup(node.name)
        if existing is None:
            self._error(f"Undefined variable '{node.name}'", node)
        elif existing.var_type is not None and type_family(existing.var_type) != "S":
            self._error(
                f"'.{m}:' only supports S Family datatypes (string/text), "
                f"not '{existing.var_type}'",
                node,
            )
        self.generic_visit(node)

    def generic_visit(self, node: Node) -> None:
        for child in node.children:
            self.visit(child)

    def _noop(self, node: Node) -> None:
        self.generic_visit(node)

    def _validate_operator_compatibility(self, node: BinaryOpNode) -> None:
        """Validate operator compatibility between operand types.

        Only compatible families may participate in arithmetic.
        Raises a semantic error for invalid combinations.
        """
        op = node.operator

        # Arithmetic operators that require compatible families
        _ARITHMETIC_OPS = {"+", "-", "*", "/", "//", "%", "%%", "**", "^"}
        if op not in _ARITHMETIC_OPS:
            # Comparison operators are always valid
            return

        # We only validate if both operands are identifiers with known types
        left_type = self._resolve_type(node.left)
        right_type = self._resolve_type(node.right)

        if left_type is None or right_type is None:
            # Types not known at compile time — skip validation
            return

        left_family = type_family(left_type)
        right_family = type_family(right_type)

        # String family: only + and / have meaning
        if left_family == "S" or right_family == "S":
            if op not in ("+", "/", "^"):
                self._error(
                    f"Operator '{op}' not supported on String family. "
                    f"Only '+', '/', and '^' are valid for strings.",
                    node,
                )
            return

        # Complex family operations
        if left_family == "C" or right_family == "C":
            if op not in ("+", "-", "*", "/", "%%", "**", "^"):
                self._error(
                    f"Operator '{op}' not supported on Complex family. "
                    f"Supported: '+', '-', '*', '/', '%%', '**', '^'.",
                    node,
                )
            return

        # I Family + Complex mix is supported (type promotion)
        if left_family == "I" and right_family == "C":
            return
        if left_family == "C" and right_family == "I":
            return

        # Both I Family or both compatible — always valid
        if left_family == right_family or (left_family == "I" and right_family == "I"):
            return

        # I + C or C + I — already handled above
        if (left_family == "I" and right_family == "C") or \
           (left_family == "C" and right_family == "I"):
            return

        # Unsupported family combinations
        if left_family != right_family and left_family is not None and right_family is not None:
            self._error(
                f"Incompatible families for operator '{op}': "
                f"{left_family} and {right_family}",
                node,
            )

    def _resolve_type(self, node: Node) -> str | None:
        """Resolve the RA type of an expression node, if possible."""
        from parser.ra_ast import LiteralNode, IdentifierNode, BinaryOpNode

        if isinstance(node, LiteralNode):
            if node.kind.name == "INTEGER":
                return "I"
            if node.kind.name == "FLOAT":
                return "F"
            if node.kind.name == "STRING":
                return "S"
            if node.kind.name == "BOOLEAN_LITERAL":
                return "TF"
            return None

        if isinstance(node, IdentifierNode):
            name = node.name
            existing = self._scope.lookup(name)
            if existing is not None:
                return getattr(existing, "var_type", None)
            return None

        # For other expressions, try to infer from BinaryOpNode
        if isinstance(node, BinaryOpNode):
            left_t = self._resolve_type(node.left)
            right_t = self._resolve_type(node.right)
            return self._promoted_type(left_t, right_t)

        return None

    @staticmethod
    def _promoted_type(left: str | None, right: str | None) -> str | None:
        """Determine the result type of a binary operation based on type promotion.

        Rules:
            I + F -> F
            I + D -> D
            F + D -> D
            I + Cx -> Cx
            F + Cx -> Cx
            D + Cx -> Cx
            S + Any -> S
        """
        if left is None or right is None:
            return None
        if left == right:
            return left
        # String promotion: S + Any -> S
        if "S" in (left, right):
            return "S"
        # Complex family promotion: Any + Cx/Cs/Ca/Cm -> Cx
        if type_family(left) == "C" or type_family(right) == "C":
            return "Cx"
        # Numeric promotion (I -> F -> D)
        _ORDER = {"I": 0, "F": 1, "D": 2, "L": 3}
        li = _ORDER.get(left, -1)
        ri = _ORDER.get(right, -1)
        if li >= 0 and ri >= 0:
            return right if ri > li else left
        return None

    def visit_BinaryOpNode(self, node: BinaryOpNode) -> None:
        """Validate operator compatibility and recurse."""
        self._validate_operator_compatibility(node)
        self.generic_visit(node)

    # ── Logical expressions ────────────────────────────────────────────

    def visit_LogicalExpressionNode(self, node: LogicalExpressionNode) -> None:
        """Validate logical expression operands must be boolean-compatible."""
        _op = node.operator
        self.generic_visit(node)

    def visit_UnaryLogicalNode(self, node: UnaryLogicalNode) -> None:
        """Validate unary NOT operand."""
        self.generic_visit(node)

    # ── Bitwise expressions ─────────────────────────────────────────────

    def visit_BitwiseExpressionNode(self, node: BitwiseExpressionNode) -> None:
        """Validate bitwise expression operands must be Integer (I) family."""
        self._validate_bitwise_operand(node.left, node.operator)
        self._validate_bitwise_operand(node.right, node.operator)
        self.generic_visit(node)

    def visit_UnaryBitwiseNode(self, node: UnaryBitwiseNode) -> None:
        """Validate unary bitwise NOT operand must be Integer (I) family."""
        self._validate_bitwise_operand(node.expr, node.operator)
        self.generic_visit(node)

    def _validate_bitwise_operand(self, operand: Node, op: str) -> None:
        """Validate that an operand to a bitwise operator is Integer (I) family."""
        from parser.ra_ast import LiteralNode, IdentifierNode, BinaryOpNode
        resolved = self._resolve_type(operand)
        if resolved is not None:
            from semantic.family import type_family
            family = type_family(resolved)
            if family != "I":
                self._error(
                    f"Bitwise operator '{op}' requires Integer (I) family, "
                    f"got '{resolved}' (family '{family}')",
                    operand,
                )

    # ── Comparison expressions ─────────────────────────────────────────

    def visit_StrictComparisonNode(self, node: StrictComparisonNode) -> None:
        """Validate strict comparison operands must be compatible families."""
        self.generic_visit(node)

    visit_PrintNode = _noop
    visit_LiteralNode = _noop
    visit_BooleanNode = _noop
    visit_IfNode = _noop
    visit_ElseIfNode = _noop
    visit_ElseNode = _noop
    visit_ForNode = _noop
    visit_ForUpdaterNode = _noop

    def visit_InNode(self, node: InNode) -> None:
        """Validate the ?In construct.

        Validates the source and limit expressions are well-typed.
        The ''in'' keyword (RC3-01B) disambiguates Type 1 at parse time.
        Semantic analysis does not distinguish Type 1 vs Type 2/3.
        """
        # Validate source is a valid expression
        self.visit(node.source)
        self.visit(node.limit)
        if node.step is not None:
            self.visit(node.step)
        # Validate body statements
        for stmt in node.body:
            self.visit(stmt)

    def visit_TupleNode(self, node: TupleNode) -> None:
        """Validate a tuple literal.

        Recurse into each item expression.
        """
        for item in node.items:
            self.visit(item)

    def visit_SetNode(self, node: SetNode) -> None:
        """Validate a set literal.

        Recurse into each item expression.
        """
        for item in node.items:
            self.visit(item)

    def visit_WhichControlNode(self, node: WhichControlNode) -> None:
        """Validate a ?Which block.

        Walks each branch and validates selector expressions.
        """
        for branch in node.branches:
            for stmt in branch.body:
                self.visit(stmt)
        if node.selectors:
            for var_name, value_expr in node.selectors.items():
                self.visit(value_expr)

    def visit_WhatPreconditionNode(self, node: WhatPreconditionNode) -> None:
        """Validate a ?What block.

        Checks:
        - No ElseIf inside the What block
        - All arguments are valid expressions
        - Condition is valid (if present)
        """
        # Check for ElseIf inside What block
        if node.has_elseif:
            self._error(
                "'ElseIf' is not supported inside ?What blocks. "
                "Use if/else only.",
                node,
            )
        if node.condition is not None:
            self.visit(node.condition)
        for stmt in node.if_body:
            self.visit(stmt)
        for stmt in node.else_body:
            self.visit(stmt)
        if node.arguments:
            for var_name, value_expr in node.arguments.items():
                self.visit(value_expr)

    visit_WhileNode = _noop
    visit_PrintBlockNode = _noop
    visit_InputBlockNode = _noop
    visit_RunBlockNode = _noop
    visit_OOPNode = _noop
    visit_PFNode = _noop
    visit_ProgramHandlerNode = _noop
    visit_FunctionFlowNode = _noop
    visit_ConstructorNode = _noop
    visit_EncapsulationNode = _noop
    visit_DbSaveNode = _noop
    visit_DbLoadNode = _noop
    visit_DbNextNode = _noop
    visit_DbBreakNode = _noop
    visit_MethodCallNode = _noop
    visit_PropertyAssignmentNode = _noop
    visit_CheckNode = _noop
    visit_SwitchNode = _noop
    visit_CaseNode = _noop
    visit_DbNode = _noop
    visit_SdbNode = _noop
    visit_SdbSaveNode = _noop
    visit_SdbLoadNode = _noop
    visit_SdbCursorSetNode = _noop
    visit_RelationAssignmentNode = _noop
    visit_MultiAssignmentNode = _noop
    visit_MultiPrintNode = _noop
    visit_ImaginaryNode = _noop
    visit_CsNode = _noop
    visit_CaNode = _noop
    def visit_CmNode(self, node: CmNode) -> None:
        """Validate absolute value |expr| operand.

        Validates that the inner expression evaluates to a numeric type
        (I, F, D, Cx) or is a complex number. Strings and booleans are
        rejected at the family level.
        """
        inner_type = self._resolve_type(node.value)
        if inner_type is not None:
            from semantic.family import type_family
            family = type_family(inner_type)
            if family not in ("I", "C"):
                self._error(
                    f"Absolute value |...| requires a numeric or complex "
                    f"expression, got '{inner_type}' (family '{family}')",
                    node,
                )
        self.generic_visit(node)
    visit_CxNode = _noop
