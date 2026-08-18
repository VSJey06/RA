"""parser_decision.py — Decision Family parser for the RA language.

Constitutionally required specialized parser for all Decision constructs:

  Primary Decisions:
    - !If.condition, body #           (IfNode)
    - !! Elseif.condition, body #     (ElseIfNode)
    - !Else body #                    (ElseNode)
    - Tree flow: !If.cond ---> pre_action :  (tree_flow=True)
    - Pre-action: !If.cond --> pre_action : body ...
    - Post-action: ... <-- post_action #

  Nested Decisions (inside executable blocks only):
    - if.condition: body #
    - elif.condition: body #
    - else: body #

  What Block (Type Decision Engine):
    - !What variable :
          !i var == Type : body #
          !e var == Type : body #
          !else : body #
      #

DecisionParser produces AST nodes only.
No runtime logic. No semantic analysis.
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    BooleanNode,
    ElseIfNode,
    ElseNode,
    IfNode,
    Node,
    UnaryLogicalNode,
    WhatBranchNode,
    WhatNode,
)
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class DecisionParser:
    """Parses all Decision Family constructs.

    DecisionParser is the SOLE owner of:

      - Primary Decisions: !If, !!ElseIf, !Else (parse_if)
      - Nested Decisions:  if, elif, else       (parse_nested_if)
      - What Block:         !What               (parse_what)

    All other parser modules (statement_parser, parser.py) shall
    ONLY dispatch to this parser — never implement decision grammar.

    DecisionParser produces AST nodes only.
    """

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry

        # ── Delegates set by the facade (parser.py) ────────────────────
        self._parse_body_func: Optional[callable] = None
        self._expression_parser: Optional[object] = None
        # Callback to statement_parser.parse_stmt() — used for pre/post
        # actions and nested !If inside !If then-bodies.
        self._parse_stmt_callback: Optional[callable] = None

    # ── Expression parsing delegate ─────────────────────────────────────

    def _parse_expression(self) -> Node:
        """Parse an expression — delegates to ExpressionParser."""
        if self._expression_parser is not None:
            return self._expression_parser.parse_expression()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())

    # ── Suppress method-call ':' consumption helpers ────────────────────

    def _suppress_expression_method_call(self) -> bool:
        """Save and suppress method-call ':' consumption in expression parser.

        Returns the previous value so it can be restored.
        """
        saved = getattr(
            self._expression_parser, '_suppress_method_call_suffix', False,
        )
        self._expression_parser._suppress_method_call_suffix = True
        return saved

    def _restore_expression_method_call(self, saved: bool) -> None:
        """Restore method-call ':' consumption in expression parser."""
        self._expression_parser._suppress_method_call_suffix = saved

    # ── Line-column map for indentation validation ──────────────────────

    def _build_line_column_map(self) -> dict[int, int]:
        """Build a mapping from source line numbers to their leading column.

        Returns a dict ``{line_number: column}`` where *column* is the
        column of the first token on that line.  This is used by
        ``_validate_indentation()`` to check that block statements are
        properly indented.
        """
        line_map: dict[int, int] = {}
        for tok in self.env.tokens:
            if tok.line not in line_map:
                line_map[tok.line] = tok.column
        return line_map

    def _validate_indentation(
        self,
        body: list[Node],
        parent_col: int,
        line_map: dict[int, int],
        opening_line: int,
    ) -> None:
        """Validate that all statements in *body* are properly indented.

        Rules (matching Python-like indentation):

        1. Every statement inside the block must have a column greater
           than the parent column (i.e. indented by at least 1 space).
        2. All sibling statements must share the same leading column.
        3. Statements on the same line as the opening construct
           (e.g. ``!If.a==10: p "inline"``) are allowed.
        """
        if not body:
            return
        columns: list[int] = []
        for node in body:
            col = line_map.get(node.line, 0)
            if node.line == opening_line:
                continue  # same-line statements are allowed
            if col <= parent_col:
                from parser.parser import ParseError
                raise ParseError(
                    f"Block statement must be indented by one level "
                    f"(> {parent_col} spaces). Found column {col}.",
                    self.env.current(),
                )
            columns.append(col)
        if not columns:
            return
        first_col = columns[0]
        for col in columns[1:]:
            if col != first_col:
                from parser.parser import ParseError
                raise ParseError(
                    f"Incorrect indentation. "
                    f"Expected {first_col}-space indentation inside the block, "
                    f"but found column {col}.",
                    self.env.current(),
                )

    # ── Primary If / ElseIf / Else ───────────────────────────────────────

    def parse_if(self, bang_tok: Token) -> IfNode:
        """Parse a primary ``!If`` statement with optional tree flow,
        pre/post actions, ``!!ElseIf`` branches, and ``!Else``.

        Syntax
        ------
            !If.condition, body #

            !If.condition,
                body...
                !! Elseif.condition,
                    body...
                !Else
                    body...
            #

            !If.condition --> pre_action : body ...       (pre-action)
            !If.condition ---> pre_action :               (tree flow)
            ... body ... <-- post_action #                (post-action)
        """
        if_tok = self.env.consume(TokenType.IDENTIFIER, "Expected 'If'")
        if (
            self.env.check(TokenType.DOT)
            and self.env.current().column == if_tok.end_column + 1
        ):
            self.env.advance()

        # Suppress method-call ':' consumption during condition parsing
        saved_suppress = self._suppress_expression_method_call()
        try:
            condition = self._parse_expression()
        finally:
            self._restore_expression_method_call(saved_suppress)

        parent_col = bang_tok.column

        # ── Tree Flow pre-action (--->) ────────────────────────────────
        tree_flow: bool = False
        pre_action: Optional[list[Node]] = None
        if self.env.check(TokenType.FLOW_TREE_FWD):
            tree_flow = True
            self.env.advance()
            # Parse pre-action as an expression (suppress method-call ':')
            saved_suppress2 = self._suppress_expression_method_call()
            try:
                pre_expr = self._parse_expression()
                pre_action = [pre_expr]
            finally:
                self._restore_expression_method_call(saved_suppress2)
            self.env.consume(TokenType.COLON, "Expected ':' after tree-flow pre-action")
            elseifs: list[ElseIfNode] = []
            else_node: Optional[ElseNode] = None
            return IfNode(
                condition=condition, then_body=[], elseifs=elseifs,
                else_node=else_node, pre_action=pre_action, post_action=None,
                tree_flow=tree_flow, line=bang_tok.line,
                auto_close=True,
            )

        # ── Optional pre-action (-->) ──────────────────────────────────
        if self.env.check(TokenType.FLOW_FWD):
            self.env.advance()
            saved_suppress2 = self._suppress_expression_method_call()
            try:
                pre_expr = self._parse_expression()
                pre_action = [pre_expr]
            finally:
                self._restore_expression_method_call(saved_suppress2)
            self.env.consume(TokenType.COLON, "Expected ':' after pre-action")
        else:
            if self.env.check(TokenType.COLON):
                self.env.advance()
            elif self.env.check(TokenType.COMMA):
                self.env.advance()
            else:
                from parser.parser import ParseError
                raise ParseError(
                    "Expected ':' or ',' after If condition",
                    self.env.current(),
                )

        # ── Body terminators ───────────────────────────────────────────
        body_terminators: frozenset[TokenType] = frozenset({
            TokenType.HASH, TokenType.BANG, TokenType.FLOW_REV, TokenType.FLOW_TREE_REV,
        })

        line_map = self._build_line_column_map()

        if self._parse_body_func is not None:
            then_body = self._parse_body_func(terminators=body_terminators)
        else:
            then_body = []

        self._validate_indentation(then_body, parent_col, line_map, bang_tok.line)

        # ── Optional post-action (<-- or <---) ────────────────────────
        post_action: Optional[list[Node]] = None
        if self.env.check(TokenType.FLOW_TREE_REV):
            self.env.advance()
            post_stmt = self._parse_stmt_callback() if self._parse_stmt_callback else None
            if post_stmt is not None:
                post_action = [post_stmt]
        elif self.env.check(TokenType.FLOW_REV):
            self.env.advance()
            post_stmt = self._parse_stmt_callback() if self._parse_stmt_callback else None
            if post_stmt is not None:
                post_action = [post_stmt]

        has_then_close = self.env.check(TokenType.HASH)
        if has_then_close:
            self.env.advance()

        elseifs: list[ElseIfNode] = []
        else_node: Optional[ElseNode] = None

        # ── ElseIf / Else loop ─────────────────────────────────────────
        while self.env.check(TokenType.BANG):
            nxt = self.env.pos + 1
            if (nxt < len(self.env.tokens)
                    and self.env.tokens[nxt].type == TokenType.IDENTIFIER
                    and self.env.tokens[nxt].value == "If"):
                nested = self._parse_stmt_callback() if self._parse_stmt_callback else None
                if nested is not None:
                    then_body.append(nested)
                continue

            saved_pos = self.env.pos
            saved_tok = self.env.current()
            self.env.advance()

            if self.env.check(TokenType.BANG):
                self.env.advance()
                if (self.env.check(TokenType.IDENTIFIER)
                        and self.env.current().value == "Elseif"):
                    self.env.advance()
                    self.env.consume(TokenType.DOT, "Expected '.' after 'Elseif'")
                saved_suppress2 = self._suppress_expression_method_call()
                try:
                    elseif_cond = self._parse_expression()
                finally:
                    self._restore_expression_method_call(False)
                if self.env.check(TokenType.COLON):
                    self.env.advance()
                elif self.env.check(TokenType.COMMA):
                    self.env.advance()
                else:
                    from parser.parser import ParseError
                    raise ParseError(
                        "Expected ':' or ',' after ElseIf condition",
                        self.env.current(),
                    )
                if self._parse_body_func is not None:
                    elseif_body = self._parse_body_func(terminators=body_terminators)
                else:
                    elseif_body = []
                self._validate_indentation(
                    elseif_body, parent_col, line_map, saved_tok.line,
                )
                has_elseif_close = self.env.check(TokenType.HASH)
                if has_elseif_close:
                    self.env.advance()
                elseifs.append(ElseIfNode(
                    condition=elseif_cond, body=elseif_body,
                    line=saved_tok.line, auto_close=not has_elseif_close,
                ))
            elif (self.env.check(TokenType.IDENTIFIER)
                  and self.env.current().value == "Else"):
                self.env.advance()
                if self.env.check(TokenType.COLON):
                    self.env.advance()
                if self._parse_body_func is not None:
                    else_body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
                else:
                    else_body = []
                self._validate_indentation(
                    else_body, parent_col, line_map, saved_tok.line,
                )
                has_else_close = self.env.check(TokenType.HASH)
                if has_else_close:
                    self.env.advance()
                else_node = ElseNode(
                    body=else_body, line=saved_tok.line,
                    auto_close=not has_else_close,
                )
            else:
                self.env.pos = saved_pos
                break

        if not has_then_close and self.env.check(TokenType.HASH):
            self.env.advance()
            has_then_close = True

        return IfNode(
            condition=condition, then_body=then_body, elseifs=elseifs,
            else_node=else_node, pre_action=pre_action, post_action=post_action,
            tree_flow=tree_flow, line=bang_tok.line,
            auto_close=not has_then_close,
        )

    # ── Nested if / elif / else ─────────────────────────────────────────

    def parse_nested_if(self) -> IfNode:
        """Parse a nested if/elif/else chain inside an executable block.

        Syntax (all forms accepted):

            if.condition:
                body
            #

            if condition, body #

            if.condition:
                body
            elif.condition2:
                body
            else:
                body
            #

        Produces the SAME AST nodes as the primary !If parser (IfNode,
        ElseIfNode, ElseNode).

        Raises NestedBlockSyntaxError if not inside a block.
        """
        from EHub.PE.statement_parser import NestedBlockSyntaxError

        if self.env.nested_block_depth == 0:
            raise NestedBlockSyntaxError(
                "'if' is only valid inside an executable block. "
                "Use '!If' at the top level instead."
            )

        if_tok = self.env.advance()  # consume 'if'
        if (
            self.env.check(TokenType.DOT)
            and self.env.current().column == if_tok.end_column + 1
        ):
            self.env.advance()

        saved_suppress = self._suppress_expression_method_call()
        try:
            condition = self._parse_expression()
        finally:
            self._restore_expression_method_call(saved_suppress)

        parent_col = if_tok.column

        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            from parser.parser import ParseError
            raise ParseError(
                "Expected ':' or ',' after nested if condition",
                self.env.current(),
            )

        body_terminators: frozenset[TokenType] = frozenset({
            TokenType.HASH,
            TokenType.ELIF_NESTED,
            TokenType.ELSE_NESTED,
        })

        line_map = self._build_line_column_map()

        if self._parse_body_func is not None:
            then_body = self._parse_body_func(terminators=body_terminators)
        else:
            then_body = []

        self._validate_indentation(then_body, parent_col, line_map, if_tok.line)

        if self.env.check(TokenType.FLOW_REV):
            self.env.advance()

        has_then_close = self.env.check(TokenType.HASH)
        if has_then_close:
            self.env.advance()

        elseifs: list[ElseIfNode] = []
        else_node: Optional[ElseNode] = None

        while self.env.check(TokenType.ELIF_NESTED):
            elif_tok = self.env.advance()
            if (
                self.env.check(TokenType.DOT)
                and self.env.current().column == elif_tok.end_column + 1
            ):
                self.env.advance()

            saved_suppress2 = self._suppress_expression_method_call()
            try:
                elif_cond = self._parse_expression()
            finally:
                self._restore_expression_method_call(False)

            if self.env.check(TokenType.COLON):
                self.env.advance()
            elif self.env.check(TokenType.COMMA):
                self.env.advance()
            else:
                from parser.parser import ParseError
                raise ParseError(
                    "Expected ':' or ',' after elif condition",
                    self.env.current(),
                )

            if self._parse_body_func is not None:
                elif_body = self._parse_body_func(terminators=body_terminators)
            else:
                elif_body = []

            self._validate_indentation(
                elif_body, parent_col, line_map, elif_tok.line,
            )

            has_elif_close = self.env.check(TokenType.HASH)
            if has_elif_close:
                self.env.advance()

            elseifs.append(ElseIfNode(
                condition=elif_cond, body=elif_body,
                line=elif_tok.line, auto_close=not has_elif_close,
            ))

        if self.env.check(TokenType.ELSE_NESTED):
            else_tok = self.env.advance()
            if self.env.check(TokenType.COLON):
                self.env.advance()

            if self._parse_body_func is not None:
                else_body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
            else:
                else_body = []

            self._validate_indentation(
                else_body, parent_col, line_map, else_tok.line,
            )

            has_else_close = self.env.check(TokenType.HASH)
            if has_else_close:
                self.env.advance()

            else_node = ElseNode(
                body=else_body, line=else_tok.line,
                auto_close=not has_else_close,
            )

        if not has_then_close and self.env.check(TokenType.HASH):
            self.env.advance()
            has_then_close = True

        return IfNode(
            condition=condition, then_body=then_body, elseifs=elseifs,
            else_node=else_node, pre_action=None, post_action=None,
            tree_flow=False, line=if_tok.line,
            auto_close=not has_then_close,
        )

    # ── What Block (Type Decision Engine) ────────────────────────────────

    def parse_what(self, bang_tok: Token) -> WhatNode:
        """Parse a What Block (Type Decision Engine).

        Syntax
        ------
            !What variable :
                !i var == I : body #
                !e var == F : body #
                !else : body #
            #
        """
        what_tok = self.env.advance()  # consume 'What'
        if (self.env.check(TokenType.DOT)
                and self.env.current().column == what_tok.end_column + 1):
            self.env.advance()
        var_tok = self.env.consume(
            TokenType.IDENTIFIER,
            "Expected variable name after '!What'",
        )
        self.env.consume(TokenType.COLON, "Expected ':' after variable name in !What")

        branches: list[WhatBranchNode] = []
        has_default = False

        while not self.env.check(TokenType.HASH, TokenType.EOF):
            if self.env.check(TokenType.BANG):
                saved_pos = self.env.pos
                self.env.advance()
                if self.env.check(TokenType.IDENTIFIER):
                    ident = self.env.current().value
                    if ident == "i" and not has_default:
                        self.env.advance()
                        self.env.consume(
                            TokenType.IDENTIFIER,
                            "Expected variable name after '!i'",
                        )
                        self.env.consume(
                            TokenType.EQ,
                            "Expected '==' after variable in !i branch",
                        )
                        type_tok = self.env.current()
                        if type_tok.is_keyword() or type_tok.type == TokenType.IDENTIFIER:
                            self.env.advance()
                            type_name = str(type_tok.value)
                        else:
                            from parser.parser import ParseError
                            raise ParseError(
                                "Expected type name after '==' in !i branch",
                                type_tok,
                            )
                        self.env.consume(
                            TokenType.COLON,
                            "Expected ':' after type in !i branch",
                        )
                        if self._parse_body_func is not None:
                            body = self._parse_body_func(
                                terminators=frozenset({TokenType.HASH}),
                            )
                        else:
                            body = []
                        has_close = self.env.check(TokenType.HASH)
                        if has_close:
                            self.env.advance()
                        branches.append(WhatBranchNode(
                            var_type=type_name, body=body,
                            line=bang_tok.line, auto_close=not has_close,
                        ))
                        continue
                    elif ident == "e" and not has_default:
                        self.env.advance()
                        self.env.consume(
                            TokenType.IDENTIFIER,
                            "Expected variable name after '!e'",
                        )
                        self.env.consume(
                            TokenType.EQ,
                            "Expected '==' after variable in !e branch",
                        )
                        type_tok = self.env.current()
                        if type_tok.is_keyword() or type_tok.type == TokenType.IDENTIFIER:
                            self.env.advance()
                            type_name = str(type_tok.value)
                        else:
                            from parser.parser import ParseError
                            raise ParseError(
                                "Expected type name after '==' in !e branch",
                                type_tok,
                            )
                        self.env.consume(
                            TokenType.COLON,
                            "Expected ':' after type in !e branch",
                        )
                        if self._parse_body_func is not None:
                            body = self._parse_body_func(
                                terminators=frozenset({TokenType.HASH}),
                            )
                        else:
                            body = []
                        has_close = self.env.check(TokenType.HASH)
                        if has_close:
                            self.env.advance()
                        branches.append(WhatBranchNode(
                            var_type=type_name, body=body,
                            line=bang_tok.line, auto_close=not has_close,
                        ))
                        continue
                    elif ident in ("Else", "else") and not has_default:
                        self.env.advance()
                        if self.env.check(TokenType.COLON):
                            self.env.advance()
                        elif self.env.check(TokenType.COMMA):
                            self.env.advance()
                        if self._parse_body_func is not None:
                            body = self._parse_body_func(
                                terminators=frozenset({TokenType.HASH}),
                            )
                        else:
                            body = []
                        has_close = self.env.check(TokenType.HASH)
                        if has_close:
                            self.env.advance()
                        has_default = True
                        branches.append(WhatBranchNode(
                            var_type="", body=body, is_default=True,
                            line=bang_tok.line, auto_close=not has_close,
                        ))
                        continue
                # Not a What branch marker — restore and break
                self.env.pos = saved_pos
                break
            break

        has_full_close = self.env.check(TokenType.HASH)
        if has_full_close:
            self.env.advance()

        return WhatNode(
            variable=var_tok.value, branches=branches,
            line=bang_tok.line, auto_close=not has_full_close,
        )
