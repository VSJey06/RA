"""
ra_ast.py — Abstract Syntax Tree node definitions for the RA language.

Every node guarantees:
  .children   — list of direct child nodes for generic tree traversal
  .line       — 1-based source line where the construct starts
  .auto_close — True when the parser injected an implicit block terminator

Node hierarchy
--------------
  Node  (abstract base)
  ├── Expression nodes
  │   ├── LiteralNode
  │   ├── IdentifierNode
  │   ├── BinaryOpNode
  │   ├── PropertyAccessNode  (re-exported from compiler.oop.ast)
  │   └── BooleanNode
  └── Statement / block nodes
      ├── ProgramNode
      ├── RunBlockNode    # .run: … r.close
      ├── FunctionBlockNode  # .fun.name: … f.close
      ├── FunctionCallNode   # .name / .name.args
      ├── OOPNode         # OOP (re-exported from compiler.oop.ast)
      ├── ConstructorNode # Con: … con.close (re-exported from compiler.oop.ast)
      ├── EncapsulationNode  # En: … en.close (re-exported from compiler.oop.ast)
      ├── DbNode
      ├── ClassNode       (re-exported from compiler.oop.ast)
      ├── MethodNode      (re-exported from compiler.oop.ast)
      ├── ObjectDeclarationNode      (re-exported from compiler.oop.ast)
      ├── IfNode
      ├── ElseIfNode
      ├── ElseNode
      ├── ForNode
      ├── WhileNode
      ├── InNode         # ?In loop
   ├── AssignmentNode
   ├── RelationAssignmentNode
   ├── PropertyAssignmentNode  (re-exported from compiler.oop.ast)
   ├── MethodCallNode     (re-exported from compiler.oop.ast)
   ├── TypeInfoNode
       ├── ReturnNode
       ├── PrintNode
       ├── DbNextNode
       └── DbBreakNode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from lexer.tokens import TokenType
from parser.ast_core import Node, NodeVisitor
from parser.source_location import SourceLocation

# OOP AST nodes (extracted to dedicated package)
from compiler.oop.ast import (
    ClassNode,
    ConstructorNode,
    EncapsulationNode,
    InheritanceNode,
    MethodCallNode,
    MethodInvokeNode,
    MethodNode,
    ObjectDeclarationNode,
    OOPNode,
    PropertyAccessNode,
    PropertyAssignmentNode,
)


# ===========================================================================
# Expression nodes
# ===========================================================================

@dataclass
class LiteralNode(Node):
    """A compile-time constant: a STRING or INTEGER literal.

    Attributes
    ----------
    value : str | int  — Python-native value of the literal.
    kind  : TokenType  — STRING or INTEGER.
    was_measurement : bool — True when the literal came from a numeric
                             suffix expression (e.g. ``5K``, ``3Cr``).
                             ``False`` for plain numeric literals.
    """

    value: Any
    kind:  TokenType
    was_measurement: bool = False

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"LiteralNode(kind={self.kind.name}, value={self.value!r}, "
            f"line={self.line}was_measurement={self.was_measurement})"
        )


@dataclass
class IdentifierNode(Node):
    """A reference to a named variable or symbol.

    Attributes
    ----------
    name : str — bare identifier text (e.g. ``"age"``, ``"Person"``).
    """

    name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"IdentifierNode(name={self.name!r}, line={self.line})"


@dataclass
class BinaryOpNode(Node):
    """A binary expression: ``left operator right``.

    Attributes
    ----------
    operator : str  — raw operator text (``"=="``, ``"+"``, ``">="``, ...).
    left     : Node — left-hand operand.
    right    : Node — right-hand operand.
    """

    operator: str
    left:     Node
    right:    Node

    @property
    def children(self) -> list[Node]:
        return [self.left, self.right]

    def __repr__(self) -> str:
        return f"BinaryOpNode(op={self.operator!r}, line={self.line})"


@dataclass
class BooleanNode(Node):
    """A .TF boolean evaluation suffix: ``expr.TF``

    Evaluates *expr* and returns the native Python bool.

    Attributes
    ----------
    expr : Node — the expression whose result becomes a boolean.
    """

    expr: Node

    @property
    def children(self) -> list[Node]:
        return [self.expr]

    def __repr__(self) -> str:
        return (
            f"BooleanNode(line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class LogicalExpressionNode(Node):
    """A binary logical expression: ``left AND right``, ``left OR right``, etc.

    Normalises all keyword and symbol forms into one of the canonical
    operator strings:

        "and"  — logical AND
        "or"   — logical OR
        "xor"  — logical XOR
        "nor"  — logical NOR
        "nand" — logical NAND
        "xnor" — logical XNOR

    Attributes
    ----------
    operator : str  — canonical operator (``"and"``, ``"or"``, ``"xor"``, ...).
    left     : Node — left-hand operand.
    right    : Node — right-hand operand (None for unary NOT).
    """

    operator: str
    left:     Node
    right:    Optional[Node] = None

    @property
    def children(self) -> list[Node]:
        result: list[Node] = [self.left]
        if self.right is not None:
            result.append(self.right)
        return result

    def __repr__(self) -> str:
        if self.right is not None:
            return f"LogicalExpressionNode(op={self.operator!r}, line={self.line})"
        return f"UnaryLogicalNode(op={self.operator!r}, line={self.line})"


@dataclass
class UnaryLogicalNode(Node):
    """A unary logical expression: ``NOT expr``, ``!expr``

    Normalises ``not``, ``NOT``, and ``!`` into operator ``"not"``.

    Attributes
    ----------
    operator : str  — canonical operator (``"not"``).
    expr     : Node — the expression to negate.
    """

    operator: str
    expr:    Node

    @property
    def children(self) -> list[Node]:
        return [self.expr]

    def __repr__(self) -> str:
        return f"UnaryLogicalNode(op={self.operator!r}, line={self.line})"


@dataclass
class BitwiseExpressionNode(Node):
    """A binary bitwise expression: ``left band right``, ``left bor right``, etc.

    Normalises all keyword and symbol forms into one of the canonical
    operator strings:

        "band"    — bitwise AND
        "bor"     — bitwise OR
        "bxor"    — bitwise XOR
        "blshift" — bitwise left shift
        "brshift" — bitwise right shift

    Attributes
    ----------
    operator : str  — canonical operator (``"band"``, ``"bor"``, ...).
    left     : Node — left-hand operand.
    right    : Node — right-hand operand.
    """

    operator: str
    left:     Node
    right:    Node

    @property
    def children(self) -> list[Node]:
        return [self.left, self.right]

    def __repr__(self) -> str:
        return f"BitwiseExpressionNode(op={self.operator!r}, line={self.line})"


@dataclass
class UnaryBitwiseNode(Node):
    """A unary bitwise expression: ``bnot expr``, ``~expr``

    Normalises ``bnot``, ``BNOT``, and ``~`` into operator ``"bnot"``.

    Attributes
    ----------
    operator : str  — canonical operator (``"bnot"``).
    expr     : Node — the expression to negate.
    """

    operator: str
    expr:    Node

    @property
    def children(self) -> list[Node]:
        return [self.expr]

    def __repr__(self) -> str:
        return f"UnaryBitwiseNode(op={self.operator!r}, line={self.line})"


@dataclass
class StrictComparisonNode(Node):
    """A strict comparison: ``left === right``

    Compares both value AND family. No implicit type promotion.

    Attributes
    ----------
    left     : Node — left-hand operand.
    right    : Node — right-hand operand.
    """

    left:     Node
    right:    Node

    @property
    def children(self) -> list[Node]:
        return [self.left, self.right]

    def __repr__(self) -> str:
        return f"StrictComparisonNode(line={self.line})"


# ComparisonFlowNode has been REMOVED as of SPRINT 24A.
# The old comparison flow operators (-->, <--) are now reserved for
# branch execution markers inside !If statements (pre_action/post_action).
# See IfNode.pre_action and IfNode.post_action.

# ===========================================================================
# Program root
# ===========================================================================

@dataclass
class ProgramNode(Node):
    """The root of the AST. Contains every top-level statement in order.

    Attributes
    ----------
    body : list[Node] — ordered top-level statements.
    """

    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"ProgramNode(statements={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class RunBlockNode(Node):
    """An immediate execution block: ``.run: ... r.close``

    ``auto_close=True`` means the parser injected an implicit ``r.close``.

    Attributes
    ----------
    body : list[Node] — statements executed when the block is entered.
    """

    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"RunBlockNode(stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class FunctionBlockNode(Node):
    """A function declaration: ``.fun.name: ... f.close``

    ``name=None`` represents the deprecated legacy immediate block
    ``.fun: ... f.close``.  Named functions are registered and executed only
    when called.

    Attributes
    ----------
    name : str | None — canonical function name.
    params : list[str] — parameter names bound into local scope on call.
    body : list[Node] — statements executed inside the local scope.
    """

    name: Optional[str] = None
    params: list[str] = field(default_factory=list)
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        signature = self.name if self.name is not None else "<legacy>"
        if self.params:
            signature += "." + ",".join(self.params)
        return (
            f"FunctionBlockNode(name={signature!r}, stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class PrintBlockNode(Node):
    """A Print block: ``Print: ...`` or ``Print.<Name>: ...``

    A top-level block that owns print/output statements.
    ``auto_close=True`` means the parser closed it implicitly.

    Syntax
    ------
        Print:
            body...

        Print.Greeting:
            body...

        Print.Greeting, a, b, c:
            body...

    Attributes
    ----------
    name   : str | None      — optional block name (from ``Print.<Name>:``).
    params : list[str]       — optional parameter names (from ``Print.Name, a, b, c:``).
    body   : list[Node]      — statements inside the block.
    """

    name: Optional[str] = None
    params: list[str] = field(default_factory=list)
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        label = self.name if self.name is not None else "<unnamed>"
        return (
            f"PrintBlockNode(name={label!r}, stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class InputBlockNode(Node):
    """An Input block: ``Ip: ...`` or ``Ip.<Name>: ...``

    A top-level block that owns input statements.
    ``auto_close=True`` means the parser closed it implicitly.

    Syntax
    ------
        Ip:
            body...

        Ip.UserInput:
            body...

        Ip.Name, a, b, c:
            body...

        Ip.Name, a, b, c:
            I.a
            S.b
            D.d
        ip.close

    Attributes
    ----------
    name   : str | None      — optional block name (from ``Ip.<Name>:``).
    params : list[str]       — optional parameter names (from ``Ip.Name, a, b, c:``).
    body   : list[Node]      — statements inside the block.
    """

    name: Optional[str] = None
    params: list[str] = field(default_factory=list)
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        label = self.name if self.name is not None else "<unnamed>"
        return (
            f"InputBlockNode(name={label!r}, stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class FunctionCallNode(Node):
    """A function call expression/statement: ``.name`` or ``.name.args``."""

    name: str
    args: list[Node] = field(default_factory=list)
    named_arguments: list[tuple[str, Node]] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return [*self.args, *(value for _, value in self.named_arguments)]

    @property
    def positional_arguments(self) -> list[Node]:
        return self.args

    def __repr__(self) -> str:
        return (
            f"FunctionCallNode(name={self.name!r}, args={len(self.args)}, "
            f"named={len(self.named_arguments)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class PFNode(Node):
    """Activates the built-in PF (Program Flow) library: ``PF``

    A single-word statement that enables pH and fF blocks.
    """

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"PFNode(line={self.line})"


@dataclass
class ProgramHandlerNode(Node):
    """A Program Handler block: ``pH: ... pH.close``

    ``auto_close=True`` means the parser injected an implicit close.

    Attributes
    ----------
    body : list[Node] — registered references (classes, objects, methods).
    """

    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"ProgramHandlerNode(items={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class FunctionFlowNode(Node):
    """A Function Flow block: ``fF: ... f.close``

    ``auto_close=True`` means the parser injected an implicit close.

    Attributes
    ----------
    body   : list[Node] — ordered method-call statements to execute.
    target : str | None — explicit pH binding (e.g. ``"M.Login"``),
                          or ``None`` for Mode A (unbound).
    """

    body:   list[Node] = field(default_factory=list)
    target: Optional[str] = None

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"FunctionFlowNode(calls={len(self.body)}, "
            f"target={self.target!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class PriorityHandlerNode(Node):
    """A CF Priority Handler block: ``pH.<Name>: ... pH.close`` (RC3-08J)

    Stores ordered fF references — does NOT contain executable code.

    Syntax::

        pH.user:
            fF.call
            fF.enter
        pH.close

    Attributes
    ----------
    name           : str        — pH block name (e.g. ``"user"``).
    flow_references : list[str] — ordered list of fF block names to execute.
    """

    name: str = ""
    flow_references: list[str] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"PriorityHandlerNode(name={self.name!r}, refs={self.flow_references}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class FlowFragmentNode(Node):
    """A CF Flow Fragment block: ``fF.<Name>: ... fF.close`` (RC3-08J)

    Contains actual executable instructions.

    Syntax::

        fF.call:
            ken.User
        fF.close

    Attributes
    ----------
    name : str        — fF block name (e.g. ``"call"``).
    body : list[Node] — executable statements.
    """

    name: str = ""
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"FlowFragmentNode(name={self.name!r}, stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


# ===========================================================================
# Error-handling / switch nodes
# ===========================================================================

@dataclass
class CheckNode(Node):
    """An error-handling block: ``Check: … Valid: … Invalid: … Check.close``

    ``auto_close=True`` means the parser injected an implicit ``Check.close``.

    Attributes
    ----------
    body        : list[Node] — the checked statements.
    valid_body  : list[Node] — executed when *body* succeeds.
    invalid_body : list[Node] — executed when *body* raises an error.
    """

    body:         list[Node] = field(default_factory=list)
    valid_body:   list[Node] = field(default_factory=list)
    invalid_body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return [*self.body, *self.valid_body, *self.invalid_body]

    def __repr__(self) -> str:
        return (
            f"CheckNode(stmts={len(self.body)}, "
            f"valid={len(self.valid_body)}, "
            f"invalid={len(self.invalid_body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class CaseNode(Node):
    """A single case branch inside a ``SwitchNode``.

    Attributes
    ----------
    condition : Node        — the value to compare against the key.
    body      : list[Node]  — statements to execute on match.
    """

    condition: Node
    body:      list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return [self.condition, *self.body]

    def __repr__(self) -> str:
        return (
            f"CaseNode(line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class SwitchNode(Node):
    """A switch / case block: ``Key.value: … c.cond: … def: … Key.close``

    Attributes
    ----------
    value        : Node          — the key expression.
    cases        : list[CaseNode] — ordered case branches.
    default_body : list[Node]    — fallback when no case matches.
    """

    value:        Node
    cases:        list[CaseNode] = field(default_factory=list)
    default_body: list[Node]     = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return [self.value, *self.cases, *self.default_body]

    def __repr__(self) -> str:
        return (
            f"SwitchNode(cases={len(self.cases)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


# ===========================================================================
# Block / scope nodes
# ===========================================================================

@dataclass
class DbNode(Node):
    """A database block: ``Db: ... db.close``

    ``auto_close=True`` means the parser injected an implicit ``db.close``
    because the source omitted it.

    Attributes
    ----------
    name : str        — connection alias (``"db"`` or named like ``"Personal"``).
    body : list[Node] — statements executed inside the database context.
    """

    name: str
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"DbNode(name={self.name!r}, body_stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class DbSaveNode(Node):
    """A database save command: ``Db.<name>.save``

    Attributes
    ----------
    database_name : str — name of the database to persist.
    """

    database_name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"DbSaveNode(database={self.database_name!r}, "
            f"line={self.line})"
        )


@dataclass
class DbLoadNode(Node):
    """A database load command: ``Db.<name>.load``

    Attributes
    ----------
    database_name : str — name of the database to load.
    """

    database_name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"DbLoadNode(database={self.database_name!r}, "
            f"line={self.line})"
        )


# ===========================================================================
# What Block (Type Decision Engine) nodes
# ===========================================================================

@dataclass
class WhatBranchNode(Node):
    """A single type-check branch inside a ``WhatNode``.

    Attributes
    ----------
    var_type   : str       — the RA type to check (e.g. ``"I"``, ``"F"``, ``"Str"``).
    body       : list[Node] — statements to execute on type match.
    is_default : bool       — ``True`` for the ``!else`` default branch.
    """

    var_type: str
    body: list[Node] = field(default_factory=list)
    is_default: bool = False

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"WhatBranchNode(type={self.var_type!r}, default={self.is_default}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class WhatNode(Node):
    """A What Block (Type Decision Engine).

    Evaluates the datatype of a variable and dispatches to the matching
    typed branch.  Uses the Property Engine for ``.type`` dispatch.

    Syntax
    ------
        !What variable :
            !i variable == I :
                body ...
            #
            !e variable == F :
                body ...
            #
            !else :
                body ...
            #
        #

    Attributes
    ----------
    variable : str              — the variable name whose type to check.
    branches : list[WhatBranchNode] — ordered type-check branches.
    """

    variable: str
    branches: list[WhatBranchNode] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        result: list[Node] = []
        for branch in self.branches:
            result.append(branch)
        return result

    @property
    def has_default(self) -> bool:
        return any(b.is_default for b in self.branches)

    def __repr__(self) -> str:
        return (
            f"WhatNode(var={self.variable!r}, branches={len(self.branches)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


# ===========================================================================
# Control-flow nodes
# ===========================================================================

@dataclass
class WhichBranchNode(Node):
    """A single branch inside a ``WhichControlNode`` (RC3-03A).

    Each branch is controlled by a named variable (from For/While/In).
    The selector matches against this variable name.

    Attributes
    ----------
    variable    : str          — controlling variable name (e.g. ``"i"``, ``"j"``).
    body        : list[Node]   — statements in this branch.
    branch_type : str          — the type of branch (``"For"``, ``"While"``, ``"In"``, etc.).
    branch_node : Node | None  — the actual ForNode/WhileNode/InNode if applicable.
    """

    variable: str
    body: list[Node] = field(default_factory=list)
    branch_type: str = ""
    branch_node: Optional[Node] = None

    @property
    def children(self) -> list[Node]:
        result: list[Node] = []
        result.extend(self.body)
        return result

    def __repr__(self) -> str:
        return (
            f"WhichBranchNode(var={self.variable!r}, type={self.branch_type!r}, "
            f"stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class WhichControlNode(Node):
    """A ?Which selection control-flow block (RC3-03A).

    Contains multiple candidate branches, each identified by a controlling
    variable name.  Selectors determine which branches execute — only
    branches whose controlling variable matches a selector are run.

    Syntax
    ------
        ? Which:
            For.i = 0, 5:
                p i
            #
            For.j = 0, 2:
                p j
            #
        #. i = 1, j = 2

    RC3-08J extension — named Which controller:

        ? Which.User:
            pH.user:
                fF.call
                fF.enter
            pH.close
            fF.call:
                ken.User
            fF.close
        #.user

    Attributes
    ----------
    name             : str | None          — optional Which name (e.g. ``"User"``).
    branches         : list[WhichBranchNode] — candidate branches in source order.
    selectors        : dict[str, Node] | None — selector variable -> value expression.
    priority_handlers : list[PriorityHandlerNode] — pH blocks (CF extension).
    flow_fragments   : list[FlowFragmentNode]     — fF blocks (CF extension).
    closure_argument  : Node | None        — the #. argument expression (CF extension).
    """

    name: Optional[str] = None
    branches: list[WhichBranchNode] = field(default_factory=list)
    selectors: Optional[dict[str, Node]] = None
    priority_handlers: list[PriorityHandlerNode] = field(default_factory=list)
    flow_fragments: list[FlowFragmentNode] = field(default_factory=list)
    closure_argument: Optional[Node] = None
    dispatch_var_name: Optional[str] = None

    @property
    def children(self) -> list[Node]:
        result: list[Node] = []
        for branch in self.branches:
            result.extend(branch.body)
        return result

    def __repr__(self) -> str:
        label = self.name if self.name else "<unnamed>"
        return (
            f"WhichControlNode(name={label!r}, branches={len(self.branches)}, "
            f"selectors={len(self.selectors or {})}, "
            f"phs={len(self.priority_handlers)}, ffs={len(self.flow_fragments)}, "
            f"dispatch_var={self.dispatch_var_name!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class WhatPreconditionNode(Node):
    """A ?What precondition control-flow block (RC3-03A).

    Checks a condition before executing candidate branches.
    Arguments are supplied via the closing ``#.`` syntax and bound
    into scope before the condition is evaluated.

    Syntax
    ------
        ? What:
            if condition:
                body...
            #
            else
                body...
            #
        #. variable = value

    Attributes
    ----------
    if_body    : list[Node]          — statements in the if branch.
    else_body  : list[Node]          — statements in the else branch (may be empty).
    arguments  : dict[str, Node]     — argument variable -> value expression.
    condition  : Node | None         — the if condition expression.
    """

    if_body: list[Node] = field(default_factory=list)
    else_body: list[Node] = field(default_factory=list)
    arguments: Optional[dict[str, Node]] = None
    condition: Optional[Node] = None

    @property
    def children(self) -> list[Node]:
        result: list[Node] = []
        if self.condition is not None:
            result.append(self.condition)
        result.extend(self.if_body)
        result.extend(self.else_body)
        return result

    @property
    def has_else(self) -> bool:
        return bool(self.else_body)

    @property
    def has_elseif(self) -> bool:
        """Check if the if_body contains any ElseIfNode.

        If ElseIf is found inside a What block, a semantic error should
        be raised.
        """
        for stmt in self.if_body:
            from parser.ra_ast import ElseIfNode
            if isinstance(stmt, ElseIfNode):
                return True
            # Also check nested inside IfNode
            if isinstance(stmt, IfNode):
                if stmt.has_elseifs:
                    return True
        return False

    def __repr__(self) -> str:
        return (
            f"WhatPreconditionNode(has_else={self.has_else}, "
            f"args={len(self.arguments or {})}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class ElseNode(Node):
    """The else branch of an ``IfNode``.

    Attributes
    ----------
    body : list[Node] — statements executed when no condition is truthy.
    """

    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"ElseNode(body_stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class IfNode(Node):
    """A conditional branch with optional elseif and else chains.

    Supports optional pre-action (executed after condition succeeds
    but before body) and post-action (executed after body but before
    leaving the branch) via the ``-->`` and ``<--`` operators.

    Attributes
    ----------
    condition   : Node              — boolean guard expression.
    then_body   : list[Node]        — statements when condition is truthy.
    elseifs     : list[ElseIfNode]  — elseif branches (empty if none).
    else_node   : ElseNode | None   — else branch (None when absent).
    pre_action  : list[Node] | None — executed after condition succeeds,
                                      before body (``-->``).
    post_action : list[Node] | None — executed after body,
                                      before leaving branch (``<--``).
    """

    condition: Node
    then_body: list[Node] = field(default_factory=list)
    elseifs:   list[ElseIfNode] = field(default_factory=list)
    else_node: Optional[ElseNode] = None
    pre_action:  Optional[list[Node]] = None
    post_action: Optional[list[Node]] = None
    tree_flow:   bool = False

    @property
    def children(self) -> list[Node]:
        result: list[Node] = [self.condition]
        if self.pre_action:
            result.extend(self.pre_action)
        result.extend(self.then_body)
        if self.post_action:
            result.extend(self.post_action)
        result.extend(self.elseifs)
        if self.else_node is not None:
            result.append(self.else_node)
        return result

    @property
    def has_else(self) -> bool:
        return self.else_node is not None

    @property
    def has_elseifs(self) -> bool:
        return bool(self.elseifs)

    def __repr__(self) -> str:
        parts = [f"has_else={self.has_else}", f"elseifs={len(self.elseifs)}"]
        if self.pre_action:
            parts.append(f"pre_action={len(self.pre_action)}")
        if self.post_action:
            parts.append(f"post_action={len(self.post_action)}")
        parts.append(f"line={self.line}")
        parts.append(f"auto_close={self.auto_close}")
        return f"IfNode({', '.join(parts)})"


@dataclass
class ElseIfNode(Node):
    """An elseif branch inside an ``IfNode``.

    Attributes
    ----------
    condition : Node        — boolean guard expression.
    body      : list[Node]  — statements when this branch is taken.
    """

    condition: Node
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return [self.condition, *self.body]

    def __repr__(self) -> str:
        return (
            f"ElseIfNode(line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class ForNode(Node):
    """A for loop in RA.

    Canonical forms (RC2-06B, RC2-06B Contextual Updater):

    Syntax 1 — Pre-declared value:
        i = 0
        ? For.i < 10, n+:
            p i
        #

    Syntax 2 — Inline declaration:
        ? For.i = 0, i < 10, n+:
            p i
        #

    Nested forms:
        for.j < 10, n+:
            p j
        #

        for.j = 0, j < 10, n+:
            p j
        #

    Attributes
    ----------
    variable    : str              — loop variable name.
    condition   : Node             — loop guard expression.
    iteration   : Node             — ForUpdaterNode (n+/+n/n-/-n).
    initializer : Node | None      — None for Syntax 1 (pre-declared),
                                       AssignmentNode for Syntax 2 (inline).
    body        : list[Node]       — loop body statements.
    """

    variable: str
    condition: Node
    iteration: Node
    initializer: Optional[Node] = None
    body:     list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        result: list[Node] = []
        if self.initializer is not None:
            result.append(self.initializer)
        result.append(self.condition)
        result.append(self.iteration)
        result.extend(self.body)
        return result

    @property
    def is_inline(self) -> bool:
        """True for Syntax 2 (inline declaration)."""
        return self.initializer is not None

    def __repr__(self) -> str:
        form = "inline" if self.is_inline else "pre-declared"
        return (
            f"ForNode(var={self.variable!r}, form={form}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class ForUpdaterNode(Node):
    """A contextual For loop updater: ``n+``, ``+n``, ``n-``, ``-n``

    These forms are recognized ONLY in the For update argument position.
    Plain ``n`` remains an ordinary identifier everywhere else.

    The updater acts on the current For loop's control variable,
    not on a variable literally named ``n``.

    Updater semantics
    ------------------
    ``n+`` (suffix increment):
        current For control variable = current For control variable + 1
    ``+n`` (prefix increment):
        current For control variable = 1 + current For control variable
    ``n-`` (suffix decrement):
        current For control variable = current For control variable - 1
    ``-n`` (prefix decrement):
        current For control variable = 1 - current For control variable
    ``n+2`` (suffix increment by 2):
        current For control variable = current For control variable + 2
    ``n-2`` (suffix decrement by 2):
        current For control variable = current For control variable - 2

    The default contextual count value represented by updater-form ``n`` is ``1``.

    Attributes
    ----------
    operator : str  — ``"+"`` (increment) or ``"-"`` (decrement).
    position : str  — ``"suffix"`` (n+, n-) or ``"prefix"`` (+n, -n).
    amount   : int  — the increment/decrement amount (default 1).
    """

    operator: str   # "+" or "-"
    position: str   # "suffix" or "prefix"
    amount: int = 1

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        form = f"n{self.operator}" if self.position == "suffix" else f"{self.operator}n"
        if self.amount != 1:
            form += str(self.amount)
        return (
            f"ForUpdaterNode(form={form!r}, amount={self.amount}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class WhileNode(Node):
    """A while loop in RA.

    Canonical forms (RC2-06B/RC2-06C):

    Syntax 1 — Pre-declared with contextual updater:
        i = 0
        ? While.i < 10, n+:
            p i
        #

    Syntax 2 — Inline declaration with manual increment:
        ? While.i = 0, i <= 5:
            p i
            i++
        #

    Attributes
    ----------
    condition   : Node               — loop guard expression.
    variable    : str                — loop variable name (used for auto-increment
                                       or extracted from condition, empty if unknown).
    iteration   : Node | None        — ForUpdaterNode (Syntax 1, contextual updater),
                                        None for Syntax 2 (manual inc in body).
    initializer : Node | None        — None for Syntax 1 (pre-declared),
                                        AssignmentNode for Syntax 2 (inline).
    body        : list[Node]         — loop body statements.
    """

    condition: Node
    variable: str = ""
    iteration: Optional[Node] = None
    initializer: Optional[Node] = None
    body:      list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        result: list[Node] = [self.condition]
        if self.iteration is not None:
            result.append(self.iteration)
        if self.initializer is not None:
            result.append(self.initializer)
        result.extend(self.body)
        return result

    @property
    def has_auto_iteration(self) -> bool:
        """True for Syntax 1 (has auto iteration value)."""
        return self.iteration is not None

    @property
    def is_inline(self) -> bool:
        """True for Syntax 2 (inline declaration)."""
        return self.initializer is not None

    def __repr__(self) -> str:
        parts = [f"line={self.line}"]
        if self.is_inline:
            parts.append("form=inline")
        elif self.has_auto_iteration:
            parts.append("form=auto")
        else:
            parts.append("form=pre-declared")
        if self.variable:
            parts.append(f"var={self.variable!r}")
        parts.append(f"auto_close={self.auto_close}")
        return f"WhileNode({', '.join(parts)})"


# ===========================================================================
# DoWhileNode — ?Do Loop (RC3-08A)
# ===========================================================================

@dataclass
class DoWhileNode(Node):
    """A do-while loop in RA: ``? Do: body #. while: condition, args``

    Executes the body FIRST, then checks the post-condition.
    The body is guaranteed to execute at least once.

    Syntax
    ------
        i = -10
        ? Do:
            p i
        #. while: i < 0, i = -10

    Attributes
    ----------
    body        : list[Node]       — loop body statements.
    condition   : Node | None      — the while condition expression.
    arguments   : dict[str, Node]  — argument variable -> value expression
                                       (evaluated before first iteration,
                                        AND re-evaluated after each iteration).
    variable    : str              — loop variable name (from condition or declarations).
    updater_args : set[str]        — argument names whose values use the ``n+<num>``
                                      contextual updater pattern.  These are NOT
                                      bound before the first iteration — only
                                      re-evaluated after each iteration.
    """

    body: list[Node] = field(default_factory=list)
    condition: Optional[Node] = None
    arguments: Optional[dict[str, Node]] = None
    variable: str = ""
    updater_args: set[str] = field(default_factory=set)

    @property
    def children(self) -> list[Node]:
        result: list[Node] = []
        if self.condition is not None:
            result.append(self.condition)
        result.extend(self.body)
        return result

    def __repr__(self) -> str:
        return (
            f"DoWhileNode(stmts={len(self.body)}, "
            f"has_condition={self.condition is not None}, "
            f"args={len(self.arguments or {})}, "
            f"updaters={len(self.updater_args)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


# ===========================================================================
# InNode — ?In Loop (RC3-01A — Unified Loop Family)
# ===========================================================================

@dataclass
class ListNode(Node):
    """A list literal value: ``[1, 2, 3]``

    Used by the ?In Loop family and other constructs that
    accept inline collection literals.

    Attributes
    ----------
    items : list[Node] — the elements of the list.
    """

    items: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.items

    def __repr__(self) -> str:
        return (
            f"ListNode(items={len(self.items)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class TupleNode(Node):
    """A tuple literal value: ``(1, 2, 3)``   (RC3-02A)

    Tuples are immutable — fixed-size, ordered collections.

    Attributes
    ----------
    items : list[Node] — the elements of the tuple.
    """

    items: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.items

    def __repr__(self) -> str:
        return (
            f"TupleNode(items={len(self.items)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class SetNode(Node):
    """A set literal value: ``Set{1, 2, 3}``   (RC3-02A)

    Sets are unordered collections with unique elements.
    Duplicate values are automatically removed at runtime.

    Syntax
    ------
        colors = Set{
            Red,
            Green,
            Blue
        }

    Attributes
    ----------
    items : list[Node] — the elements of the set.
    """

    items: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.items

    def __repr__(self) -> str:
        return (
            f"SetNode(items={len(self.items)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class InNode(Node):
    """An ?In loop: ``? In.variable = expr1, expr2[, expr3]: body #``

    Unified RA Loop Family member (RC3-01A). Uses the same canonical loop
    architecture as For and While — no second execution engine.

    Three forms (RC3-01B syntax):

      Type 1 — Membership Check (``in`` keyword):
          ? In.i = value in container:
              body
          #
          Evaluates ``value in container``. Variable receives Boolean result.
          Body executes exactly once (if membership is True).

      Type 2 — Range Iteration (comma separator):
          ? In.i = start, end:
              body
          #
          Iterates from start (inclusive) to end (exclusive) with step=1.

      Type 3 — Range Iteration With Step (comma separator):
          ? In.i = start, end, step:
              body
          #
          Iterates from start (inclusive) to end (exclusive) with user step.

    The ``in`` keyword (RC3-01B) disambiguates Type 1 membership from
    Type 2/3 range iteration at parse time. Previously the comma-based
    syntax ``value, container`` was ambiguous with ``start, end``.

    Runtime detection of Type 1 vs Type 2:
      - If limit evaluates to a list → Type 1 (membership)
      - If both source and limit are numeric → Type 2 (range)
      - If step is present → Type 3 (always range with step)

    Attributes
    ----------
    variable : str        — loop/member variable name.
    source   : Node       — Type 1: value to check; Type 2/3: start value.
    limit    : Node       — Type 1: container expression; Type 2/3: end (exclusive).
    step     : Node | None — Type 3: user-supplied step (None for Type 1/2).
    body     : list[Node]  — loop/body statements.
    """

    variable: str
    source:   Node
    limit:    Node
    step:     Optional[Node] = None
    body:     list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        result: list[Node] = [self.source, self.limit]
        if self.step is not None:
            result.append(self.step)
        result.extend(self.body)
        return result

    def __repr__(self) -> str:
        parts = [f"var={self.variable!r}", f"line={self.line}"]
        if self.step is not None:
            parts.append("has_step")
        parts.append(f"auto_close={self.auto_close}")
        return f"InNode({', '.join(parts)})"


# ===========================================================================
# Statement nodes
# ===========================================================================

@dataclass
class AssignmentNode(Node):
    """A variable assignment, optionally preceded by a type keyword.

    Examples in RA source
    ---------------------
        S name = "Alice"   -> var_type=TokenType.S
        I age  = 30        -> var_type=TokenType.I
        L items = myList   -> var_type=TokenType.L
        x = 99             -> var_type=None  (plain re-assignment)

    Attributes
    ----------
    var_type : TokenType | None — S / I / L, or None for re-assignment.
    name     : str              — target variable name.
    value    : Node             — right-hand side expression.
    """

    var_type: Optional[TokenType]
    name:     str
    value:    Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    @property
    def is_declaration(self) -> bool:
        """True when a type keyword is present (first assignment)."""
        return self.var_type is not None

    @property
    def type_name(self) -> str:
        """Human-readable type label, or ``'~'`` for plain assignment."""
        return self.var_type.name if self.var_type else "~"

    def __repr__(self) -> str:
        return (
            f"AssignmentNode(type={self.type_name}, name={self.name!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class CompoundAssignmentNode(Node):
    """A compound assignment: ``name += expr``, ``name *= expr``, etc.

    Examples
    --------
        age += 5         -> operator="+="
        total *= 2       -> operator="*="
        name += "World"  -> operator="+="  (string concatenation)

    Attributes
    ----------
    name     : str   — target variable name.
    operator : str   — compound operator text ("+=", "-=", "*=", "/=", etc.).
    value    : Node  — right-hand side expression.
    """

    name:     str
    operator: str
    value:    Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return (
            f"CompoundAssignmentNode(op={self.operator!r}, name={self.name!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class MultiAssignmentNode(Node):
    """A multi-variable declaration: ``I a, b, c = 1, 2, 3``

    Attributes
    ----------
    var_type : TokenType — the type keyword (Cx, Cs, Ca, Cm, I, S, L, etc.).
    names    : list[str] — the variable names.
    values   : list[Node] — the corresponding value expressions.
    """

    var_type: TokenType
    names:   list[str]
    values:  list[Node]

    @property
    def children(self) -> list[Node]:
        return self.values

    @property
    def type_name(self) -> str:
        return self.var_type.name

    def __repr__(self) -> str:
        return (
            f"MultiAssignmentNode(type={self.type_name}, "
            f"names={self.names!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class RelationAssignmentNode(Node):
    """A typed relation assignment: ``S.prop.entity : value``

    Attributes
    ----------
    var_type      : TokenType — S, I, or L.
    property_name : str       — relation / property name.
    entity_name   : str       — entity identifier.
    value         : Node      — assigned expression.
    """

    var_type:      TokenType
    property_name: str
    entity_name:   str
    value:         Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    @property
    def type_name(self) -> str:
        return self.var_type.name

    def __repr__(self) -> str:
        return (
            f"RelationAssignmentNode(type={self.type_name}, "
            f"prop={self.property_name!r}, entity={self.entity_name!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )



@dataclass
class TypeInfoNode(Node):
    """A .type: query: ``.type:variable``

    Returns the RA type name (I, S, TF) of the queried variable.

    Attributes
    ----------
    name : str — the variable name to query.
    """

    name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"TypeInfoNode(name={self.name!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class LenNode(Node):
    """A .len: query: ``.len:variable``

    Returns the character count of the queried String variable.

    Attributes
    ----------
    name : str — the variable name to query.
    """

    name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"LenNode(name={self.name!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class AbsNode(Node):
    """A .abs: query: ``.abs:variable``

    Returns the absolute value of the queried numeric (I) variable.

    Attributes
    ----------
    name : str — the variable name to query.
    """

    name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"AbsNode(name={self.name!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class RoundNode(Node):
    """A .round: query: ``.round:variable``

    Returns the nearest whole number of the queried numeric (I) variable.

    Attributes
    ----------
    name : str — the variable name to query.
    """

    name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"RoundNode(name={self.name!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class IsNode(Node):
    """A .is: query: ``.is:variable``

    Returns the boolean state of the queried TF variable.

    Attributes
    ----------
    name : str — the variable name to query.
    """

    name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"IsNode(name={self.name!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class StringTransformNode(Node):
    """A string-transform query: ``.upper:variable`` / ``.lower:variable`` / ``.trim:variable``

    Returns the transformed String (uppercase, lowercase, or trimmed).

    Attributes
    ----------
    name   : str — the variable name to transform.
    method : str — the operation (``upper``, ``lower``, or ``trim``).
    """

    name: str
    method: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"StringTransformNode(name={self.name!r}, method={self.method!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class CharNode(Node):
    """A .char: query: ``.char:variable,index``

    Returns the character at the given index in a String variable.

    Attributes
    ----------
    name  : str — the variable name to query.
    index : int — zero-based index of the character.
    """

    name: str
    index: int

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"CharNode(name={self.name!r}, index={self.index}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class CharMethodNode(Node):
    """A Char method: ``.first:variable`` / ``.last:variable`` / ``.count:variable,"c"``
    / ``.find:variable,"c"`` / ``.replace:variable,"a","b"``

    Attributes
    ----------
    name   : str — the variable name.
    method : str — operation (``first``, ``last``, ``count``, ``find``, ``replace``).
    arg    : str — first string argument (count/find char, or replace old).
    arg2   : str — second string argument (replace new).
    """

    name: str
    method: str
    arg: str = ""
    arg2: str = ""

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"CharMethodNode(name={self.name!r}, method={self.method!r}, "
            f"arg={self.arg!r}, arg2={self.arg2!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )



@dataclass
class HighlightNode(Node):
    """A ^^ highlight expression: ^^ expr

    Converts the expression's string representation to UPPERCASE
    with bold terminal styling.

    Syntax
    ------
        ^^ "hello"     → "HELLO" (bold)
        ^^ name        → uppercase of name's string value (bold)
        ^^ 42          → "42" (bold)

    Attributes
    ----------
    value : Node — the expression to highlight.
    """

    value: Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return (
            f"HighlightNode(line={self.line}, "
            f"auto_close={self.auto_close})"
        )



@dataclass
class ReturnNode(Node):
    """A return statement: ``R.value``

    Attributes
    ----------
    value : Node — the expression whose value is returned.
    """

    value: Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return (
            f"ReturnNode(line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class PrintNode(Node):
    """A print / output statement: ``p expression``

    Attributes
    ----------
    value      : Node — the expression whose representation is printed.
    no_newline : bool — when True, print without trailing newline (``pl``).
    """

    value: Node
    no_newline: bool = False

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return (
            f"PrintNode(line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class MultiPrintNode(Node):
    """A multi-variable print statement: ``p expr1, expr2, ...``

    Attributes
    ----------
    values     : list[Node] — list of expressions to print.
    no_newline : bool — when True, print without trailing newline (``pl``).
    """

    values: list[Node]
    no_newline: bool = False

    @property
    def children(self) -> list[Node]:
        return self.values

    def __repr__(self) -> str:
        return (
            f"MultiPrintNode(count={len(self.values)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class PrintParagraphNode(Node):
    """A paragraph print statement: ``pr expression``

    ``pr`` prints a Paragraph Object.
    Only accepts expressions that evaluate to a Paragraph Object.

    Attributes
    ----------
    value : Node — expression that evaluates to a Paragraph Object.
    """

    value: Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return (
            f"PrintParagraphNode(line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class FormattedPrintNode(Node):
    """A formatted print statement: ``pf \"format %s\" arg1, arg2``

    Uses Python-style ``%`` formatting. The format string is evaluated
    as an expression, then arguments are evaluated and applied.

    Attributes
    ----------
    format_string : Node     — the format template expression (must be string).
    args          : list[Node] — argument expressions to format.
    no_newline    : bool      — when True, print without trailing newline.
    """

    format_string: Node
    args: list[Node] = field(default_factory=list)
    no_newline: bool = False

    @property
    def children(self) -> list[Node]:
        return [self.format_string, *self.args]

    def __repr__(self) -> str:
        return (
            f"FormattedPrintNode(args={len(self.args)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class InputNode(Node):
    """An input expression: reads a value from stdin.

    Attributes
    ----------
    input_type : str — kind of input ("generic", "integer", "char",
                       "dchar", "tchar", "line", "buffer", "builder",
                       "paragraph").
    prompt     : Node | None — optional prompt expression (string).
    var_type   : str | None — declared variable type hint
                               ("I", "F", "S", etc.).
    """

    input_type: str
    prompt:     Node | None = None
    var_type:   str | None = None

    @property
    def children(self) -> list[Node]:
        if self.prompt is not None:
            return [self.prompt]
        return []

    def __repr__(self) -> str:
        return (
            f"InputNode(type={self.input_type!r}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class ParagraphNode(Node):
    """A Paragraph Object: stores multi-line text content.

    Created by ``par.in:`` with paragraph content as a string
    or by ``par.in`` interactive input.

    Attributes
    ----------
    content : Node — the expression containing paragraph text.
    name    : str | None — optional variable name for reference.
    """

    content: Node
    name:    str | None = None

    @property
    def children(self) -> list[Node]:
        return [self.content]

    def __repr__(self) -> str:
        return (
            f"ParagraphNode(line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class DbNextNode(Node):
    """Advance the database cursor: ``db.next``"""

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"DbNextNode(line={self.line})"


@dataclass
class ImaginaryNode(Node):
    """An imaginary number literal: ``5i``, ``-3i``

    Attributes
    ----------
    value : int | float — the magnitude of the imaginary part.
    """

    value: int | float

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"ImaginaryNode(value={self.value!r}, line={self.line})"


@dataclass
class CsNode(Node):
    """A Complex Standard Equation: ``Cs eq = <expr> : <rhs>``

    Represents an equation LHS = RHS in standard form.

    Attributes
    ----------
    value  : Node — the left-hand side expression.
    rhs    : Node — the right-hand side expression.
    name   : str  — the variable name assigned to this equation.
    """

    value: Node
    rhs:   Node
    name:  str = ""

    @property
    def children(self) -> list[Node]:
        return [self.value, self.rhs]

    def __repr__(self) -> str:
        return f"CsNode(name={self.name!r}, line={self.line})"


@dataclass
class CaNode(Node):
    """A Complex Algebra Equation: ``Ca eq = <expr> : <rhs>``

    Represents an algebra equation with complex coefficients.

    Attributes
    ----------
    value  : Node — the left-hand side expression.
    rhs    : Node — the right-hand side expression.
    name   : str  — the variable name assigned to this equation.
    """

    value: Node
    rhs:   Node
    name:  str = ""

    @property
    def children(self) -> list[Node]:
        return [self.value, self.rhs]

    def __repr__(self) -> str:
        return f"CaNode(name={self.name!r}, line={self.line})"


@dataclass
class CmNode(Node):
    """A Complex Magnitude expression: ``|<expr>|``

    Computes sqrt(real² + imag²) of the wrapped expression.

    Attributes
    ----------
    value : Node — the expression whose magnitude to compute.
    """

    value: Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return f"CmNode(line={self.line})"


@dataclass
class CollectionContainerNode(Node):
    """A reserved collection container placeholder: ``[]``

    This node exists solely to reserve the ``[]`` syntax for future
    collection types (Array, List, Queue, Stack, Deque, Tuple,
    Dictionary, Matrix, Tensor).  No runtime implementation yet.

    RESERVED — NOT YET IMPLEMENTED.

    Attributes
    ----------
    body : list[Node] — optional contents (currently unused).
    """

    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"CollectionContainerNode(stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class CxNode(Node):
    """A Complex Number declaration: ``Cx a = 3 + 5i``

    Attributes
    ----------
    name  : str  — the variable name.
    value : Node — the expression to evaluate.
    """

    name:  str
    value: Node

    @property
    def children(self) -> list[Node]:
        return [self.value]

    def __repr__(self) -> str:
        return f"CxNode(name={self.name!r}, line={self.line})"


@dataclass
class SdbNode(Node):
    """A structured database block: ``Sdb.Name: ... sdb.close``

    ``auto_close=True`` means the parser injected an implicit ``sdb.close``
    because the source omitted it.

    Attributes
    ----------
    name : str        — table name (e.g. ``"Employee"``).
    body : list[Node] — field declarations executed inside the table context.
    """

    name: str
    body: list[Node] = field(default_factory=list)

    @property
    def children(self) -> list[Node]:
        return self.body

    def __repr__(self) -> str:
        return (
            f"SdbNode(name={self.name!r}, body_stmts={len(self.body)}, "
            f"line={self.line}, auto_close={self.auto_close})"
        )


@dataclass
class SdbSaveNode(Node):
    """A structured database save command: ``Sdb.<name>.save``

    Attributes
    ----------
    table_name : str — name of the table to persist.
    """

    table_name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"SdbSaveNode(table={self.table_name!r}, "
            f"line={self.line})"
        )


@dataclass
class SdbLoadNode(Node):
    """A structured database load command: ``Sdb.<name>.load``

    Attributes
    ----------
    table_name : str — name of the table to load.
    """

    table_name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"SdbLoadNode(table={self.table_name!r}, "
            f"line={self.line})"
        )


@dataclass
class SdbCursorSetNode(Node):
    """A multi-assignment cursor set: ``Table.at.R,C.set: v1, v2 = a, b``

    The ``set:`` method accepts comma-separated column names followed
    by an ``=`` sign and comma-separated values.

    Attributes
    ----------
    method : str       — the method path (e.g. ``"Users.at.2,1.set"``).
    names  : list[str] — variable/column names for schema validation.
    values : list[Node] — corresponding value expressions.
    """

    method: str
    names: list[str]
    values: list[Node]

    @property
    def children(self) -> list[Node]:
        return self.values

    def __repr__(self) -> str:
        return (
            f"SdbCursorSetNode(method={self.method!r}, "
            f"names={self.names!r}, line={self.line}, "
            f"auto_close={self.auto_close})"
        )


@dataclass
class DbUpdateNode(Node):
    """A database update command: ``Db.<name>.update``

    Reloads the database from disk and merges changes without recreating.

    Attributes
    ----------
    database_name : str — name of the database to update.
    """

    database_name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"DbUpdateNode(database={self.database_name!r}, "
            f"line={self.line})"
        )


@dataclass
class SdbUpdateNode(Node):
    """An Sdb table update command: ``Sdb.<table>.update``

    Reloads the table from disk and merges changes without recreating.

    Attributes
    ----------
    table_name : str — name of the table to update.
    """

    table_name: str

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"SdbUpdateNode(table={self.table_name!r}, "
            f"line={self.line})"
        )


@dataclass
class SdbMoveNode(Node):
    """An Sdb cell move operation: ``Table.move.<row>,<col> : <destRow>,<destCol>``

    Moves a cell value from source to destination. Destination overwritten,
    source cleared.

    Attributes
    ----------
    table_name : str — name of the table.
    src_row    : int — source row (1-based).
    src_col    : int — source column (1-based).
    dest_row   : int — destination row (1-based).
    dest_col   : int — destination column (1-based).
    """

    table_name: str
    src_row: int
    src_col: int
    dest_row: int
    dest_col: int

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"SdbMoveNode(table={self.table_name!r}, "
            f"src=({self.src_row},{self.src_col}), "
            f"dest=({self.dest_row},{self.dest_col}), "
            f"line={self.line})"
        )


@dataclass
class SdbWidthNode(Node):
    """An Sdb column width operation: ``Table.width.<column> : <size>``

    Sets the column width.

    Attributes
    ----------
    table_name : str     — name of the table.
    column     : int|str — column number (1-based) or column name.
    size       : int     — width of the column.
    """

    table_name: str
    column: int | str
    size: int

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"SdbWidthNode(table={self.table_name!r}, "
            f"column={self.column!r}, size={self.size}, "
            f"line={self.line})"
        )


@dataclass
class SdbHeightNode(Node):
    """An Sdb row height operation: ``Table.height.<row> : <size>``

    Sets the row height.

    Attributes
    ----------
    table_name : str — name of the table.
    row        : int — row number (1-based).
    size       : int — height of the row.
    """

    table_name: str
    row: int
    size: int

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return (
            f"SdbHeightNode(table={self.table_name!r}, "
            f"row={self.row}, size={self.size}, "
            f"line={self.line})"
        )


@dataclass
class DbBreakNode(Node):
    """Break out of a database loop: ``db.break``"""

    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"DbBreakNode(line={self.line})"


@dataclass
class BreakNode(Node):
    """A break statement: ``break``      """
    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"BreakNode(line={self.line}, auto_close={self.auto_close})"


@dataclass
class ContinueNode(Node):
    """A continue statement: ``continue``  """
    @property
    def children(self) -> list[Node]:
        return []

    def __repr__(self) -> str:
        return f"ContinueNode(line={self.line}, auto_close={self.auto_close})"


# NodeVisitor is imported from parser.ast_core (see top of file)

# ===========================================================================
# Pretty-printer
# ===========================================================================

def dump(node: Node, indent: int = 0) -> str:
    """Return a multi-line, indented string representation of an AST subtree.

    Usage
    -----
        print(dump(program_node))
    """
    lines = [f"{'  ' * indent}{_summary(node)}"]
    for child in node.children:
        lines.append(dump(child, indent + 1))
    return "\n".join(lines)


def _summary(node: Node) -> str:
    """Compact single-line label including key scalar fields."""
    cls    = type(node).__name__
    parts: list[str] = [f"line={node.line}"]

    match node:
        case LiteralNode():
            parts += [f"kind={node.kind.name}", f"value={node.value!r}"]
        case IdentifierNode():
            parts += [f"name={node.name!r}"]
        case BinaryOpNode():
            parts += [f"op={node.operator!r}"]
        case PropertyAccessNode():
            parts += [f"prop={node.property!r}"]
        case MultiAssignmentNode():
            parts += [f"type={node.type_name}", f"names={node.names!r}"]
        case MultiPrintNode():
            parts += [f"count={len(node.values)}"]
        case ImaginaryNode():
            parts += [f"value={node.value!r}"]
        case CsNode() | CaNode():
            parts += [f"name={node.name!r}"]
        case CmNode():
            parts += []
        case CollectionContainerNode():
            parts += []
        case BooleanNode():
            parts += []
        case ProgramNode():
            parts += [f"stmts={len(node.body)}"]
        case RunBlockNode():
            parts += [f"stmts={len(node.body)}"]
        case FunctionBlockNode():
            if node.name is not None:
                parts += [f"name={node.name!r}", f"params={node.params!r}"]
            parts += [f"stmts={len(node.body)}"]
        case PrintBlockNode():
            label = node.name if node.name else "<unnamed>"
            parts += [f"name={label!r}", f"stmts={len(node.body)}"]
        case InputBlockNode():
            label = node.name if node.name else "<unnamed>"
            parts += [f"name={label!r}", f"stmts={len(node.body)}"]
        case FunctionCallNode():
            parts += [
                f"name={node.name!r}",
                f"args={len(node.args)}",
                f"named={len(node.named_arguments)}",
            ]
        case OOPNode():
            parts += []
        case PFNode():
            parts += []
        case ProgramHandlerNode():
            parts += [f"items={len(node.body)}"]
        case FunctionFlowNode():
            parts += [f"calls={len(node.body)}"]
            if node.target is not None:
                parts += [f"target={node.target!r}"]
        case PriorityHandlerNode():
            parts += [f"name={node.name!r}", f"refs={node.flow_references}"]
        case FlowFragmentNode():
            parts += [f"name={node.name!r}", f"stmts={len(node.body)}"]
        case CheckNode():
            parts += [f"stmts={len(node.body)}",
                      f"valid={len(node.valid_body)}",
                      f"invalid={len(node.invalid_body)}"]
        case SwitchNode():
            parts += [f"cases={len(node.cases)}",
                      f"default={len(node.default_body)}"]
        case CaseNode():
            parts += [f"stmts={len(node.body)}"]
        case ConstructorNode():
            parts += [f"stmts={len(node.body)}"]
        case EncapsulationNode():
            parts += [f"stmts={len(node.body)}"]
        case DbNode():
            parts += [f"name={node.name!r}", f"stmts={len(node.body)}"]
        case DbSaveNode():
            parts += [f"db={node.database_name!r}"]
        case DbLoadNode():
            parts += [f"db={node.database_name!r}"]
        case SdbNode():
            parts += [f"name={node.name!r}", f"stmts={len(node.body)}"]
        case SdbSaveNode():
            parts += [f"table={node.table_name!r}"]
        case SdbLoadNode():
            parts += [f"table={node.table_name!r}"]
        case SdbCursorSetNode():
            parts += [f"method={node.method!r}", f"names={node.names!r}"]
        case ClassNode():
            parts += [f"name={node.name!r}", f"members={len(node.members)}"]
        case MethodNode():
            parts += [f"name={node.name!r}"]
        case ObjectDeclarationNode():
            parts += [f"obj={node.object_name!r}", f"cls={node.class_name!r}"]
        case WhatNode():
            parts += [f"var={node.variable!r}", f"branches={len(node.branches)}"]
        case WhatBranchNode():
            parts += [f"type={node.var_type!r}", f"default={node.is_default}", f"stmts={len(node.body)}"]
        case WhichControlNode():
            label = node.name if node.name else "<unnamed>"
            parts += [f"name={label!r}", f"branches={len(node.branches)}", f"selectors={len(node.selectors or {})}", f"phs={len(node.priority_handlers)}"]
        case WhichBranchNode():
            parts += [f"var={node.variable!r}", f"type={node.branch_type!r}", f"stmts={len(node.body)}"]
        case WhatPreconditionNode():
            parts += [f"has_else={node.has_else}", f"args={len(node.arguments or {})}"]
            if node.condition is not None:
                parts.append("has_condition")
        case IfNode():
            parts += [f"has_else={node.has_else}", f"elseifs={len(node.elseifs)}"]
            if node.tree_flow:
                parts.append("tree_flow=True")
            if node.pre_action:
                parts.append(f"pre_action={len(node.pre_action)}")
            if node.post_action:
                parts.append(f"post_action={len(node.post_action)}")
        case ElseIfNode():
            parts += [f"stmts={len(node.body)}"]
        case ElseNode():
            parts += [f"stmts={len(node.body)}"]
        case ForNode():
            parts += [f"var={node.variable!r}"]
            if node.is_inline:
                parts.append("form=inline")
            else:
                parts.append("form=pre-declared")
            if isinstance(node.iteration, ForUpdaterNode):
                form = f"n{node.iteration.operator}" if node.iteration.position == "suffix" else f"{node.iteration.operator}n"
                parts.append(f"updater={form!r}")
        case ForUpdaterNode():
            form = f"n{node.operator}" if node.position == "suffix" else f"{node.operator}n"
            parts += [f"form={form!r}"]
        case WhileNode():
            parts += [f"line={node.line}"]
            if node.is_inline:
                parts.append("form=inline")
            elif node.has_auto_iteration:
                parts.append("form=auto")
            else:
                parts.append("form=pre-declared")
        case DoWhileNode():
            parts += [f"stmts={len(node.body)}", f"has_condition={node.condition is not None}"]
            if node.arguments:
                parts.append(f"args={len(node.arguments)}")
        case InNode():
            parts += [f"var={node.variable!r}"]
            if node.step is not None:
                parts.append("has_step")
        case AssignmentNode():
            parts += [f"type={node.type_name}", f"name={node.name!r}"]
        case RelationAssignmentNode():
            parts += [f"type={node.type_name}", f"prop={node.property_name!r}", f"entity={node.entity_name!r}"]
        case MethodCallNode():
            parts += [f"method={node.method!r}"]
        case TypeInfoNode():
            parts += [f"name={node.name!r}"]
        case LenNode():
            parts += [f"name={node.name!r}"]
        case AbsNode():
            parts += [f"name={node.name!r}"]
        case RoundNode():
            parts += [f"name={node.name!r}"]
        case IsNode():
            parts += [f"name={node.name!r}"]
        case StringTransformNode():
            parts += [f"name={node.name!r}", f"method={node.method!r}"]
        case CharNode():
            parts += [f"name={node.name!r}", f"index={node.index}"]
        case CharMethodNode():
            parts += [f"name={node.name!r}", f"method={node.method!r}"]
            if node.arg:
                parts.append(f"arg={node.arg!r}")
            if node.arg2:
                parts.append(f"arg2={node.arg2!r}")
        case MethodInvokeNode():
            parts += [f"method={node.method_name!r}"]
            if node.object_name is not None:
                parts += [f"obj={node.object_name!r}"]
        case PropertyAssignmentNode():
            parts += [f"obj={node.object_name!r}", f"prop={node.property_name!r}"]
        case ListNode():
            parts += [f"items={len(node.items)}"]
        case TupleNode():
            parts += [f"items={len(node.items)}"]
        case SetNode():
            parts += [f"items={len(node.items)}"]
        case InputNode():
            parts += [f"input_type={node.input_type!r}"]
            if node.prompt is not None:
                parts.append("has_prompt")
        case ParagraphNode():
            if node.name:
                parts += [f"name={node.name!r}"]
        case PrintParagraphNode():
            parts += []
        case FormattedPrintNode():
            parts += [f"args={len(node.args)}"]

    if node.auto_close:
        parts.append("auto_close=True")

    return f"{cls}({', '.join(parts)})"


# ===========================================================================
# Self-test
# ===========================================================================

if __name__ == "__main__":
    _program = ProgramNode(
        line=1,
        body=[
            ClassNode(
                name="Person",
                line=1,
                members=[
                    AssignmentNode(
                        var_type=TokenType.S,
                        name="name",
                        value=LiteralNode(value="Alice", kind=TokenType.STRING, line=2),
                        line=2,
                    ),
                    AssignmentNode(
                        var_type=TokenType.I,
                        name="age",
                        value=LiteralNode(value=30, kind=TokenType.INTEGER, line=3),
                        line=3,
                    ),
                ],
            ),
            DbNode(
                name="mydb",
                line=5,
                auto_close=True,
                body=[
                    DbNextNode(line=6),
                    DbBreakNode(line=7),
                ],
            ),
            MethodNode(
                name="greet",
                line=9,
                body=[
                    PrintNode(
                        value=PropertyAccessNode(
                            object=IdentifierNode(name="person", line=10),
                            property="name",
                            line=10,
                        ),
                        line=10,
                    ),
                    ReturnNode(
                        value=IdentifierNode(name="result", line=11),
                        line=11,
                    ),
                ],
            ),
            ObjectDeclarationNode(object_name="p", class_name="Person", line=13),
            IfNode(
                condition=BinaryOpNode(
                    operator="==",
                    left=IdentifierNode(name="x", line=14),
                    right=LiteralNode(value=0, kind=TokenType.INTEGER, line=14),
                    line=14,
                ),
                line=14,
                then_body=[
                    PrintNode(
                        value=LiteralNode(value="zero", kind=TokenType.STRING, line=15),
                        line=15,
                    ),
                ],
                elseifs=[
                    ElseIfNode(
                        condition=BinaryOpNode(
                            operator="==",
                            left=IdentifierNode(name="x", line=16),
                            right=LiteralNode(value=1, kind=TokenType.INTEGER, line=16),
                            line=16,
                        ),
                        line=16,
                        body=[
                            PrintNode(
                                value=LiteralNode(value="one", kind=TokenType.STRING, line=17),
                                line=17,
                            ),
                        ],
                    ),
                ],
                else_node=ElseNode(
                    body=[
                        PrintNode(
                            value=LiteralNode(value="other", kind=TokenType.STRING, line=19),
                            line=19,
                        ),
                    ],
                    line=18,
                    auto_close=False,
                ),
            ),
            ForNode(
                variable="i",
                initializer=AssignmentNode(
                    var_type=None, name="i",
                    value=LiteralNode(value=0, kind=TokenType.INTEGER, line=21),
                    line=21,
                ),
                condition=BinaryOpNode(
                    operator="<",
                    left=IdentifierNode(name="i", line=21),
                    right=LiteralNode(value=10, kind=TokenType.INTEGER, line=21),
                    line=21,
                ),
                iteration=LiteralNode(value=1, kind=TokenType.INTEGER, line=21),
                line=21,
                body=[
                    PrintNode(
                        value=IdentifierNode(name="i", line=22),
                        line=22,
                    ),
                ],
            ),
            WhileNode(
                condition=BinaryOpNode(
                    operator=">",
                    left=IdentifierNode(name="x", line=24),
                    right=LiteralNode(value=0, kind=TokenType.INTEGER, line=24),
                    line=24,
                ),
                line=24,
                body=[
                    PrintNode(
                        value=IdentifierNode(name="x", line=25),
                        line=25,
                    ),
                ],
            ),
            MethodCallNode(
                method="calculateTax",
                argument=LiteralNode(value=50000, kind=TokenType.INTEGER, line=27),
                line=27,
            ),
            RelationAssignmentNode(
                var_type=TokenType.I,
                property_name="age",
                entity_name="Jey",
                value=LiteralNode(value=25, kind=TokenType.INTEGER, line=29),
                line=29,
            ),
        ],
    )

    print("=" * 60)
    print("RA AST -- self-test dump")
    print("=" * 60)
    print(dump(_program))

    print()
    print("=" * 60)
    print("walk() -- all nodes in depth-first order")
    print("=" * 60)
    for _n in _program.walk():
        print(f"  {type(_n).__name__:<25} line={_n.line}  auto_close={_n.auto_close}")

    print()
    print("=" * 60)
    print("NodeVisitor -- collect all AssignmentNodes")
    print("=" * 60)

    class AssignmentCollector(NodeVisitor):
        def __init__(self) -> None:
            self.found: list[AssignmentNode] = []

        def visit_AssignmentNode(self, node: AssignmentNode) -> None:
            self.found.append(node)
            self.generic_visit(node)

    _collector = AssignmentCollector()
    _collector.visit(_program)
    for _a in _collector.found:
        print(f"  {_a}")
