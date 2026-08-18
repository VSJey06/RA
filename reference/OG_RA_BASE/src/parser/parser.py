"""
parser.py — Recursive-descent parser for the RA language.

Converts a flat token stream (from the RA tokenizer) into an AST
defined in ``ra_ast.py``.

Grammar summary
---------------

    program      := stmt*

    stmt         := DbBlock | ClassDef | MethodDef | ObjectStmt
                   | PrintStmt | TypedAssign | AssignStmt
                   | MethodCall | IfStmt | ForStmt | WhileStmt
                   | ReturnStmt
                   | DbNextStmt | DbBreakStmt
                   | RunBlock | FunBlock

    RunBlock     := '.run:' {stmt} 'r.close'
    FunBlock     := '.fun:' {stmt} 'f.close'

    SdbBlock     := 'Sdb.Name' ':' {typed-decl} 'sdb.close'
    DbBlock      := 'Db' ':' {stmt} 'db.close'
    ClassDef     := '@Cls.Name' ':' {member}
    MethodDef    := 'M.name' ':' {stmt} '/'
    ObjectStmt   := 'Obj.ClassName' '.' 'VariableName'

    PrintStmt    := 'p' expression
    TypedAssign  := ('S'|'I'|'L') ident [ ('.' ident)+ ] ':' expression
    AssignStmt   := ident '=' expression
    MethodCall   := ident ':' expression

    IfStmt       := '!' 'If.condition' ',' body '#'
                     { '!!' condition ',' body '#' }
                     [ '!' 'Else' body '#' ]

    ForStmt      := '?' 'For.var=start;end' ',' body '#'
    WhileStmt    := '?' 'While.condition' ',' body '#'

    ReturnStmt   := 'R' '.' expression
    DbNextStmt   := 'db.next'
    DbBreakStmt  := 'db.break'

    expression   := primary { '.' ident } { binary_op primary }
    primary      := STRING | INTEGER | FLOAT | IDENTIFIER
    binary_op    := '==' | '!=' | '>' | '<' | '>=' | '<='
                   | '+' | '-' | '*' | '/' | '//' | '%' | '%%'
                   | '**' | '^' | ';'

All block constructs support automatic closure.  When a sibling construct
or structural boundary is encountered instead of the explicit terminator,
the block is closed implicitly and ``auto_close=True`` is set.

    Explicit terminators
    --------------------
        Db block    :  db.close
        Run block   :  r.close
        Fun block   :  f.close
        Class       :  @  (or @.close)
        Method      :  /  (or /.close)
        If / ElseIf :  #
        For / While :  #
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType

# ── Logical keyword types (used by statement dispatcher) ────────────────

_LOGICAL_KEYWORD_TYPES: frozenset[TokenType] = frozenset({
    TokenType.AND_KW, TokenType.OR_KW, TokenType.XOR_KW,
    TokenType.NOR_KW, TokenType.NAND_KW, TokenType.XNOR_KW,
})

# ── Bitwise keyword types ────────────────────────────────────────────────

_BITWISE_KEYWORD_TYPES: frozenset[TokenType] = frozenset({
    TokenType.BAND_KW, TokenType.BOR_KW, TokenType.BXOR_KW,
    TokenType.BLSHIFT_KW, TokenType.BRSHIFT_KW,
})


# ── Compound assignment operator text map ───────────────────────────────

_COMPOUND_ASSIGN_OPS: dict[TokenType, str] = {
    TokenType.PLUS_ASSIGN:   "+=",
    TokenType.MINUS_ASSIGN:  "-=",
    TokenType.STAR_ASSIGN:   "*=",
    TokenType.SLASH_ASSIGN:  "/=",
    TokenType.PERCENT_ASSIGN: "%=",
    TokenType.CARET_ASSIGN:  "^=",
}

# 3-char compound assignment patterns: (first_token, second_token) -> operator text
_COMPOUND_3CHAR: dict[tuple[TokenType, TokenType], str] = {
    (TokenType.DSTAR,   TokenType.ASSIGN): "**=",
    (TokenType.DSLASH,  TokenType.ASSIGN): "//=",
    (TokenType.DPERCENT, TokenType.ASSIGN): "%%=",
}
from parser.source_location import SourceLocation
from EHub.PE.parser_environment import ParserEnvironment
from parser.ra_ast import (
    AbsNode,
    AssignmentNode,
    BitwiseExpressionNode,
    UnaryBitwiseNode,
    CompoundAssignmentNode,
    BinaryOpNode,
    BooleanNode,
    LogicalExpressionNode,
    UnaryLogicalNode,
    StrictComparisonNode,
    CaNode,
    CaseNode,
    CharNode,
    CharMethodNode,
    CheckNode,
    ClassNode,
    CmNode,
    ConstructorNode,
    CsNode,
    CxNode,
    DbBreakNode,
    DbLoadNode,
    DbNextNode,
    DbNode,
    DbSaveNode,
    DbUpdateNode,
    ElseIfNode,
    ElseNode,
    EncapsulationNode,
    ForNode,
    FunctionBlockNode,
    FunctionCallNode,
    FunctionFlowNode,
    PriorityHandlerNode,
    FlowFragmentNode,
    IdentifierNode,
    IfNode,
    ImaginaryNode,
    InputBlockNode,
    InputNode,
    IsNode,
    LenNode,
    LiteralNode,
    MethodCallNode,
    MethodInvokeNode,
    MethodNode,
    MultiAssignmentNode,
    MultiPrintNode,
    Node,
    ObjectDeclarationNode,
    OOPNode,
    PFNode,
    PrintBlockNode,
    PrintNode,
    ProgramHandlerNode,
    ProgramNode,
    PropertyAccessNode,
    PropertyAssignmentNode,
    RelationAssignmentNode,
    ReturnNode,
    RoundNode,
    RunBlockNode,
    SdbCursorSetNode,
    SdbHeightNode,
    SdbLoadNode,
    SdbMoveNode,
    SdbNode,
    SdbSaveNode,
    SdbUpdateNode,
    SdbWidthNode,
    StringTransformNode,
    SwitchNode,
    TypeInfoNode,
    WhatBranchNode,
    WhatNode,
    WhileNode,
)
from compiler.oop.class_parser import ClassParserMixin
from compiler.oop.object_parser import ObjectParserMixin
from compiler.oop.method_parser import MethodParserMixin
from compiler.oop.constructor_parser import ConstructorParserMixin
from compiler.oop.inheritance_parser import InheritanceParserMixin
from EHub.PE.loop_parser_mixin import LoopParserMixin  # import kept for backward compat; no longer in inheritance chain
from EHub.PE.property_parser_mixin import PropertyParserMixin
from EHub.PE.pf_parser_mixin import PFParserMixin
from EHub.PE.parser_blocks import BlockParser
from EHub.PE.parser_decision import DecisionParser


# ===========================================================================
# ParseError
# ===========================================================================

class ParseError(Exception):
    """Raised when the parser encounters a syntax error.

    Attributes
    ----------
    token : Token — the token that triggered the error.
    """

    def __init__(self, message: str, token: Token) -> None:
        self.message = message
        super().__init__(
            f"[line {token.line}] ParseError: {message}, "
            f"got {token.type.name}({token.value!r})"
        )
        self.token = token


# ===========================================================================
# Parser
# ===========================================================================

class Parser(
    ClassParserMixin,
    ObjectParserMixin,
    MethodParserMixin,
    ConstructorParserMixin,
    InheritanceParserMixin,
    PropertyParserMixin,
    PFParserMixin,
):
    """Recursive-descent parser for the RA language.

    Parameters
    ----------
    tokens : list[Token] — flat token stream from ``tokenizer.tokenize()``.
    """

    def __init__(self, tokens: list[Token]) -> None:
        # ── Create the ParserEnvironment (shared state) ──────────────
        from EHub.PE.parser_environment import ParserEnvironment
        self._env = ParserEnvironment(tokens)
        self.tokens = self._env.tokens   # same list ref for mixin compat

        # ── Create the ParserRegistry (shared constants) ─────────────
        from EHub.PE.parser_registry import ParserRegistry
        self._reg = ParserRegistry()

        # ── Create specialized parsers ───────────────────────────────
        from EHub.PE.expression_parser import ExpressionParser
        self._expression = ExpressionParser(self._env, self._reg)

        from EHub.PE.statement_parser import StatementParser
        self._statement = StatementParser(self._env, self._reg)

        from EHub.PE.declaration_parser import DeclarationParser
        self._declaration = DeclarationParser(self._env, self._reg)

        from EHub.PE.database_parser import DatabaseParser
        self._database = DatabaseParser(self._env, self._reg)

        from EHub.PE.utility_parser import UtilityParser
        self._utility = UtilityParser(self._env, self._reg)

        from EHub.PE.parser_blocks import BlockParser
        self._blocks = BlockParser(self._env, self._reg)

        from EHub.PE.parser_decision import DecisionParser
        self._decision = DecisionParser(self._env, self._reg)

        from EHub.PE.parser_loop import LoopParser
        self._loop = LoopParser(self._env, self._reg)

        from EHub.PE.parser_function import FunctionParser
        self._function = FunctionParser(self._env, self._reg)

        # ── Wire cross-references between specialized parsers ────────
        self._expression._dot_stmt_parser = self._statement._parse_dot_stmt
        self._expression._make_input_node_func = self._statement._make_input_node
        self._statement._expression_parser = self._expression
        self._statement._declaration_parser = self._declaration
        self._statement._database_parser = self._database
        self._statement._utility_parser = self._utility
        self._statement._parse_body_func = self._utility.parse_body
        self._statement._parse_at_stmt_callback = self._parse_at_stmt
        self._statement._parse_object_callback = self._parse_object
        self._statement._parse_method_callback = self._parse_method
        self._statement._parse_constructor_callback = self._parse_constructor
        self._statement._parse_encapsulation_callback = self._parse_encapsulation
        self._statement._parse_block_callback = self._blocks
        self._declaration._expression_parser = self._expression
        self._database._parse_body_func = self._utility.parse_body
        self._database._expression_parser = self._expression
        self._blocks._parse_body_func = self._utility.parse_body
        self._blocks._stmt_parser = self._statement
        self._blocks._expression_parser = self._expression
        self._decision._parse_body_func = self._utility.parse_body
        self._decision._expression_parser = self._expression
        self._decision._parse_stmt_callback = self._statement.parse_stmt
        self._statement._parse_decision_callback = self._decision
        self._loop._parse_body_func = self._utility.parse_body
        self._loop._expression_parser = self._expression
        self._loop._stmt_parser = self._statement
        self._statement._parse_loop_callback = self._loop
        self._function._parse_body_func = self._utility.parse_body
        self._function._expression_parser = self._expression
        self._statement._parse_function_callback = self._function
        self._expression._function_parser = self._function
        self._utility._stmt_parser = self._statement

    # ── Properties for mixin compatibility ───────────────────────────

    @property
    def pos(self) -> int:
        """Current token position — delegates to ParserEnvironment."""
        return self._env.pos

    @pos.setter
    def pos(self, value: int) -> None:
        self._env.pos = value

    @property
    def _body_terminators(self) -> frozenset[TokenType]:
        """Body terminators — delegates to ParserEnvironment."""
        return self._env.body_terminators

    @_body_terminators.setter
    def _body_terminators(self, value: frozenset[TokenType]) -> None:
        self._env.body_terminators = value

    @property
    def _in_ff_flow(self) -> bool:
        """FF flow flag — delegates to ParserEnvironment."""
        return self._env.in_ff_flow

    @_in_ff_flow.setter
    def _in_ff_flow(self, value: bool) -> None:
        self._env.in_ff_flow = value

    # ── Token proxy methods (for mixin compatibility) ──────────────────

    def _current(self) -> Token:
        """Return the token at the current position, or an EOF sentinel."""
        return self._env.current()

    def _check(self, *types: TokenType) -> bool:
        """Return True if the current token type matches any of *types*."""
        return self._env.check(*types)

    def _match(self, *types: TokenType) -> Optional[Token]:
        """If the current token matches any of *types*, consume and return it."""
        return self._env.match(*types)

    def _advance(self) -> Token:
        """Consume and return the current token."""
        return self._env.advance()

    def _consume(self, expected: TokenType, message: str) -> Token:
        """Assert the current token is *expected*, consume it, and return it."""
        return self._env.consume(expected, message)

    # ── Source-location helpers ─────────────────────────────────────────

    @staticmethod
    def _loc(node: Node, token: Token) -> Node:
        """Populate *node* with column/end positions from *token* and return it."""
        return ParserEnvironment.loc(node, token)

    @staticmethod
    def _loc_range(
        node: Node,
        start_token: Token,
        end_token: Token | None = None,
    ) -> Node:
        """Populate *node* with location spanning *start_token* … *end_token*."""
        return ParserEnvironment.loc_range(node, start_token, end_token)

    # ── Main entry point ─────────────────────────────────────────────────

    def parse(self) -> ProgramNode:
        """Parse the full token stream into a ``ProgramNode``."""
        body: list[Node] = []
        first_tok = self._current()
        while not self._check(TokenType.EOF):
            stmt = self._parse_stmt()
            if stmt is not None:
                body.append(stmt)
        node = ProgramNode(line=first_tok.line, body=body)
        eof_tok = self._current()
        return self._loc_range(node, first_tok, eof_tok)

    # ── Generic body parser ──────────────────────────────────────────────

    def _parse_body(self, terminators: frozenset[TokenType] = frozenset()) -> list[Node]:
        """Parse a sequence of statements — delegates to UtilityParser."""
        return self._utility.parse_body(terminators=terminators)

    # ── Statement dispatch ───────────────────────────────────────────────

    def _parse_stmt(self) -> Optional[Node]:
        """Dispatch to the appropriate parse method — delegates to StatementParser."""
        return self._statement.parse_stmt()

    # ── Expression parser ───────────────────────────────────────────────

    def _parse_expression(self) -> Node:
        """Parse an expression — delegates to ExpressionParser."""
        return self._expression.parse_expression()

    # ── Delegation methods for mixin compatibility ───────────────────────

    def _parse_db(self, at_tok: Token | None = None) -> Node:
        """Parse a Db block — delegates to DatabaseParser."""
        return self._database.parse_db(at_tok=at_tok)

    def _parse_sdb(self) -> Node:
        """Parse an Sdb block — delegates to DatabaseParser."""
        return self._database.parse_sdb()

    def _parse_typed_assignment(self) -> Node:
        """Parse a typed assignment — delegates to DeclarationParser."""
        return self._declaration.parse_typed_assignment()

    # ── Dot-prefixed statements (.run:, .fun.name:, calls) ────────────────

    def _parse_dot_stmt(self) -> Node:
        """Parse a statement that starts with '.'.

        Supported forms: ``.run:``, ``.fun:``, ``.type:variable``,
        ``.len:variable``, ``.upper:variable``, ``.lower:variable``,
        ``.trim:variable``, ``.char:variable,index``,
        ``.first:variable``, ``.last:variable``,
        ``.count:variable,"c"``, ``.find:variable,"c"``,
        and ``.replace:variable,"a","b"``.
        """
        dot_tok = self._advance()  # consume '.'
        if self._check(TokenType.IDENTIFIER) and self._current().value == "fun":
            self._advance()
            if self._check(TokenType.COLON):
                self._advance()
                return self._parse_function_block(dot_tok)
            if self._check(TokenType.DOT):
                self._advance()
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected function name after '.fun.'",
                )
                params: list[str] = []
                if self._check(TokenType.DOT):
                    self._advance()
                    params = self._parse_function_params(name_tok.value)
                self._consume(
                    TokenType.COLON,
                    "Expected ':' after function declaration",
                )
                return self._parse_function_block(
                    dot_tok, name=name_tok.value, params=params,
                )
            raise ParseError(
                "Expected '.fun.<name>:' or '.fun.<name>.<params>:'",
                dot_tok,
            )

        if (self._check(TokenType.IDENTIFIER)
                and self._current().value in ("run", "type", "len",
                                               "upper", "lower", "trim", "reverse",
                                               "char", "first", "last",
                                               "count", "find", "replace",
                                               "contains", "starts", "ends",
                                               "split", "repeat",
                                                "abs", "round", "is")
                and self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.COLON):
            kind = self._advance().value  # consume identifier
            self._advance()  # consume ':'
            if kind == "run":
                return self._parse_run_block(dot_tok)
            if kind == "fun":
                return self._parse_function_block(dot_tok)
            if kind == "abs":
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.abs:'",
                )
                return AbsNode(name=name_tok.value, line=dot_tok.line)
            if kind == "round":
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.round:'",
                )
                return RoundNode(name=name_tok.value, line=dot_tok.line)
            if kind == "is":
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.is:'",
                )
                return IsNode(name=name_tok.value, line=dot_tok.line)
            if kind == "type":
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.type:'",
                )
                return TypeInfoNode(name=name_tok.value, line=dot_tok.line)
            if kind == "len":
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.len:'",
                )
                return LenNode(name=name_tok.value, line=dot_tok.line)
            if kind in ("upper", "lower", "trim"):
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    f"Expected variable name after '.{kind}:'",
                )
                return StringTransformNode(
                    name=name_tok.value, method=kind, line=dot_tok.line,
                )
            if kind == "char":
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.char:'",
                )
                self._consume(
                    TokenType.COMMA,
                    "Expected ',' after variable name in '.char:variable,index'",
                )
                idx_tok = self._consume(
                    TokenType.INTEGER,
                    "Expected integer index after '.char:variable,'",
                )
                return CharNode(
                    name=name_tok.value,
                    index=idx_tok.value,
                    line=dot_tok.line,
                )
            if kind in ("first", "last"):
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    f"Expected variable name after '.{kind}:'",
                )
                return CharMethodNode(
                    name=name_tok.value, method=kind, line=dot_tok.line,
                )
            if kind in ("count", "find"):
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    f"Expected variable name after '.{kind}:'",
                )
                self._consume(
                    TokenType.COMMA,
                    f"Expected ',' after variable name in '.{kind}:variable,\"c\"'",
                )
                char_tok = self._consume(
                    TokenType.STRING,
                    f"Expected string argument after '.{kind}:variable,'",
                )
                return CharMethodNode(
                    name=name_tok.value, method=kind,
                    arg=char_tok.value, line=dot_tok.line,
                )
            if kind == "replace":
                name_tok = self._consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.replace:'",
                )
                self._consume(
                    TokenType.COMMA,
                    "Expected ',' after variable name in '.replace:variable,\"a\",\"b\"'",
                )
                old_tok = self._consume(
                    TokenType.STRING,
                    "Expected old string after '.replace:variable,'",
                )
                self._consume(
                    TokenType.COMMA,
                    "Expected ',' after old string in '.replace:variable,\"a\",\"b\"'",
                )
                new_tok = self._consume(
                    TokenType.STRING,
                    "Expected new string after '.replace:variable,\"a\",'",
                )
                return CharMethodNode(
                    name=name_tok.value, method="replace",
                    arg=old_tok.value, arg2=new_tok.value,
                    line=dot_tok.line,
                )
        # Handle .in (standalone input without colon)
        if (self._check(TokenType.IDENTIFIER)
                and self._current().value == "in"):
            self._advance()
            node = InputNode(input_type="generic", line=dot_tok.line)
            if self._check(TokenType.COLON):
                self._advance()
                node.prompt = self._parse_expression()
            return node
        # Handle .take (universal inferred input)
        if (self._check(TokenType.IDENTIFIER)
                and self._current().value == "take"):
            self._advance()
            node = InputNode(input_type="take", line=dot_tok.line)
            if self._check(TokenType.COLON):
                self._advance()
                node.prompt = self._parse_expression()
            return node
        if self._check(TokenType.IDENTIFIER):
            return self._parse_function_call(dot_tok)
        raise ParseError(
            "Expected '.run:', '.fun.<name>:', '.type:variable', '.len:variable', "
            "'.upper:variable', '.lower:variable', '.trim:variable', "
            "'.char:variable,index', '.first:variable', '.last:variable', "
            "'.count:variable,\"c\"', '.find:variable,\"c\"', "
            "'.replace:variable,\"a\",\"b\"', '.in', '.take', or '.<function>'",
            dot_tok,
        )

    def _parse_input_stmt(self) -> Node:
        """Parse a statement-level input spec (e.g. ``I.in`` at statement
        level without assignment).

        Returns an InputNode.
        """
        tok = self._advance()
        if tok.value == "par.in":
            if self._check(TokenType.COLON):
                self._advance()
                content = self._parse_expression()
                return ParagraphNode(content=content, line=tok.line)
            return InputNode(input_type="paragraph", line=tok.line)
        node = self._make_input_node(tok.value, tok.line)
        if self._check(TokenType.COLON):
            self._advance()
            node.prompt = self._parse_expression()
        return node

    def _parse_run_block(self, dot_tok: Token) -> RunBlockNode:
        """Parse an immediate execution block:

            .run:
                body...
            r.close
        """
        body = self._parse_body(terminators=frozenset({TokenType.RUN_CLOSE}))
        has_close = self._check(TokenType.RUN_CLOSE)
        if has_close:
            self._advance()
        return RunBlockNode(
            body=body,
            line=dot_tok.line,
            auto_close=not has_close,
        )

    def _parse_check(self) -> CheckNode:
        """Parse an error-handling block:

            Check:
                statements…
            Valid:
                statements…
            Invalid:
                statements…
            Check.close
        """
        tok = self._consume(TokenType.CHECK, "Expected 'Check'")
        self._consume(TokenType.COLON, "Expected ':' after 'Check'")

        body = self._parse_body(terminators=frozenset({
            TokenType.VALID, TokenType.INVALID, TokenType.CHECK_CLOSE,
        }))

        valid_body: list[Node] = []
        if self._check(TokenType.VALID):
            self._advance()
            self._consume(TokenType.COLON, "Expected ':' after 'Valid'")
            valid_body = self._parse_body(terminators=frozenset({
                TokenType.INVALID, TokenType.CHECK_CLOSE,
            }))

        invalid_body: list[Node] = []
        if self._check(TokenType.INVALID):
            self._advance()
            self._consume(TokenType.COLON, "Expected ':' after 'Invalid'")
            invalid_body = self._parse_body(terminators=frozenset({
                TokenType.CHECK_CLOSE,
            }))

        has_close = self._check(TokenType.CHECK_CLOSE)
        if has_close:
            self._advance()

        return CheckNode(
            body=body,
            valid_body=valid_body,
            invalid_body=invalid_body,
            line=tok.line,
            auto_close=not has_close,
        )

    # ── Key / case / def (switch) block ─────────────────────────────────

    def _parse_key(self) -> SwitchNode:
        """Parse a switch block:

            Key.value:
                c.condition:
                    statements…
                c.condition:
                    statements…
                def:
                    statements…
            Key.close
        """
        key_tok = self._consume(TokenType.KEY, "Expected 'Key'")
        self._consume(TokenType.DOT, "Expected '.' after 'Key'")
        value = self._parse_switch_expression()
        self._consume(TokenType.COLON, "Expected ':' after Key value")

        cases: list[CaseNode] = []
        default_body: list[Node] = []

        while not self._check(TokenType.KEY_CLOSE, TokenType.EOF):
            # Check for 'def:' (default case)
            if self._check(TokenType.IDENTIFIER) and self._current().value == "def":
                nxt = self.pos + 1
                if nxt < len(self.tokens) and self.tokens[nxt].type == TokenType.COLON:
                    self._advance()  # consume 'def'
                    self._advance()  # consume ':'
                    default_body = self._parse_body(terminators=frozenset({
                        TokenType.KEY_CLOSE,
                    }))
                    break

            # Check for 'c.condition:' (case)
            if self._check(TokenType.IDENTIFIER) and self._current().value == "c":
                nxt = self.pos + 1
                if nxt < len(self.tokens) and self.tokens[nxt].type == TokenType.DOT:
                    c_tok = self._advance()  # consume 'c'
                    self._advance()  # consume '.'
                    condition = self._parse_switch_expression()
                    self._consume(
                        TokenType.COLON,
                        "Expected ':' after case condition",
                    )
                    case_body = self._parse_key_case_body()
                    cases.append(CaseNode(
                        condition=condition, body=case_body, line=c_tok.line,
                    ))
                    continue

            raise ParseError(
                "Expected case ('c.condition:') or default ('def:') "
                "in Key block",
                self._current(),
            )

        has_close = self._check(TokenType.KEY_CLOSE)
        if has_close:
            self._advance()

        return SwitchNode(
            value=value,
            cases=cases,
            default_body=default_body,
            line=key_tok.line,
            auto_close=not has_close,
        )

    def _parse_key_case_body(self) -> list[Node]:
        """Parse the body of a case inside a Key block.

        Stops at the next ``c.``, ``def:``, or ``Key.close``.
        """
        body: list[Node] = []
        while not self._check(TokenType.EOF):
            if self._check(TokenType.KEY_CLOSE):
                break
            if self._check(TokenType.IDENTIFIER):
                val = self._current().value
                nxt = self.pos + 1
                if nxt < len(self.tokens):
                    nxt_tt = self.tokens[nxt].type
                    if val == "c" and nxt_tt == TokenType.DOT:
                        break
                    if val == "def" and nxt_tt == TokenType.COLON:
                        break
            stmt = self._parse_stmt()
            if stmt is not None:
                body.append(stmt)
        return body

    def _parse_switch_expression(self) -> Node:
        """Parse a switch header expression without consuming a trailing ':'."""
        left = self._parse_primary_chain()
        left = self._parse_binary_rhs(left, left.line)
        if self._check(TokenType.BOOLEAN_TF):
            self._advance()
            left = BooleanNode(expr=left, line=left.line)
        return left

    # ── Program Handler (pH) block ──────────────────────────────────────

    def _parse_db(self, at_tok: Token | None = None) -> Node:
        """Parse a Db block or save command.

        ``at_tok`` is the *optional* ``@`` token if the caller
        (``_parse_at_stmt``) already consumed it; otherwise the stream is
        expected to start with ``Db``.

            Db:              ->  DbNode(name="db")
            Db.Personal:     ->  DbNode(name="Personal")
            Db.Personal.save ->  DbSaveNode(database_name="Personal")
            body...
            db.close
        """
        if at_tok is not None:
            tok = at_tok
            self._consume(TokenType.DB, "Expected 'Db' after '@'")
        else:
            tok = self._consume(TokenType.DB, "Expected 'Db' to open a database block")

        if self._check(TokenType.DOT):
            self._advance()
            name_tok = self._consume(
                TokenType.IDENTIFIER, "Expected database name after 'Db.'",
            )
            db_name = name_tok.value
        else:
            db_name = "db"

        # Db.<name>.save    ->  DbSaveNode
        # Db.<name>.load    ->  DbLoadNode
        # Db.<name>.update  ->  DbUpdateNode
        if self._check(TokenType.DOT):
            self._advance()
            cmd_tok = self._consume(
                TokenType.IDENTIFIER,
                "Expected 'save', 'load', or 'update' after '.'",
            )
            if cmd_tok.value == "save":
                return DbSaveNode(database_name=db_name, line=tok.line)
            if cmd_tok.value == "load":
                return DbLoadNode(database_name=db_name, line=tok.line)
            if cmd_tok.value == "update":
                return DbUpdateNode(database_name=db_name, line=tok.line)
            raise ParseError(
                f"Expected 'save', 'load', or 'update' after '.', got '{cmd_tok.value}'",
                cmd_tok,
            )

        self._consume(TokenType.COLON, "Expected ':' after database name")

        body = self._parse_body(terminators=frozenset({TokenType.DB_CLOSE}))
        has_explicit_close = self._check(TokenType.DB_CLOSE)
        if has_explicit_close:
            self._advance()

        return DbNode(name=db_name, body=body, line=tok.line, auto_close=not has_explicit_close)

    # ── Print statement ──────────────────────────────────────────────────

    def _parse_print(self) -> Node:
        """Parse a print-with-newline statement:

            p expression
            p.expression
            p a, b, c       (multi-variable print)
        """
        tok = self._consume(TokenType.P, "Expected 'p'")
        if (
            self._check(TokenType.DOT)
            and self._current().column == tok.end_column + 1
        ):
            self._advance()
        values = self._parse_print_values()
        if len(values) == 1:
            return PrintNode(value=values[0], line=tok.line, no_newline=False)
        return MultiPrintNode(values=values, line=tok.line, no_newline=False)

    def _parse_print_line(self) -> Node:
        """Parse a print-without-newline statement:

            pl expression
            pl.expression
            pl a, b, c      (multi-variable print)
        """
        tok = self._consume(TokenType.PL, "Expected 'pl'")
        if (
            self._check(TokenType.DOT)
            and self._current().column == tok.end_column + 1
        ):
            self._advance()
        values = self._parse_print_values()
        if len(values) == 1:
            return PrintNode(value=values[0], line=tok.line, no_newline=True)
        return MultiPrintNode(values=values, line=tok.line, no_newline=True)

    def _parse_print_values(self) -> list[Node]:
        """Parse comma-separated print values.

        Returns a list of expression nodes.
        """
        values = [self._parse_expression()]
        while self._check(TokenType.COMMA):
            self._advance()
            values.append(self._parse_expression())
        return values

    def _parse_print_paragraph(self) -> PrintParagraphNode:
        """Parse a paragraph print statement:
            pr expression
            pr.expression
        """
        tok = self._consume(TokenType.PR, "Expected 'pr'")
        if (
            self._check(TokenType.DOT)
            and self._current().column == tok.end_column + 1
        ):
            self._advance()
        value = self._parse_expression()
        return PrintParagraphNode(value=value, line=tok.line)

    # ── Return statement ─────────────────────────────────────────────────

    def _parse_return(self) -> ReturnNode:
        """Parse a return statement:

            R.expression
        """
        r_tok = self._consume(TokenType.R, "Expected 'R' for return statement")
        if (
            self._check(TokenType.DOT)
            and self._current().column == r_tok.end_column + 1
        ):
            self._advance()
        value = self._parse_expression()
        return ReturnNode(value=value, line=r_tok.line)

    # ── Typed assignment (S, I, L, Cx, Cs, Ca, Cm) ───────────────────────

    def _parse_typed_assignment(self) -> Node:
        """Parse a typed assignment or relation assignment:

            S name = value                    ->  AssignmentNode
            S.name : value                    ->  AssignmentNode
            I.age.Jey : value                 ->  RelationAssignmentNode
            I a, b, c = 1, 2, 3              ->  MultiAssignmentNode
            Cx a = 3 + 5i                    ->  AssignmentNode
            Cs eq = expr : rhs                ->  CsNode
            Ca eq = expr : rhs                ->  CaNode
            Cm mag = |expr|                  ->  AssignmentNode with CmNode value
        """
        type_tok = self._advance()

        if not self._check(TokenType.DOT):
            name_tok = self._consume(
                TokenType.IDENTIFIER,
                f"Expected identifier after '{type_tok.value}'",
            )

            # ── Multi-declaration: I a, b, c = 1, 2, 3 ────────────────
            if self._check(TokenType.COMMA):
                names = [name_tok.value]
                while self._check(TokenType.COMMA):
                    self._advance()
                    ntok = self._consume(
                        TokenType.IDENTIFIER,
                        "Expected identifier after ','",
                    )
                    names.append(ntok.value)
                self._consume(
                    TokenType.ASSIGN,
                    "Expected '=' after variable list",
                )
                values = [self._parse_expression()]
                while self._check(TokenType.COMMA):
                    self._advance()
                    values.append(self._parse_expression())
                if len(names) != len(values):
                    raise ParseError(
                        "Variable/value count mismatch: "
                        f"{len(names)} variables but {len(values)} values",
                        type_tok,
                    )
                return MultiAssignmentNode(
                    var_type=type_tok.type,
                    names=names,
                    values=values,
                    line=type_tok.line,
                )

            # ── Cs / Ca equation syntax: Cs eq = expr : rhs ────────────
            if type_tok.type in (TokenType.CS, TokenType.CA):
                self._consume(
                    TokenType.ASSIGN,
                    f"Expected '=' after {type_tok.value} declaration",
                )
                # Parse LHS expression without consuming ':' (method-call syntax)
                lhs = self._parse_primary_chain()
                lhs = self._parse_binary_rhs(lhs, lhs.line)
                # Skip .TF suffix for equations
                if self._check(TokenType.BOOLEAN_TF):
                    self._advance()
                    lhs = BooleanNode(expr=lhs, line=lhs.line)
                self._consume(
                    TokenType.COLON,
                    f"Expected ':' after LHS in {type_tok.value} equation",
                )
                rhs = self._parse_expression()
                if type_tok.type == TokenType.CS:
                    return CsNode(name=name_tok.value, value=lhs, rhs=rhs,
                                  line=type_tok.line)
                else:
                    return CaNode(name=name_tok.value, value=lhs, rhs=rhs,
                                  line=type_tok.line)

            # ── Cm magnitude syntax: Cm mag = |expr| ───────────────────
            if type_tok.type == TokenType.CM:
                self._consume(
                    TokenType.ASSIGN,
                    "Expected '=' after Cm declaration",
                )
                value = self._parse_expression()
                return AssignmentNode(
                    var_type=type_tok.type,
                    name=name_tok.value,
                    value=value,
                    line=type_tok.line,
                )

            # ── Cx complex number syntax: Cx a = expr ──────────────────
            if type_tok.type == TokenType.CX:
                if self._check(TokenType.COLON):
                    self._advance()
                elif self._check(TokenType.ASSIGN):
                    self._advance()
                else:
                    value = LiteralNode(value=0, kind=TokenType.INTEGER, line=type_tok.line)
                    return CxNode(
                        name=name_tok.value,
                        value=value,
                        line=type_tok.line,
                    )
                value = self._parse_expression()
                return CxNode(
                    name=name_tok.value,
                    value=value,
                    line=type_tok.line,
                )

            # ── Standard single assignment ──────────────────────────────
            if self._check(TokenType.COLON):
                self._advance()
                value = self._parse_expression()
            elif self._check(TokenType.ASSIGN):
                self._advance()
                value = self._parse_expression()
            else:
                if type_tok.type == TokenType.I:
                    value = LiteralNode(value=0, kind=TokenType.INTEGER, line=type_tok.line)
                elif type_tok.type == TokenType.F:
                    value = LiteralNode(value=0.0, kind=TokenType.FLOAT, line=type_tok.line)
                elif type_tok.type == TokenType.D:
                    value = LiteralNode(value=0.0, kind=TokenType.FLOAT, line=type_tok.line)
                elif type_tok.type == TokenType.TF:
                    value = LiteralNode(value=False, kind=TokenType.BOOLEAN_LITERAL, line=type_tok.line)
                elif type_tok.type == TokenType.YN_KW:
                    value = LiteralNode(value=False, kind=TokenType.BOOLEAN_LITERAL, line=type_tok.line)
                elif type_tok.type == TokenType.CM:
                    value = LiteralNode(value=0, kind=TokenType.INTEGER, line=type_tok.line)
                else:
                    value = LiteralNode(value=None, kind=TokenType.STRING, line=type_tok.line)
            return AssignmentNode(
                var_type=type_tok.type,
                name=name_tok.value,
                value=value,
                line=type_tok.line,
            )

        parts: list[str] = []
        while self._check(TokenType.DOT):
            self._advance()
            parts.append(
                self._consume(TokenType.IDENTIFIER, "Expected identifier after '.'").value,
            )
        self._consume(TokenType.COLON, "Expected ':' after property path")
        value = self._parse_expression()

        if len(parts) == 1:
            return AssignmentNode(
                var_type=type_tok.type,
                name=parts[0],
                value=value,
                line=type_tok.line,
            )
        if len(parts) > 2:
            raise ParseError(
                "Relation assignment requires exactly one property and one entity "
                "(e.g. 'I.age.Jey : value')",
                type_tok,
            )
        return RelationAssignmentNode(
            var_type=type_tok.type,
            property_name=parts[0],
            entity_name=parts[1],
            value=value,
            line=type_tok.line,
        )

    # ── Identifier statement ─────────────────────────────────────────────

    def _parse_identifier_stmt(self) -> Node:
        """Parse a statement that starts with an identifier or logical keyword.

            id : expr    ->  MethodCallNode
            id = expr    ->  AssignmentNode
            id.run       ->  MethodInvokeNode
            id op expr   ->  BinaryOpNode  (other operators)
            and/or/...   ->  LogicalExpressionNode (binary logical)
            id           ->  bare IdentifierNode
        """
        name_tok = self._advance()
        if self._check(TokenType.COLON):
            self._advance()
            # Alias syntax: ident : Obj.ClassName  →  ObjectDeclarationNode
            if (self._check(TokenType.OBJ)
                    and self.pos + 2 < len(self.tokens)
                    and self.tokens[self.pos + 1].type == TokenType.DOT
                    and self.tokens[self.pos + 2].type == TokenType.IDENTIFIER):
                self._advance()                     # consume Obj
                self._advance()                     # consume .
                cls_tok = self._advance()            # consume ClassName
                return ObjectDeclarationNode(
                    object_name=name_tok.value,
                    class_name=cls_tok.value,
                    line=name_tok.line,
                )
            value = self._parse_expression()
            return MethodCallNode(method=name_tok.value, argument=value, line=name_tok.line)
        # Compound assignment operators: +=, -=, *=, /=, %=, ^=, **=, //=, %%=
        compound_op = self._check_compound_assign()
        if compound_op is not None:
            value = self._parse_expression()
            return CompoundAssignmentNode(
                name=name_tok.value,
                operator=compound_op,
                value=value,
                line=name_tok.line,
            )

        if self._check(TokenType.ASSIGN):
            self._advance()
            value = self._parse_expression()
            return AssignmentNode(
                var_type=None,
                name=name_tok.value,
                value=value,
                line=name_tok.line,
            )
        if self._check(TokenType.DOT):
            dot_tok = self._advance()
            next_tok = self._consume(
                TokenType.IDENTIFIER,
                "Expected identifier after '.'",
            )
            # Global method: name.run
            if next_tok.value == "run":
                return MethodInvokeNode(
                    method_name=name_tok.value, line=name_tok.line,
                )
            # Stack / property operation: name.prop:expr  (e.g. Users.push:10)
            if self._check(TokenType.COLON):
                self._advance()
                arg = self._parse_expression()
                return MethodCallNode(
                    method=f"{name_tok.value}.{next_tok.value}",
                    argument=arg, line=name_tok.line,
                )
            # Property chain: name.prop.subprop / name.prop.N / name.diagonal.x-y
            prop_parts: list[str] = [next_tok.value]
            while self._check(TokenType.DOT):
                self._advance()
                # Coordinate syntax: name.prop.X,Y or name.prop.X,Y:expr
                if (self._current().type in (TokenType.INTEGER, TokenType.IDENTIFIER)
                        and self.pos + 1 < len(self.tokens)
                        and self.tokens[self.pos + 1].type == TokenType.COMMA):
                    x_tok = self._advance()
                    self._consume(TokenType.COMMA, "Expected ',' after coordinate X")
                    y_tok = self._advance()
                    coord = f"{x_tok.value},{y_tok.value}"
                    prop_parts.append(coord)
                    if self._check(TokenType.COLON):
                        self._advance()
                        # Sdb move/width/height detection (coordinate path)
                        if (name_tok.value[:1].isupper()
                                and len(prop_parts) >= 2
                                and prop_parts[0] in ("move", "width", "height")):
                            table_name = name_tok.value
                            prop0 = prop_parts[0]
                            if prop0 == "move":
                                dest_parts = self._parse_coordinate_pair()
                                if dest_parts is not None:
                                    dest_row, dest_col = dest_parts
                                    src_parts = prop_parts[1].split(",")
                                    if len(src_parts) == 2:
                                        return SdbMoveNode(
                                            table_name=table_name,
                                            src_row=int(src_parts[0]),
                                            src_col=int(src_parts[1]),
                                            dest_row=dest_row,
                                            dest_col=dest_col,
                                            line=name_tok.line,
                                        )
                            elif prop0 == "width":
                                col_str = prop_parts[1]
                                try:
                                    col = int(col_str)
                                except ValueError:
                                    col = col_str
                                size_tok = self._consume(
                                    TokenType.INTEGER,
                                    "Expected integer width after ':'",
                                )
                                return SdbWidthNode(
                                    table_name=table_name,
                                    column=col,
                                    size=size_tok.value,
                                    line=name_tok.line,
                                )
                            elif prop0 == "height":
                                row = int(prop_parts[1])
                                size_tok = self._consume(
                                    TokenType.INTEGER,
                                    "Expected integer height after ':'",
                                )
                                return SdbHeightNode(
                                    table_name=table_name,
                                    row=row,
                                    size=size_tok.value,
                                    line=name_tok.line,
                                )
                        # Fallthrough to MethodCallNode
                        arg = self._parse_expression()
                        return MethodCallNode(
                            method=f"{name_tok.value}.{'.'.join(prop_parts)}",
                            argument=arg, line=name_tok.line,
                        )
                    continue
                sub_prop = self._parse_dot_property()
                # Check for special .run termination
                if sub_prop == "run" and len(prop_parts) == 1:
                    return MethodInvokeNode(
                        method_name=prop_parts[0],
                        object_name=name_tok.value,
                        line=name_tok.line,
                    )
                prop_parts.append(sub_prop)
                if self._check(TokenType.COLON):
                    self._advance()
                    method_name = f"{name_tok.value}.{'.'.join(prop_parts)}"
                    # Sdb move/width/height detection
                    if (name_tok.value[:1].isupper()
                            and len(prop_parts) >= 2
                            and prop_parts[0] in ("move", "width", "height")):
                        table_name = name_tok.value
                        prop0 = prop_parts[0]
                        if prop0 == "move":
                            dest_parts = self._parse_coordinate_pair()
                            if dest_parts is not None:
                                dest_row, dest_col = dest_parts
                                src_parts = prop_parts[1].split(",")
                                if len(src_parts) == 2:
                                    return SdbMoveNode(
                                        table_name=table_name,
                                        src_row=int(src_parts[0]),
                                        src_col=int(src_parts[1]),
                                        dest_row=dest_row,
                                        dest_col=dest_col,
                                        line=name_tok.line,
                                    )
                        elif prop0 == "width":
                            col_str = prop_parts[1]
                            try:
                                col = int(col_str)
                            except ValueError:
                                col = col_str
                            size_tok = self._consume(
                                TokenType.INTEGER,
                                "Expected integer width after ':'",
                            )
                            return SdbWidthNode(
                                table_name=table_name,
                                column=col,
                                size=size_tok.value,
                                line=name_tok.line,
                            )
                        elif prop0 == "height":
                            row = int(prop_parts[1])
                            size_tok = self._consume(
                                TokenType.INTEGER,
                                "Expected integer height after ':'",
                            )
                            return SdbHeightNode(
                                table_name=table_name,
                                row=row,
                                size=size_tok.value,
                                line=name_tok.line,
                            )
                    # ── Multi-assignment cursor set: ident, ident = expr, expr
                    #    Also handles single-variable: ident = expr ──
                    if (method_name.endswith(".set")
                            and self._check(TokenType.IDENTIFIER)
                            and self.pos + 1 < len(self.tokens)
                            and self.tokens[self.pos + 1].type
                                in (TokenType.COMMA, TokenType.ASSIGN)):
                        names = [self._advance().value]
                        while self._check(TokenType.COMMA):
                            self._advance()
                            ntok = self._consume(
                                TokenType.IDENTIFIER,
                                "Expected identifier after ','",
                            )
                            names.append(ntok.value)
                        self._consume(
                            TokenType.ASSIGN,
                            "Expected '=' after variable list",
                        )
                        values = [self._parse_expression()]
                        while self._check(TokenType.COMMA):
                            self._advance()
                            values.append(self._parse_expression())
                        if len(names) != len(values):
                            raise ParseError(
                                "Variable/value count mismatch: "
                                f"{len(names)} variables but {len(values)} values",
                                name_tok,
                            )
                        return SdbCursorSetNode(
                            method=method_name,
                            names=names,
                            values=values,
                            line=name_tok.line,
                        )
                    # ── Single-assignment fallthrough ───────────────────────
                    arg = self._parse_expression()
                    return MethodCallNode(
                        method=method_name,
                        argument=arg, line=name_tok.line,
                    )
            if self._in_ff_flow and len(prop_parts) == 1:
                return MethodInvokeNode(
                    method_name=prop_parts[0],
                    object_name=name_tok.value,
                    line=name_tok.line,
                )
            if (name_tok.value[:1].isupper()
                    and prop_parts
                    and prop_parts[0][:1].isupper()
                    and len(prop_parts) > 1):
                raise ParseError(
                    "Expected '.run' after method name",
                    dot_tok,
                )
            return PropertyAccessNode(
                object=IdentifierNode(name=name_tok.value, line=name_tok.line),
                property=".".join(prop_parts),
                line=dot_tok.line,
            )
        left: Node = IdentifierNode(name=name_tok.value, line=name_tok.line)
        return self._parse_binary_rhs(left, name_tok.line)

    # ── Logical unary statement (not / NOT) ────────────────────────────

    def _parse_unary_logical_stmt(self) -> Node:
        """Parse a unary logical statement: ``not expr`` or ``NOT expr``

        The expression result is negated.
        """
        tok = self._advance()  # consume 'not' / 'NOT'
        expr = self._parse_expression()
        return UnaryLogicalNode(operator="not", expr=expr, line=tok.line)

    # ── Unary bitwise statement (bnot / BNOT) ────────────────────────────

    def _parse_unary_bitwise_stmt(self) -> Node:
        """Parse a unary bitwise statement: ``bnot expr`` or ``BNOT expr``

        The expression result is bitwise-NOTed.
        """
        tok = self._advance()  # consume 'bnot' / 'BNOT'
        expr = self._parse_expression()
        return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)

    # ── Unary bitwise NOT statement (~) ─────────────────────────────────

    def _parse_unary_bitwise_not_stmt(self) -> Node:
        """Parse a unary bitwise NOT statement: ``~expr``

        The expression result is bitwise-NOTed.
        """
        tok = self._advance()  # consume '~'
        expr = self._parse_expression()
        return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)

    # ── Check compound assignment operator ────────────────────────────

    def _check_compound_assign(self) -> str | None:
        """Check for a compound assignment operator at the current position.

        Returns the operator text (e.g. ``"+="``) if found, or ``None``.
        Handles both 2-char tokens (``+=``, ``-=``) and 3-char sequences
        (``**=``, ``//=``, ``%%=``).
        """
        # Check 2-char compound assignment tokens
        tt = self._current().type
        if tt in _COMPOUND_ASSIGN_OPS:
            self._advance()
            return _COMPOUND_ASSIGN_OPS[tt]

        # Check 3-char compound assignment patterns (DSTAR+ASSIGN, DSLASH+ASSIGN, DPERCENT+ASSIGN)
        nxt = self.pos + 1
        if nxt < len(self.tokens):
            nxt_tt = self.tokens[nxt].type
            key = (tt, nxt_tt)
            if key in _COMPOUND_3CHAR:
                self._advance()  # consume first token (DSTAR/DSLASH/DPERCENT)
                self._advance()  # consume second token (ASSIGN)
                return _COMPOUND_3CHAR[key]

        return None

    def _parse_expression(self) -> Node:
        """Parse an expression:

            primary ( '.' ident )* ( binary_op primary ( '.' ident )* )*
            optionally followed by .TF boolean suffix or :arg method call
        """
        left = self._parse_primary_chain()
        left = self._parse_binary_rhs(left, left.line)

        # Handle method call syntax: object.prop : arg  (e.g., D.find:5)
        if self._check(TokenType.COLON):
            self._advance()
            arg = self._parse_expression()
            flat = self._flatten_prop_chain(left)
            if flat is not None:
                return MethodCallNode(
                    method=f"{flat[0]}.{flat[1]}",
                    argument=arg, line=left.line,
                )
            raise ParseError(
                "Expected a property chain before ':'", self._current(),
            )

        if self._check(TokenType.BOOLEAN_TF):
            self._advance()
            left = BooleanNode(expr=left, line=left.line)
        return left

    # ── Bitwise operator matching ────────────────────────────────────────

    def _match_bitwise(self) -> str | None:
        """Check and consume a bitwise operator.

        Multi-token: |^| -> bxor
        Keywords: band, bor, bxor, blshift, brshift
        Symbols: &, |, <<, >>, ~
        """
        tok = self._current()
        # Multi-token: |^| (PIPE + CARET + PIPE) -> bxor
        if tok.type == TokenType.PIPE and self.pos + 2 < len(self.tokens):
            key3 = (
                self.tokens[self.pos].type,
                self.tokens[self.pos + 1].type,
                self.tokens[self.pos + 2].type,
            )
            if key3 == (TokenType.PIPE, TokenType.CARET, TokenType.PIPE):
                op = "bxor"
                self._advance()
                self._advance()
                self._advance()
                return op
        # Keywords: band, bor, bxor, blshift, brshift
        if tok.type in _BITWISE_KEYWORD_TYPES:
            val = tok.value.lower()
            if val in ("band", "bor", "bxor", "blshift", "brshift"):
                self._advance()
                return val
        # Symbols: &, |, <<, >>, ~
        if tok.type == TokenType.AMPERSAND:
            self._advance()
            return "band"
        if tok.type == TokenType.PIPE:
            self._advance()
            return "bor"
        if tok.type == TokenType.BITWISE_LSHIFT:
            self._advance()
            return "blshift"
        if tok.type == TokenType.BITWISE_RSHIFT:
            self._advance()
            return "brshift"
        return None

    # ── Bitwise expression parsing (between comparison and logical AND) ──

    def _parse_bitwise_rhs(self, left: Node) -> Node:
        """Parse bitwise operators (&, |, ^, <<, >>) and keyword forms.

        Positioned between comparison (higher) and logical AND (lower).
        """
        left = self._parse_comparison_rhs(left)
        while True:
            op = self._match_bitwise()
            if op is None:
                break
            right = self._parse_bitwise_operand()
            left = BitwiseExpressionNode(operator=op, left=left, right=right, line=left.line)
        return left

    def _parse_bitwise_operand(self) -> Node:
        """Parse the operand of a bitwise operator (comparison-level precedence)."""
        left = self._parse_primary_chain()
        return self._parse_comparison_rhs(left)

    # ── Logical operator matching ───────────────────────────────────────

    def _match_and_logical(self) -> str | None:
        """Check and consume AND-level logical operators (and, &&, nor, nand).

        Never consumes OR-level operators (or, ||, xor, xnor, xnor) —
        those are handled by the OR-level precedence layer.
        """
        # Multi-token: ^|^ (nor), ^&^ (nand) — starts with CARET
        tok = self._current()
        if tok.type == TokenType.CARET and self.pos + 2 < len(self.tokens):
            key3 = (
                self.tokens[self.pos].type,
                self.tokens[self.pos + 1].type,
                self.tokens[self.pos + 2].type,
            )
            if key3 == (TokenType.CARET, TokenType.PIPE, TokenType.CARET):
                op = "nor"
                self._advance()
                self._advance()
                self._advance()
                return op
            if key3 == (TokenType.CARET, TokenType.AMPERSAND, TokenType.CARET):
                op = "nand"
                self._advance()
                self._advance()
                self._advance()
                return op
        # Keywords: and, nor, nand
        if tok.type in _LOGICAL_KEYWORD_TYPES:
            val = tok.value.lower()
            if val in ("and", "nor", "nand"):
                self._advance()
                return val
        # Symbol: &&
        if tok.type == TokenType.LOGICAL_AND:
            self._advance()
            return "and"
        return None

    def _match_or_logical(self) -> str | None:
        """Check and consume OR-level logical operators (or, ||, xor, xnor).

        Never consumes AND-level operators (and, &&, nor, nand) —
        those are handled by the AND-level precedence layer.
        """
        tok = self._current()
        # Multi-token: ^|| (xor), ^||^ (xnor) — starts with CARET
        if tok.type == TokenType.CARET:
            if self.pos + 2 < len(self.tokens):
                key3 = (
                    self.tokens[self.pos].type,
                    self.tokens[self.pos + 1].type,
                    self.tokens[self.pos + 2].type,
                )
                if key3 == (TokenType.CARET, TokenType.LOGICAL_OR, TokenType.CARET):
                    op = "xnor"
                    self._advance()
                    self._advance()
                    self._advance()
                    return op
            if self.pos + 1 < len(self.tokens):
                key2 = (
                    self.tokens[self.pos].type,
                    self.tokens[self.pos + 1].type,
                )
                if key2 == (TokenType.CARET, TokenType.LOGICAL_OR):
                    op = "xor"
                    self._advance()
                    self._advance()
                    return op
        # Keywords: or, xor, xnor
        if tok.type in _LOGICAL_KEYWORD_TYPES:
            val = tok.value.lower()
            if val in ("or", "xor", "xnor"):
                self._advance()
                return val
        # Symbol: ||
        if tok.type == TokenType.LOGICAL_OR:
            self._advance()
            return "or"
        return None

    # ── Logical AND-level operators: and, &&, nor, nand ─────────────────

    def _parse_logical_and_rhs(self, left: Node) -> Node:
        """Parse logical AND-level operators (and, &&, nor, nand).

        These have precedence below bitwise and above logical OR.
        """
        left = self._parse_bitwise_rhs(left)
        while True:
            op = self._match_and_logical()
            if op is None:
                break
            right = self._parse_logical_operand()
            left = LogicalExpressionNode(operator=op, left=left, right=right, line=left.line)
        return left

    def _parse_logical_operand(self) -> Node:
        """Parse the RHS operand of a logical-AND operator.

        Uses bitwise-level precedence so that ``and`` binds tighter
        within the same AND-level, but ``or`` is NOT consumed here.
        """
        left = self._parse_primary_chain()
        return self._parse_bitwise_rhs(left)

    def _parse_or_operand(self) -> Node:
        """Parse the RHS operand of a logical-OR operator.

        Uses AND-level precedence so that ``A or B and C`` is parsed
        as ``A or (B and C)`` — the ``and`` binds tighter than ``or``.
        """
        left = self._parse_primary_chain()
        return self._parse_logical_and_rhs(left)

    # ── Logical OR-level operators: or, ||, xor, xnor ──────────────────

    def _parse_logical_or_rhs(self, left: Node) -> Node:
        """Parse logical OR-level operators (or, ||, xor, xnor).

        Uses ``_parse_or_operand`` (AND-level precedence) so that
        ``A or B and C`` parses as ``A or (B and C)``, respecting
        the higher precedence of AND over OR.
        """
        left = self._parse_logical_and_rhs(left)
        while True:
            op = self._match_or_logical()
            if op is None:
                break
            right = self._parse_or_operand()
            left = LogicalExpressionNode(operator=op, left=left, right=right, line=left.line)
        return left

    def _parse_binary_rhs(self, left: Node, line: int) -> Node:
        """Extend *left* with zero or more binary operators (proper precedence).

        Precedence (highest to lowest):
          1. **, ^    (power)
          2. *, /, //, %, %%  (multiplicative)
          3. +, -      (additive)
          4. ==, !=, >, <, >=, <=, ===  (comparison / strict)
          5. &, |, <<, >>, band, bor, ... (bitwise)
          6. and, &&, nor, nand (logical AND-level)
          7. or, ||, xor, xnor  (logical OR-level)
        """
        # Comparison flow operators (-->, <--) are DEPRECATED as expression
        # operators. They are now reserved for branch execution markers
        # inside !If statements (pre_action/post_action).
        return self._parse_logical_or_rhs(left)

    _COMPARISON_OPS: frozenset[TokenType] = frozenset({
        TokenType.EQ, TokenType.NEQ,
        TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE,
    })

    _ADDITIVE_OPS: frozenset[TokenType] = frozenset({
        TokenType.PLUS, TokenType.MINUS,
    })

    _MULTIPLICATIVE_OPS: frozenset[TokenType] = frozenset({
        TokenType.STAR, TokenType.SLASH, TokenType.PERCENT,
        TokenType.DSLASH, TokenType.DPERCENT,
    })

    _POWER_OPS: frozenset[TokenType] = frozenset({
        TokenType.DSTAR, TokenType.CARET,
    })

    def _parse_comparison_rhs(self, left: Node) -> Node:
        """Parse comparison operators (==, !=, >, <, >=, <=, ===).

        Strict comparison (===) is also handled at this level.
        NOTE: `is`/`to` binary operators are handled in expression_parser.py.
        """
        left = self._parse_additive_rhs(left)
        while True:
            if self._check(TokenType.STRICT_EQ):
                self._advance()
                right = self._parse_additive()
                left = StrictComparisonNode(left=left, right=right, line=left.line)
            elif self._check(*self._COMPARISON_OPS):
                op_tok = self._advance()
                right = self._parse_additive()
                left = BinaryOpNode(
                    operator=op_tok.value,
                    left=left, right=right,
                    line=op_tok.line,
                )
            else:
                break
        return left

    def _parse_additive_rhs(self, left: Node) -> Node:
        """Parse additive operators (+/-)."""
        left = self._parse_multiplicative_rhs(left)
        while self._check(*self._ADDITIVE_OPS):
            op_tok = self._advance()
            right = self._parse_multiplicative()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_multiplicative_rhs(self, left: Node) -> Node:
        """Parse multiplicative operators (*, /, //, %, %%)."""
        # First handle any power operators on the left
        left = self._parse_power_rhs(left)
        while self._check(*self._MULTIPLICATIVE_OPS):
            op_tok = self._advance()
            right = self._parse_power()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_power_rhs(self, left: Node) -> Node:
        """Parse power operators (**, ^) — highest precedence.

        NOTE: If ``^`` (CARET) starts a multi-token logical operator
        (``^||``, ``^|^``, ``^&^``, ``^||^``) we back off and let the
        logical expression chain handle it.
        """
        while self._check(*self._POWER_OPS):
            tok = self._current()
            # If CARET is part of a multi-token logical operator, skip
            if tok.type == TokenType.CARET and self.pos + 1 < len(self.tokens):
                nxt = self.tokens[self.pos + 1].type
                if nxt in (TokenType.LOGICAL_OR, TokenType.PIPE, TokenType.AMPERSAND):
                    break
            op_tok = self._advance()
            right = self._parse_primary_chain()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_additive(self) -> Node:
        """Parse an additive expression (for use as RHS of comparison)."""
        left = self._parse_multiplicative()
        while self._check(*self._ADDITIVE_OPS):
            op_tok = self._advance()
            right = self._parse_multiplicative()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_multiplicative(self) -> Node:
        """Parse a multiplicative expression (for use as RHS of additive)."""
        left = self._parse_power()
        while self._check(*self._MULTIPLICATIVE_OPS):
            op_tok = self._advance()
            right = self._parse_power()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_power(self) -> Node:
        """Parse a power expression (for use as RHS of multiplicative).

        NOTE: If ``^`` (CARET) starts a multi-token logical operator
        (``^||``, ``^|^``, ``^&^``, ``^||^``) we back off and let the
        logical expression chain handle it.
        """
        left = self._parse_primary_chain()
        while self._check(*self._POWER_OPS):
            tok = self._current()
            # If CARET is part of a multi-token logical operator, skip
            if tok.type == TokenType.CARET and self.pos + 1 < len(self.tokens):
                nxt = self.tokens[self.pos + 1].type
                if nxt in (TokenType.LOGICAL_OR, TokenType.PIPE, TokenType.AMPERSAND):
                    break
            op_tok = self._advance()
            right = self._parse_primary_chain()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_primary(self) -> Node:
        """Parse a primary expression: string, integer, float, identifier,
        or a dot-method expression (``.len:var``, ``.upper:var``, etc.)."""
        tok = self._current()
        if tok.type == TokenType.STRING:
            self._advance()
            return LiteralNode(value=tok.value, kind=TokenType.STRING, line=tok.line)
        if tok.type == TokenType.INTEGER:
            self._advance()
            return LiteralNode(value=tok.value, kind=TokenType.INTEGER, line=tok.line)
        if tok.type == TokenType.FLOAT:
            self._advance()
            return LiteralNode(value=tok.value, kind=TokenType.FLOAT, line=tok.line)
        if tok.type == TokenType.IMAGINARY:
            self._advance()
            return ImaginaryNode(value=tok.value, line=tok.line)
        if tok.type == TokenType.BOOLEAN_LITERAL:
            self._advance()
            return LiteralNode(value=tok.value == "True", kind=TokenType.BOOLEAN_LITERAL, line=tok.line)
        if tok.type == TokenType.IDENTIFIER:
            self._advance()
            return IdentifierNode(name=tok.value, line=tok.line)
        if tok.type == TokenType.MINUS:
            # Unary minus: -<integer> or -<float>
            self._advance()
            nxt = self._current()
            if nxt.type == TokenType.INTEGER:
                self._advance()
                return LiteralNode(value=-nxt.value, kind=TokenType.INTEGER, line=tok.line)
            if nxt.type == TokenType.FLOAT:
                self._advance()
                return LiteralNode(value=-nxt.value, kind=TokenType.FLOAT, line=tok.line)
            raise ParseError("Expected a number after '-'", tok)
        if tok.type == TokenType.BANG:
            # Unary NOT: !expr
            self._advance()
            expr = self._parse_expression()
            return UnaryLogicalNode(operator="not", expr=expr, line=tok.line)
        if tok.type == TokenType.NOT_KW:
            # Unary logical NOT: not expr
            self._advance()
            expr = self._parse_expression()
            return UnaryLogicalNode(operator="not", expr=expr, line=tok.line)
        if tok.type == TokenType.BNOT_KW:
            # Unary bitwise NOT: bnot expr
            self._advance()
            expr = self._parse_expression()
            return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)
        if tok.type == TokenType.BITWISE_NOT:
            # Unary bitwise NOT: ~expr
            self._advance()
            expr = self._parse_expression()
            return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)
        if tok.type in (TokenType.YES_KW, TokenType.NO_KW):
            self._advance()
            value = tok.type == TokenType.YES_KW
            return LiteralNode(value=value, kind=TokenType.BOOLEAN_LITERAL, line=tok.line)
        if tok.type == TokenType.DOT:
            # Dot-method expression in value position: .len:var, .upper:var, etc.
            nxt = self.pos + 1
            if (nxt < len(self.tokens)
                    and self.tokens[nxt].type == TokenType.IDENTIFIER
                    and self.tokens[nxt].value in ("run", "fun")):
                raise ParseError(
                    "'.run:' and '.fun:' cannot be used as a value", tok
                )
            if self._is_dot_query_or_input():
                return self._parse_dot_stmt()
            # Delegate function calls in expression position to FunctionParser
            # (FunctionParserMixin was removed in RC2-05A)
            if hasattr(self, '_function') and self._function is not None:
                return self._function.parse_function_call_from_expr()
            from parser.parser import ParseError
            raise ParseError("Function parser not configured", tok)
        if tok.type == TokenType.PIPE:
            # Absolute value: |expr|
            # Use comparison-level precedence (arithmetic + comparison but
            # NOT bitwise/|) so the closing | is not consumed as bor.
            open_tok = self._advance()  # consume '|'
            inner = self._parse_primary_chain()
            inner = self._parse_comparison_rhs(inner)
            self._consume(
                TokenType.PIPE,
                "Expected closing '|' for absolute value expression",
            )
            return CmNode(value=inner, line=open_tok.line)
        if tok.type == TokenType.INPUT_SPEC:
            self._advance()
            if tok.value == "par.in":
                if self._check(TokenType.COLON):
                    self._advance()
                    content = self._parse_expression()
                    return ParagraphNode(content=content, line=tok.line)
                return InputNode(input_type="paragraph", line=tok.line)
            node = self._make_input_node(tok.value, tok.line)
            if self._check(TokenType.COLON):
                self._advance()
                node.prompt = self._parse_expression()
            return node
        if tok.type == TokenType.LPAREN:
            # Parenthesized expression: ( expr )
            self._advance()  # consume '('
            expr = self._parse_expression()
            self._consume(
                TokenType.RPAREN,
                "Expected ')' after parenthesized expression",
            )
            return expr
        raise ParseError(
            f"Expected a value (string, number, or identifier), "
            f"but found '{tok.value}'",
            tok,
        )

    def _parse_coordinate_pair(self) -> tuple[int, int] | None:
        """Parse a coordinate pair like ``8,4`` into (8, 4).

        Expected token sequence: INTEGER COMMA INTEGER
        Returns None on failure.
        """
        if self._check(TokenType.INTEGER):
            first = self._advance()
            if self._check(TokenType.COMMA):
                self._advance()
                if self._check(TokenType.INTEGER):
                    second = self._advance()
                    return (int(first.value), int(second.value))
        return None


    _INPUT_TYPE_MAP: dict[str, str] = {
        "I.in": "integer",
        "F.in": "float",
        "D.in": "double",
        "L.in": "long",
        "Byte.in": "byte",
        "S.in": "string",
        "Char.in": "char_single",
        "c.in": "char",
        "dchar.in": "dchar",
        "tchar.in": "tchar",
        "line.in": "line",
        "b.in": "buffer",
        "bl.in": "builder",
        "par.in": "paragraph",
    }

    def _make_input_node(self, compound: str, line: int) -> InputNode:
        """Create an InputNode from a compound input keyword.

        Args:
            compound: The compound keyword value (e.g. "I.in", "c.in").
            line: Source line number.

        Returns:
            An InputNode with the appropriate input_type and var_type.
        """
        input_type = self._INPUT_TYPE_MAP.get(compound, "generic")
        var_type: str | None = None
        if compound == "I.in":
            var_type = "I"
        elif compound == "F.in":
            var_type = "F"
        elif compound == "D.in":
            var_type = "D"
        elif compound == "L.in":
            var_type = "L"
        elif compound == "Byte.in":
            var_type = "I"
        elif compound == "S.in":
            var_type = "S"
        elif compound == "Char.in":
            var_type = "S"
        return InputNode(input_type=input_type, var_type=var_type, line=line)
