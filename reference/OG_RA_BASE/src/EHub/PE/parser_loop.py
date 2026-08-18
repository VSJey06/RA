"""parser_loop.py — Loop Family parser for the RA language.

Constitutionally required specialized parser for all Loop constructs:

  Primary Loops (RC3-01A — Unified Loop Family):
    - ? For.<condition>, <iteration>:     (Syntax 1 — pre-declared)
    - ? For.<decl>, <condition>, <iter>:  (Syntax 2 — inline)
    - ? While.<condition>, <iter>:        (Syntax 1 — pre-declared auto)
    - ? While.<decl>, <condition>:        (Syntax 2 — inline manual)
    - ? In.<var> = expr1, expr2[, expr3]: (Type 1/2/3, RC3-01A)

  Nested Loops (inside executable blocks only):
    - for.<condition>, <iteration>:
    - for.<decl>, <condition>, <iter>:
    - while.<condition>, <iteration>:
    - while.<decl>, <condition>:

  Reserved (future implementation — parser ownership only):
    - ? Do                                  (Reserved)
    - ? Which                               (Reserved)
    - ? What                                (Reserved)

LoopParser produces AST nodes only.
No runtime logic. No semantic analysis.
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    AssignmentNode,
    BinaryOpNode,
    DoWhileNode,
    ForNode,
    ForUpdaterNode,
    IdentifierNode,
    IfNode,
    InNode,
    ListNode,
    LiteralNode,
    Node,
    WhatPreconditionNode,
    WhichBranchNode,
    WhichControlNode,
    WhileNode,
)
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class LoopParser:
    """Parses all Loop Family constructs.

    LoopParser is the SOLE owner of:

      - Primary Loops:   ? For, ? While, ? In   (parse_question_stmt)
      - Nested Loops:    for, while            (parse_nested_for, parse_nested_while)

    Active:
      - ? In                                  (RC2-06A, unchanged)

    Reserved (parser ownership, execution deferred):
      - ? Do, ? Which, ? What

    All other parser modules (statement_parser, parser.py) shall
    ONLY dispatch to this parser — never implement loop grammar.

    LoopParser produces AST nodes only.
    """

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry

        # ── Delegates set by the facade (parser.py) ────────────────────
        self._parse_body_func: Optional[callable] = None
        self._expression_parser: Optional[object] = None
        self._stmt_parser: Optional[object] = None

    # ── Shared contextual updater pattern detection (RC3-08I1) ─────────────
    #
    # This is the SINGLE canonical location where the ``n`` contextual
    # updater symbol is parsed from token sequences.  Both header-level
    # updaters (``_parse_loop_iteration``) and body-level updaters
    # (``_try_parse_updater_stmt``) call this method to detect the
    # ``IDENTIFIER("n") + (PLUS|MINUS) + [INTEGER]`` pattern.
    #
    # The expression-based counterpart ``canonicalize_updater_expression()``
    # handles ``n+<int>`` patterns from BinaryOpNode (e.g. Do-While's
    # ``i=n+2`` argument syntax).  That path is fundamentally different
    # (parsing an existing AST node vs. token stream) and is therefore
    # kept separate but converges to the same ForUpdaterNode result.
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_updater_pattern(env):
        """Try to detect an ``n+<int>`` / ``n-<int>`` pattern at the current
        token position.

        This is the SHARED helper that eliminates the three-independent-
        implementations problem.  It returns a tuple of the detected updater
        information, or ``None`` if the current position does not match an ``n``
        updater pattern.

        Returns
        -------
        tuple | None
            ``(operator, position, amount, consumed_count, peek_after, op_line)``
            where:
              - *operator*: ``"+"`` or ``"-"``
              - *position*: ``"suffix"`` (``n+``) or ``"prefix"`` (``+n``)
              - *amount*: ``int`` (default 1)
              - *consumed_count*: number of tokens consumed (2 or 3)
              - *peek_after*: the next ``Token`` after the pattern
              - *op_line*: line number of the operator for line-gap detection

            Returns ``None`` if no updater pattern is found.
        """
        tok = env.current()
        tt = tok.type

        # Suffix forms: n+ or n- (with optional amount)
        if tt == TokenType.IDENTIFIER and tok.value == "n":
            peek = env.peek(1)
            if peek is not None and peek.type in (TokenType.PLUS, TokenType.MINUS):
                op = peek.value
                after = env.peek(2)
                has_amount = False
                amount = 1
                if after is not None and after.type == TokenType.INTEGER:
                    amount = int(after.value)
                    has_amount = True
                    after = env.peek(3)
                return (op, "suffix", amount, 2 + (1 if has_amount else 0), after, peek.line)

        # Prefix forms: +n or -n
        if tt in (TokenType.PLUS, TokenType.MINUS):
            peek = env.peek(1)
            if peek is not None and peek.type == TokenType.IDENTIFIER and peek.value == "n":
                op = tok.value
                after = env.peek(2)
                return (op, "prefix", 1, 2, after, tok.line)

        return None

    # ── Expression parsing delegates ─────────────────────────────────────

    def _parse_expression(self) -> Node:
        """Parse an expression — delegates to ExpressionParser."""
        if self._expression_parser is not None:
            return self._expression_parser.parse_expression()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())

    def _parse_primary_chain(self) -> Node:
        """Parse a primary chain — delegates to ExpressionParser."""
        if self._expression_parser is not None:
            return self._expression_parser._parse_primary_chain()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())

    # ── Suppress method-call ':' consumption helpers ────────────────────

    def _suppress_expression_method_call(self) -> bool:
        saved = getattr(
            self._expression_parser, '_suppress_method_call_suffix', False,
        )
        self._expression_parser._suppress_method_call_suffix = True
        return saved

    def _restore_expression_method_call(self, saved: bool) -> None:
        self._expression_parser._suppress_method_call_suffix = saved

    # ── Helper: peek whether next token is an assignment (for disambiguation) ─

    def _is_assignment_at_current(self) -> bool:
        """Check if the current token is an IDENTIFIER followed by ASSIGN.

        Used for disambiguating Syntax 1 vs Syntax 2 of For/While.
        """
        return (
            self.env.check(TokenType.IDENTIFIER)
            and self.env.pos + 1 < len(self.env.tokens)
            and self.env.tokens[self.env.pos + 1].type == TokenType.ASSIGN
        )

    # ── Primary ?For / ?While ────────────────────────────────────────────

    def parse_question_stmt(self) -> Node:
        """Parse a question-prefixed loop statement.

        Canonical forms (RC2-06B):

            ? For.<condition>, <iteration>:   body #   (Syntax 1)
            ? For.<decl>, <condition>, <iter>: body #   (Syntax 2)
            ? While.<condition>, <iter>:      body #   (Syntax 1)
            ? While.<decl>, <condition>:      body #   (Syntax 2)

        Active:
            ?In var = source, limit[, step]:  body #   (?In — unchanged)

        Reserved future loops:
            ? Do, ? Which, ? What   ->  NotImplementedError
        """
        q_tok = self.env.advance()
        if self.env.check(TokenType.IDENTIFIER):
            val = self.env.current().value
            if val == "For":
                return self.parse_for(q_tok)
            if val == "While":
                return self.parse_while(q_tok)
            if val == "In":
                return self.parse_in(q_tok)
            if val == "Do":
                return self.parse_do(q_tok)
            if val == "Which":
                return self.parse_which(q_tok)
            if val == "What":
                return self.parse_what(q_tok)
        from parser.parser import ParseError
        raise ParseError(
            "Expected 'For', 'While', 'In', 'Do', 'Which', or 'What' after '?'",
            q_tok,
        )

    # ── Loop iteration updater parsing (RC2-06B/R2-06C) ────────────────

    def _parse_loop_iteration(self) -> ForUpdaterNode:
        """Parse the For/While update argument -- recognizes contextual updater forms.

        Delegates pattern detection to the shared ``_detect_updater_pattern()``
        method (the SINGLE canonical location for ``n`` token-sequence detection).

        Valid updater forms:
            n+     (suffix increment by 1)
            +n     (prefix increment by 1)
            n-     (suffix decrement by 1)
            -n     (prefix decrement by 1)
            n+<int>  (suffix increment by <int>)
            n-<int>  (suffix decrement by <int>)

        Raises ParseError for any non-updater expression in the update position.

        The ``n`` is NOT a keyword -- it is only special in this context.
        """
        from parser.parser import ParseError

        result = self._detect_updater_pattern(self.env)
        if result is not None:
            op, position, amount, consumed, peek_after, _ = result
            # In header position, the updater must be followed by a terminator
            terminators = (TokenType.COLON, TokenType.COMMA, TokenType.HASH)
            if peek_after is not None and peek_after.type in terminators:
                tok_line = self.env.current().line
                for _ in range(consumed):
                    self.env.advance()
                return ForUpdaterNode(operator=op, position=position,
                                      amount=amount, line=tok_line)

        # Invalid -- reject non-updater forms in loop update position
        tok = self.env.current()
        raise ParseError(
            "?For/?While: Invalid iteration argument. "
            "Only contextual updater forms are valid: n+, +n, n-, -n, n+<num>, n-<num>. "
            "(Plain 'n' remains an ordinary identifier everywhere else.)",
            tok,
        )

    # ── Contextual updater as statement (RC2-06C body-level updater) ───

    def _try_parse_updater_stmt(self) -> Optional[ForUpdaterNode]:
        """Try to parse a contextual updater as a standalone body statement.

        Delegates pattern detection to the shared ``_detect_updater_pattern()``
        method (the SINGLE canonical location for ``n`` token-sequence detection).

        Recognizes the same updater forms as ``_parse_loop_iteration()``:

            n+       (suffix increment by 1)
            +n       (prefix increment by 1)
            n-       (suffix decrement by 1)
            -n       (prefix decrement by 1)
            n+<int>  (suffix increment by <int>)
            n-<int>  (suffix decrement by <int>)

        Unlike ``_parse_loop_iteration()``, this method returns ``None``
        when the current position does NOT match an updater, instead of
        raising ParseError.  This allows the body parser to fall through
        to normal statement parsing.

        The updater tokens are consumed ONLY when matched.

        To distinguish standalone ``n+`` from the start of an expression
        like ``n + 1``, this method checks that the pattern is immediately
        followed by a line break (a different line) or by a terminator.

        Returns
        -------
        ForUpdaterNode | None
        """
        result = self._detect_updater_pattern(self.env)
        if result is not None:
            op, position, amount, consumed, peek_after, op_line = result
            # In body position, the token after the pattern must be on a
            # DIFFERENT line or be a block terminator (HASH, EOF).
            if peek_after is not None and (
                peek_after.line > op_line
                or peek_after.type in (TokenType.HASH, TokenType.EOF)
            ):
                tok_line = self.env.current().line
                for _ in range(consumed):
                    self.env.advance()
                return ForUpdaterNode(operator=op, position=position,
                                      amount=amount, line=tok_line)

        return None

    def _parse_loop_body(
        self,
        terminators: frozenset[TokenType] = frozenset(),
    ) -> list:
        """Parse a loop body with contextual updater interception.

        This method wraps the standard body parser to intercept contextual
        updater statements (n+, +n, n-, -n) BEFORE they reach the statement
        parser.  Updater tokens are converted to ForUpdaterNode and added
        to the body.  All other statements are delegated to the configured
        body parser (``_parse_body_func``).

        Parameters
        ----------
        terminators : frozenset[TokenType]
            Token types that terminate the body.

        Returns
        -------
        list[Node]
        """
        from parser.ra_ast import Node

        body: list[Node] = []
        active = self.env.body_terminators | terminators
        saved = self.env.body_terminators
        self.env.body_terminators = active
        saved_depth = self.env.nested_block_depth
        self.env.nested_block_depth += 1
        try:
            while not self.env.check(TokenType.EOF):
                if self.env.check(*active):
                    break
                # ── Try contextual updater first ──────────────────────
                updater = self._try_parse_updater_stmt()
                if updater is not None:
                    body.append(updater)
                    continue
                # ── Delegate to configured statement parser ───────────
                # The facade sets _stmt_parser to the fully configured
                # StatementParser instance.  If not configured, fall through
                # to _parse_body_func for backward compatibility.
                if self._stmt_parser is not None:
                    stmt = self._stmt_parser.parse_stmt()
                elif self._parse_body_func is not None:
                    # No _stmt_parser configured; use _parse_body_func to
                    # parse ALL remaining body statements at once (no updater
                    # interception for this edge case).
                    remaining = list(self._parse_body_func(terminators=active))
                    body.extend(remaining)
                    break
                else:
                    stmt = None
                if stmt is not None:
                    body.append(stmt)
        finally:
            self.env.nested_block_depth = saved_depth
            self.env.body_terminators = saved
        return body

    # ── Canonical For ────────────────────────────────────────────────────

    def parse_for(self, q_tok: Token) -> ForNode:
        """Parse a primary for loop with canonical syntax.

        Syntax 1 — Pre-declared:
            ? For.<condition>, <iteration>:
                body...
            #

        Syntax 2 — Inline declaration:
            ? For.<declaration>, <condition>, <iteration>:
                body...
            #
        """
        self.env.advance()  # consume 'For'
        self.env.consume(TokenType.DOT, "Expected '.' after 'For'")

        # Suppress method-call ':' during header parsing
        saved_suppress = self._suppress_expression_method_call()
        try:
            # ── Disambiguate Syntax 1 vs Syntax 2 ──────────────────────
            if self._is_assignment_at_current():
                # Syntax 2: inline declaration
                var_tok = self.env.advance()  # consume variable name
                self.env.consume(TokenType.ASSIGN, "Expected '=' after loop variable")
                init_val = self._parse_primary_chain()
                initializer = AssignmentNode(
                    var_type=None, name=var_tok.value,
                    value=init_val, line=var_tok.line,
                )
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after inline declaration in For")
                condition = self._parse_expression()
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after condition in For")
                iteration = self._parse_loop_iteration()
                loop_var = var_tok.value
            else:
                # Syntax 1: pre-declared — first component is condition
                condition = self._parse_expression()
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after condition in For")
                iteration = self._parse_loop_iteration()
                initializer = None
                # Extract variable name from condition for auto-increment
                loop_var = self._extract_var_from_condition(condition)
        finally:
            self._restore_expression_method_call(saved_suppress)

        # ── Body separator (':' or ',') ─────────────────────────────────
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            from parser.parser import ParseError
            raise ParseError(
                "Expected ':' or ',' after For header components",
                self.env.current(),
            )

        # ── Body (with contextual updater interception) ────────────────
        body = self._parse_loop_body(terminators=frozenset({TokenType.HASH}))
        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return ForNode(
            variable=loop_var, condition=condition,
            iteration=iteration, initializer=initializer,
            body=body, line=q_tok.line, auto_close=not has_close,
        )

    # ── Canonical While ──────────────────────────────────────────────────

    # ── Shared canonical updater normalization (RC3-08I) ───────────────

    @staticmethod
    def canonicalize_updater_expression(
        expr: Node,
        target_var: str,
    ) -> Optional[ForUpdaterNode]:
        """Recognize a contextual updater expression pattern and return a
        canonical ``ForUpdaterNode``.

        This is the SINGLE canonical location where the ``n`` contextual
        updater symbol is interpreted.  Both header-level updaters
        (``n+``/``n-``/``n+2``/``n-2``) and argument-level updaters
        (``i=n+2`` inside Do-While ``#. while:``) resolve through this
        method.

        Recognized patterns::

            n+            ->  ForUpdaterNode(op="+", amount=1)
            n+2           ->  ForUpdaterNode(op="+", amount=2)
            n-            ->  ForUpdaterNode(op="-", amount=1)
            n-2           ->  ForUpdaterNode(op="-", amount=2)

        Parameters
        ----------
        expr       : Node  — the parsed expression (e.g. a BinaryOpNode).
        target_var : str   — the loop variable name that replaces ``n``.

        Returns
        -------
        ForUpdaterNode | None
            The canonical updater node if *expr* matches the
            ``n +<amount>`` or ``n -<amount>`` pattern, or ``None``
            if the expression is not a recognized contextual updater.
        """
        if not isinstance(expr, BinaryOpNode):
            return None
        if not (isinstance(expr.left, IdentifierNode)
                and expr.left.name == "n"):
            return None
        if expr.operator not in ("+", "-"):
            return None
        if not isinstance(expr.right, (LiteralNode, IdentifierNode)):
            return None

        # Extract amount from LiteralNode or default to 1 for bare n+
        amount = 1
        if isinstance(expr.right, LiteralNode):
            try:
                amount = int(expr.right.value)
            except (ValueError, TypeError):
                amount = 1
        if isinstance(expr.right, IdentifierNode):
            # IdentifierNode right-hand side — only accept if it's a
            # numeric literal identifier (e.g. a constant).  Default to 1.
            amount = 1

        return ForUpdaterNode(
            operator=expr.operator,
            position="suffix",
            amount=amount,
            line=expr.line,
        )

    def _extract_var_from_condition(self, condition: Node) -> str:
        """Try to extract the loop variable name from a condition expression.

        Handles common patterns:
          - IdentifierNode (bare variable)
          - BinaryOpNode with IdentifierNode left (e.g. x < 10 -> 'x')
        Returns empty string if extraction fails.
        """
        if isinstance(condition, IdentifierNode):
            return condition.name
        if isinstance(condition, BinaryOpNode):
            if isinstance(condition.left, IdentifierNode):
                return condition.left.name
        return ""

    def parse_while(self, q_tok: Token) -> WhileNode:
        """Parse a primary while loop with canonical syntax.

        Syntax 1 — Pre-declared with contextual updater (RC2-06C):
            i = 0
            ? While.i < 10, n+:
                body...
            #

        Syntax 2 — Inline declaration with manual increment:
            ? While.i = 0, i <= 5:
                body...
                <increment/decrement>
            #

        Syntax 3 — Bare condition (RC3-08G):
            ? While.x > 0:
                body...
            #
        """
        self.env.advance()  # consume 'While'
        self.env.consume(TokenType.DOT, "Expected '.' after 'While'")

        # Suppress method-call ':' during header parsing
        saved_suppress = self._suppress_expression_method_call()
        try:
            # ── Disambiguate Syntax 1 vs Syntax 2 vs Syntax 3 ──────────
            if self._is_assignment_at_current():
                # Syntax 2: inline declaration (no auto iteration)
                var_tok = self.env.advance()
                self.env.consume(TokenType.ASSIGN,
                    "Expected '=' after loop variable in While")
                init_val = self._parse_primary_chain()
                initializer = AssignmentNode(
                    var_type=None, name=var_tok.value,
                    value=init_val, line=var_tok.line,
                )
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after inline declaration in While")
                condition = self._parse_expression()
                iteration = None  # No auto iteration — manual inc/dec in body
                while_var = var_tok.value
            else:
                # Syntax 1 or 3: parse condition first, then decide
                condition = self._parse_expression()
                if self.env.check(TokenType.COLON):
                    # Syntax 3: bare condition (no updater)
                    iteration = None
                    initializer = None
                    while_var = self._extract_var_from_condition(condition)
                else:
                    # Syntax 1: pre-declared with updater
                    self.env.consume(TokenType.COMMA,
                        "Expected ',' after condition in While")
                    iteration = self._parse_loop_iteration()
                    initializer = None
                    while_var = self._extract_var_from_condition(condition)
        finally:
            self._restore_expression_method_call(saved_suppress)

        # ── Body separator ──────────────────────────────────────────────
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            from parser.parser import ParseError
            raise ParseError(
                "Expected ':' or ',' after While header components",
                self.env.current(),
            )

        # ── Body ────────────────────────────────────────────────────────
        body = self._parse_loop_body(terminators=frozenset({TokenType.HASH}))
        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return WhileNode(
            variable=while_var, condition=condition, iteration=iteration,
            initializer=initializer, body=body,
            line=q_tok.line, auto_close=not has_close,
        )

    # ── Nested for / while (inside executable blocks) ───────────────────

    def parse_nested_for(self) -> ForNode:
        """Parse a nested for loop inside an executable block.

        Canonical nested forms:

        Syntax 1 — Pre-declared:
            for.j < 10, 5:
                p j
            #

        Syntax 2 — Inline declaration:
            for.j = 0, j < 10, 5:
                p j
            #

        Raises NestedBlockSyntaxError if not inside a block.
        """
        from EHub.PE.statement_parser import NestedBlockSyntaxError

        if self.env.nested_block_depth == 0:
            raise NestedBlockSyntaxError(
                "'for' is only valid inside an executable block. "
                "Use '?For' at the top level instead."
            )

        for_tok = self.env.advance()  # consume 'for'

        # Optional dot after 'for'
        if self.env.check(TokenType.DOT):
            self.env.advance()

        saved_suppress = self._suppress_expression_method_call()
        try:
            if self._is_assignment_at_current():
                # Syntax 2: inline declaration
                var_tok = self.env.advance()
                self.env.consume(TokenType.ASSIGN,
                    "Expected '=' after loop variable in nested for")
                init_val = self._parse_primary_chain()
                initializer = AssignmentNode(
                    var_type=None, name=var_tok.value,
                    value=init_val, line=var_tok.line,
                )
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after inline declaration in nested for")
                condition = self._parse_expression()
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after condition in nested for")
                iteration = self._parse_loop_iteration()
                loop_var = var_tok.value
            else:
                # Syntax 1: pre-declared
                condition = self._parse_expression()
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after condition in nested for")
                iteration = self._parse_loop_iteration()
                initializer = None
                loop_var = self._extract_var_from_condition(condition)
        finally:
            self._restore_expression_method_call(saved_suppress)

        # Body separator: ':' or ','
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            from parser.parser import ParseError
            raise ParseError(
                "Expected ':' or ',' after nested for clause",
                self.env.current(),
            )

        body = self._parse_loop_body(terminators=frozenset({TokenType.HASH}))
        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return ForNode(
            variable=loop_var, condition=condition,
            iteration=iteration, initializer=initializer,
            body=body, line=for_tok.line, auto_close=not has_close,
        )

    def parse_nested_while(self) -> WhileNode:
        """Parse a nested while loop inside an executable block.

        Canonical nested forms:

        Syntax 1 — Pre-declared with contextual updater (RC2-06C):
            while.j < 10, n+:
                p j
            #

        Syntax 2 — Inline manual:
            while.j = 0, j <= 5:
                p j
                j++
            #

        Raises NestedBlockSyntaxError if not inside a block.
        """
        from EHub.PE.statement_parser import NestedBlockSyntaxError

        if self.env.nested_block_depth == 0:
            raise NestedBlockSyntaxError(
                "'while' is only valid inside an executable block. "
                "Use '?While' at the top level instead."
            )

        while_tok = self.env.advance()  # consume 'while'

        # Optional dot after 'while'
        if self.env.check(TokenType.DOT):
            self.env.advance()

        saved_suppress = self._suppress_expression_method_call()
        try:
            if self._is_assignment_at_current():
                # Syntax 2: inline declaration, no auto iteration
                var_tok = self.env.advance()
                self.env.consume(TokenType.ASSIGN,
                    "Expected '=' after loop variable in nested while")
                init_val = self._parse_primary_chain()
                initializer = AssignmentNode(
                    var_type=None, name=var_tok.value,
                    value=init_val, line=var_tok.line,
                )
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after inline declaration in nested while")
                condition = self._parse_expression()
                iteration = None
                while_var = var_tok.value
            else:
                # Syntax 1: pre-declared with contextual updater
                condition = self._parse_expression()
                self.env.consume(TokenType.COMMA,
                    "Expected ',' after condition in nested while")
                iteration = self._parse_loop_iteration()
                initializer = None
                while_var = self._extract_var_from_condition(condition)
        finally:
            self._restore_expression_method_call(saved_suppress)

        # Body separator: ':' or ','
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            from parser.parser import ParseError
            raise ParseError(
                "Expected ':' or ',' after nested while clause",
                self.env.current(),
            )

        body = self._parse_loop_body(terminators=frozenset({TokenType.HASH}))
        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return WhileNode(
            variable=while_var, condition=condition, iteration=iteration,
            initializer=initializer, body=body,
            line=while_tok.line, auto_close=not has_close,
        )

    # ── Primary ?In (RC3-01A — Unified Loop Family) ──────────────────
    #
    # Note: nested 'In' (without ? prefix, inside executable blocks) is
    # not yet supported at the parser level.  The runtime supports InNode
    # inside methods/functions — tested via AST construction in
    # TestMethodContainingIn and TestFunctionContainingIn.
    # A future sprint should add an IN_NESTED token type to the lexer
    # and dispatch in StatementParser (matching FOR_NESTED/WHILE_NESTED).
    # ──────────────────────────────────────────────────────────────────

    def parse_in(self, q_tok: Token) -> InNode:
        """Parse a primary ?In loop with unified syntax.

        Canonical syntax (RC3-01B):

          Type 1 — Membership Check (uses ``in`` keyword):
              ? In.i = value in container:
                  body
              #

          Type 2 — Range Iteration (comma separator):
              ? In.i = start, end:
                  body
              #

          Type 3 — Range Iteration With Step (comma separator):
              ? In.i = start, end, step:
                  body
              #

        The DOT after ``In`` unifies the ?In header syntax with
        ``? For.`` and ``? While.`` — all three Loop Family members
        now use the same header structure.

        The ``in`` keyword (RC3-01B) disambiguates Type 1 membership
        from Type 2/3 range iteration at parse time — no more ambiguity
        between ``value, container`` and ``start, end``.
        """
        self.env.advance()  # consume 'In' identifier

        # ── Consume DOT (RC3-01A — unified with For/While) ────────────
        self.env.consume(TokenType.DOT, "Expected '.' after 'In'")

        # ── Loop variable ───────────────────────────────────────────────
        var_tok = self.env.consume(
            TokenType.IDENTIFIER,
            "?In: Expected loop variable after '?In.'",
        )

        # ── '=' ─────────────────────────────────────────────────────────
        self.env.consume(TokenType.ASSIGN, "?In: Expected '=' after loop variable")

        # ── Suppress method-call ':' consumption while parsing header ───
        saved_suppress = self._suppress_expression_method_call()
        try:
            # ── Source expression ───────────────────────────────────────
            source = self._parse_in_source()

            # ── Detect Type 1 (membership) vs Type 2/3 (range) ──────────
            # RC3-01B: ``in`` keyword unambiguously marks membership.
            step: Optional[Node] = None
            if self.env.check(TokenType.IDENTIFIER) and self.env.current().value == "in":
                # ── Type 1 — Membership Check ───────────────────────
                self.env.advance()  # consume 'in' keyword
                limit = self._parse_in_source()
                # No step for Type 1
            else:
                # ── Type 2/3 — Range Iteration ──────────────────────
                self.env.consume(TokenType.COMMA, "?In: Expected ',' or 'in' after source value")
                limit = self._parse_in_source()
                # Optional step (Type 3 only)
                if self.env.check(TokenType.COMMA):
                    self.env.advance()
                    step = self._parse_expression()
        finally:
            self._restore_expression_method_call(saved_suppress)

        # ── Body separator: ':' or ',' ──────────────────────────────────
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            from parser.parser import ParseError
            raise ParseError(
                "?In: Expected ':' after loop header",
                self.env.current(),
            )

        # ── Body ────────────────────────────────────────────────────────
        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
        else:
            body = []
        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return InNode(
            variable=var_tok.value,
            source=source,
            limit=limit,
            step=step,
            body=body,
            line=q_tok.line,
            auto_close=not has_close,
        )

    def _parse_in_source(self) -> Node:
        """Parse the source/limit expression for ?In.

        Handles:
          - Scalar: integer, identifier, expression
          - Collection: [item, item, ...]
        """
        if self.env.check(TokenType.LBRACKET):
            return self._parse_in_list()
        # Suppress method-call ':' so the ':' body separator isn't eaten
        saved_suppress = self._suppress_expression_method_call()
        try:
            return self._parse_primary_chain()
        finally:
            self._restore_expression_method_call(saved_suppress)

    def _parse_in_list(self) -> ListNode:
        """Parse a list literal: [item, item, ...]"""
        tok = self.env.advance()  # consume '['
        items: list[Node] = []
        if not self.env.check(TokenType.RBRACKET):
            items.append(self._parse_expression())
            while self.env.check(TokenType.COMMA):
                self.env.advance()
                items.append(self._parse_expression())
        self.env.consume(TokenType.RBRACKET, "?In: Expected ']' after list items")
        return ListNode(items=items, line=tok.line)

    # ── ?Which (RC3-03A) ────────────────────────────────────────────────

    def _parse_which_branch(self) -> Optional[WhichBranchNode]:
        """Parse a single branch inside ? Which.

        Recognized branch syntaxes:

          - For branch: ``For.<var> = <start>, <end>: <body> #``
            Creates a ForNode with ``i = start``, condition ``i < end``,
            and ``n+`` auto-increment.

          - While branch: ``While.<condition>: <body> #``
            Creates a WhileNode with the given condition.

          - Other statements: delegated to ``parse_stmt()``
            (e.g. ``? In``, ``? Which``, ``? What``, or any normal statement)

        Returns
        -------
        WhichBranchNode | None
        """
        from parser.parser import ParseError

        # ── For branch: For.<var> = <start>, <end>: ───────────────────
        if (self.env.check(TokenType.IDENTIFIER)
                and self.env.current().value == "For"):
            return self._parse_which_for_branch()

        # ── Lowercase for branch: for.<var> = <start>, <end>: ─────────
        if self.env.check(TokenType.FOR_NESTED):
            dot_tok = self.env.peek(1)
            if (dot_tok is not None and dot_tok.type == TokenType.DOT):
                ident_tok = self.env.peek(2)
                if (ident_tok is not None
                        and ident_tok.type == TokenType.IDENTIFIER):
                    after_ident = self.env.peek(3)
                    if (after_ident is not None
                            and after_ident.type == TokenType.ASSIGN):
                        return self._parse_which_for_branch()
            # for without DOT+ID+ASSIGN → fall through to parse_stmt

        # ── While branch: While.<condition>: ───────────────────────────
        if (self.env.check(TokenType.IDENTIFIER)
                and self.env.current().value == "While"):
            return self._parse_which_while_branch()

        # ── Lowercase while branch: while.<condition>: ─────────────────
        if self.env.check(TokenType.WHILE_NESTED):
            dot_tok = self.env.peek(1)
            if dot_tok is not None and dot_tok.type == TokenType.DOT:
                return self._parse_which_while_branch()
            # while without DOT → fall through to parse_stmt

        # ── Everything else: delegate to statement parser ─────────────
        if self._stmt_parser is not None:
            stmt = self._stmt_parser.parse_stmt()
            if stmt is not None:
                branch_type = self._classify_branch_type(stmt)
                var_name = self._extract_branch_variable(stmt)
                return WhichBranchNode(
                    variable=var_name,
                    body=[stmt],
                    branch_type=branch_type,
                    branch_node=stmt if branch_type in ("For", "While", "In") else None,
                    line=stmt.line,
                    auto_close=False,
                )
        return None

    def _parse_which_for_branch(self) -> WhichBranchNode:
        """Parse a For branch inside Which.

        Syntax::

            For.<var> = <start>, <end>:
                body
            #

        Creates a ForNode with auto-generated condition ``var < end``
        and ``n+`` auto-increment.
        """
        from parser.parser import ParseError

        tok = self.env.advance()  # consume 'For'
        self.env.consume(TokenType.DOT, "?Which For branch: Expected '.' after 'For'")
        var_tok = self.env.consume(
            TokenType.IDENTIFIER,
            "?Which For branch: Expected variable name after 'For.'",
        )
        self.env.consume(
            TokenType.ASSIGN,
            "?Which For branch: Expected '=' after variable",
        )

        saved_suppress = self._suppress_expression_method_call()
        try:
            start_expr = self._parse_primary_chain()
            self.env.consume(
                TokenType.COMMA,
                "?Which For branch: Expected ',' after start value",
            )
            end_expr = self._parse_expression()
        finally:
            self._restore_expression_method_call(saved_suppress)

        # Body separator: ':' or ','
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            raise ParseError(
                "Expected ':' after For branch header",
                self.env.current(),
            )

        # Parse body (terminated by '#')
        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
        else:
            body = []
        has_hash = self.env.check(TokenType.HASH)
        if has_hash:
            self.env.advance()

        # Build ForNode with auto-generated condition and iteration
        condition = BinaryOpNode(
            left=IdentifierNode(name=var_tok.value, line=var_tok.line),
            operator="<",
            right=end_expr,
            line=var_tok.line,
        )
        iteration = ForUpdaterNode(
            operator="+", position="suffix", line=var_tok.line,
        )
        initializer = AssignmentNode(
            var_type=None, name=var_tok.value,
            value=start_expr, line=var_tok.line,
        )
        for_node = ForNode(
            variable=var_tok.value,
            condition=condition,
            iteration=iteration,
            initializer=initializer,
            body=body,
            line=tok.line,
            auto_close=False,
        )

        return WhichBranchNode(
            variable=var_tok.value,
            body=[for_node],
            branch_type="For",
            branch_node=for_node,
            line=tok.line,
            auto_close=False,
        )

    def _parse_which_while_branch(self) -> WhichBranchNode:
        """Parse a While branch inside Which.

        Syntax::

            While.<condition>:
                body
            #

        Wraps the condition into a WhileNode.
        """
        from parser.parser import ParseError

        tok = self.env.advance()  # consume 'While'
        self.env.consume(TokenType.DOT, "?Which While branch: Expected '.' after 'While'")

        saved_suppress = self._suppress_expression_method_call()
        try:
            condition = self._parse_expression()
        finally:
            self._restore_expression_method_call(saved_suppress)

        # Body separator: ':' or ','
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif self.env.check(TokenType.COMMA):
            self.env.advance()
        else:
            raise ParseError(
                "Expected ':' after While branch header",
                self.env.current(),
            )

        # Parse body
        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
        else:
            body = []
        has_hash = self.env.check(TokenType.HASH)
        if has_hash:
            self.env.advance()

        while_node = WhileNode(
            variable=self._extract_var_from_condition(condition),
            condition=condition,
            iteration=None,
            initializer=None,
            body=body,
            line=tok.line,
            auto_close=False,
        )

        return WhichBranchNode(
            variable=while_node.variable,
            body=[while_node],
            branch_type="While",
            branch_node=while_node,
            line=tok.line,
            auto_close=False,
        )

    @staticmethod
    def _classify_branch_type(stmt: Node) -> str:
        """Classify a statement into a Which branch type string."""
        if isinstance(stmt, ForNode):
            return "For"
        if isinstance(stmt, WhileNode):
            return "While"
        if isinstance(stmt, InNode):
            return "In"
        if isinstance(stmt, WhichControlNode):
            return "Which"
        if isinstance(stmt, WhatPreconditionNode):
            return "What"
        return ""

    @staticmethod
    def _extract_branch_variable(stmt: Node) -> str:
        """Extract the controlling variable from a branch statement."""
        if isinstance(stmt, ForNode):
            return stmt.variable
        if isinstance(stmt, WhileNode):
            return stmt.variable if stmt.variable else ""
        if isinstance(stmt, InNode):
            return stmt.variable
        return ""

    def parse_which(self, q_tok: Token) -> WhichControlNode:
        """Parse a ?Which selection control-flow block.

        Syntax::

            ? Which:
                For.i = 0, 5:
                    p i
                #
                For.j = 0, 2:
                    p j
                #
            #. i = 1, j = 2

        Each branch is a control-flow construct (For, While, In,
        nested Which/What) terminated by ``#``.  The Which block is closed
        by ``#. selectors``.

        Selector values are bound to the selected branch's controlling
        variable before execution.
        """
        from parser.parser import ParseError

        self.env.advance()  # consume 'Which' identifier

        # ── RC3-08J: Check for ? Which.<Name>: (named Which controller) ─
        which_name: Optional[str] = None
        if self.env.check(TokenType.DOT):
            self.env.advance()  # consume '.'
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected Which name after '? Which.'",
            )
            which_name = name_tok.value

        # Consume ':' separator
        if self.env.check(TokenType.COLON):
            self.env.advance()
        elif which_name is not None:
            raise ParseError(
                "Expected ':' after '? Which.<Name>'",
                self.env.current(),
            )
        else:
            raise ParseError(
                "Expected ':' after '? Which'",
                self.env.current(),
            )

        # ── RC3-08J: Named Which controllers delegate to CF body parser ─
        if which_name is not None:
            which_node = WhichControlNode(
                name=which_name,
                branches=[],
                selectors=None,
                line=q_tok.line,
                auto_close=False,
            )
            if self._stmt_parser is not None:
                parse_cf_body = getattr(
                    self._stmt_parser, '_parse_cf_which_body', None,
                )
                if parse_cf_body is not None:
                    parse_cf_body(which_name, which_node)
            return which_node

        # ── Parse branches ─────────────────────────────────────────────
        saved_depth = self.env.nested_block_depth
        self.env.nested_block_depth += 1
        branches: list[WhichBranchNode] = []
        try:
            while not self.env.check(TokenType.EOF):
                # Check for closing #. (HASH followed by DOT)
                if self.env.check(TokenType.HASH):
                    nxt = self.env.peek(1)
                    if nxt is not None and nxt.type == TokenType.DOT:
                        break  # This is #. (closing selector)
                    # Plain HASH — produced by _parse_body_func terminator
                    # Skip it so we don't confuse it with #.
                    self.env.advance()
                    continue

                # Parse branch using dedicated method
                branch = self._parse_which_branch()
                if branch is not None:
                    branches.append(branch)
                else:
                    break
        finally:
            self.env.nested_block_depth = saved_depth

        # ── Parse selectors (after #.) ─────────────────────────────────
        selectors: Optional[dict[str, Node]] = {}
        has_hash = self.env.check(TokenType.HASH)
        if has_hash:
            dot_line = self.env.current().line
            self.env.advance()  # consume '#'
            if self.env.check(TokenType.DOT):
                dot_line = self.env.current().line
                self.env.advance()  # consume '.'
                # Parse selector: variable = value, ... #
                # Stops at newline, HASH, or EOF so subsequent tokens are
                # not consumed as selectors (important for nesting).
                while not self.env.check(TokenType.HASH, TokenType.EOF):
                    if self.env.current().line > dot_line:
                        break
                    var_tok = self.env.consume(
                        TokenType.IDENTIFIER,
                        "?Which: Expected variable name in selector",
                    )
                    self.env.consume(
                        TokenType.ASSIGN,
                        "?Which: Expected '=' after selector variable",
                    )
                    value = self._parse_expression()
                    if var_tok.value in selectors:
                        raise ParseError(
                            f"?Which: Duplicate selector '{var_tok.value}'",
                            var_tok,
                        )
                    selectors[var_tok.value] = value
                    if self.env.check(TokenType.COMMA):
                        if self.env.peek(1) is not None and self.env.peek(1).line > dot_line:
                            break
                        self.env.advance()
                # Consume closing '#'
                if self.env.check(TokenType.HASH):
                    self.env.advance()
            else:
                # Had HASH but no DOT — it was just a body terminator
                selectors = None
        else:
            selectors = None

        if not selectors:
            selectors = None

        return WhichControlNode(
            branches=branches,
            selectors=selectors,
            line=q_tok.line,
            auto_close=False,
        )

    # ── ?Do (RC3-08A) ──────────────────────────────────────────────────

    def parse_do(self, q_tok: Token) -> DoWhileNode:
        """Parse a do-while loop.

        Syntax::

            ? Do:
                body...
            #. while: condition, arg1 = val1

        The body executes first, then the condition is checked.
        Arguments from the ``#. while:`` line are evaluated before
        the first iteration.
        """
        from parser.parser import ParseError

        self.env.advance()  # consume 'Do' identifier

        if self.env.check(TokenType.COLON):
            self.env.advance()
        else:
            raise ParseError(
                "Expected ':' after '? Do'",
                self.env.current(),
            )

        # ── Parse body statements until we see #. ──────────────────────
        body: list[Node] = []
        saved_depth = self.env.nested_block_depth
        self.env.nested_block_depth += 1
        try:
            while not self.env.check(TokenType.EOF):
                if self.env.check(TokenType.HASH):
                    nxt = self.env.peek(1)
                    if nxt is not None and nxt.type == TokenType.DOT:
                        break  # #. — closing with while:
                    # Plain HASH — consumed by body statements
                    self.env.advance()
                    continue

                # ── Try contextual updater first (n+, +n, n-, -n) ─────
                updater = self._try_parse_updater_stmt()
                if updater is not None:
                    body.append(updater)
                    continue

                if self._stmt_parser is not None:
                    stmt = self._stmt_parser.parse_stmt()
                    if stmt is not None:
                        body.append(stmt)
                    else:
                        break
                else:
                    break
        finally:
            self.env.nested_block_depth = saved_depth

        # ── Parse #. while: condition, args ────────────────────────────
        condition: Optional[Node] = None
        arguments: Optional[dict[str, Node]] = {}
        variable: str = ""

        has_hash = self.env.check(TokenType.HASH)
        if has_hash:
            dot_line = self.env.current().line
            self.env.advance()  # consume '#'
            if self.env.check(TokenType.DOT):
                dot_line = self.env.current().line
                self.env.advance()  # consume '.'

                # Expect 'while:' keyword
                if ((self.env.check(TokenType.IDENTIFIER) and self.env.current().value == "while")
                        or self.env.check(TokenType.WHILE_NESTED)):
                    self.env.advance()  # consume 'while'
                    self.env.consume(
                        TokenType.COLON,
                        "?Do: Expected ':' after 'while'",
                    )

                    # Parse condition expression
                    condition = self._parse_expression()

                    # Parse optional arguments: , var = value, ...
                    updater_args: set[str] = set()
                    if self.env.check(TokenType.COMMA):
                        self.env.advance()
                        while not self.env.check(TokenType.HASH, TokenType.EOF):
                            if self.env.current().line > dot_line:
                                break
                            var_tok = self.env.consume(
                                TokenType.IDENTIFIER,
                                "?Do: Expected variable name in argument",
                            )
                            self.env.consume(
                                TokenType.ASSIGN,
                                "?Do: Expected '=' after argument variable",
                            )
                            value = self._parse_expression()
                            if var_tok.value in arguments:
                                raise ParseError(
                                    f"?Do: Duplicate argument '{var_tok.value}'",
                                    var_tok,
                                )
                            # ── Detect n+<num> / n-<num> contextual updater pattern ──
                            # Use the shared canonical updater normalization (RC3-08I).
                            # If the argument value matches ``n + <int>`` or ``n - <int>``,
                            # replace the BinaryOpNode with a canonical ForUpdaterNode.
                            updater = self.canonicalize_updater_expression(
                                value, var_tok.value,
                            )
                            if updater is not None:
                                value = updater
                                updater_args.add(var_tok.value)
                            arguments[var_tok.value] = value
                            if self.env.check(TokenType.COMMA):
                                if (self.env.peek(1) is not None
                                        and self.env.peek(1).line > dot_line):
                                    break
                                self.env.advance()

                # Consume trailing '#'
                if self.env.check(TokenType.HASH):
                    self.env.advance()
            else:
                arguments = None
        else:
            arguments = None

        if not arguments:
            arguments = None

        # Extract variable name from condition
        if condition is not None:
            if isinstance(condition, IdentifierNode):
                variable = condition.name
            elif isinstance(condition, BinaryOpNode):
                if isinstance(condition.left, IdentifierNode):
                    variable = condition.left.name

        return DoWhileNode(
            body=body,
            condition=condition,
            arguments=arguments,
            variable=variable,
            updater_args=updater_args,
            line=q_tok.line,
            auto_close=False,
        )

    # ── ?What (RC3-03A) ────────────────────────────────────────────────

    def parse_what(self, q_tok: Token) -> WhatPreconditionNode:
        """Parse a ?What precondition control-flow block.

        Syntax::

            ? What:
                if condition:
                    then_body...
                #
                else
                    else_body...
                #
            #. variable = value

        The ``if`` / ``else`` branches are parsed using the standard
        nested ``if``/``else`` statement parser.  The closing ``#.``
        provides argument bindings for the precondition.

        Raises a semantic error if ``ElseIf`` is found inside the
        What block (checked by semantic analyzer).
        """
        from parser.parser import ParseError

        self.env.advance()  # consume 'What' identifier

        if self.env.check(TokenType.COLON):
            self.env.advance()
        else:
            raise ParseError(
                "Expected ':' after '? What'",
                self.env.current(),
            )

        # ── Parse body statements until we see #. ──────────────────────
        saved_depth = self.env.nested_block_depth
        self.env.nested_block_depth += 1
        body_stmts: list[Node] = []
        try:
            while not self.env.check(TokenType.EOF):
                if self.env.check(TokenType.HASH):
                    nxt = self.env.peek(1)
                    if nxt is not None and nxt.type == TokenType.DOT:
                        break  # #. — closing arguments
                    # Plain HASH — consumed by if/else branch terminator
                    self.env.advance()
                    continue

                if self._stmt_parser is not None:
                    stmt = self._stmt_parser.parse_stmt()
                    if stmt is not None:
                        body_stmts.append(stmt)
                    else:
                        break
                else:
                    break
        finally:
            self.env.nested_block_depth = saved_depth

        # ── Parse arguments (after #.) ─────────────────────────────────
        arguments: Optional[dict[str, Node]] = {}
        has_hash = self.env.check(TokenType.HASH)
        if has_hash:
            dot_line = self.env.current().line
            self.env.advance()  # consume '#'
            if self.env.check(TokenType.DOT):
                dot_line = self.env.current().line
                self.env.advance()  # consume '.'
                while not self.env.check(TokenType.HASH, TokenType.EOF):
                    if self.env.current().line > dot_line:
                        break
                    var_tok = self.env.consume(
                        TokenType.IDENTIFIER,
                        "?What: Expected variable name in argument",
                    )
                    self.env.consume(
                        TokenType.ASSIGN,
                        "?What: Expected '=' after argument variable",
                    )
                    value = self._parse_expression()
                    if var_tok.value in arguments:
                        raise ParseError(
                            f"?What: Duplicate argument '{var_tok.value}'",
                            var_tok,
                        )
                    arguments[var_tok.value] = value
                    if self.env.check(TokenType.COMMA):
                        if self.env.peek(1) is not None and self.env.peek(1).line > dot_line:
                            break
                        self.env.advance()
                if self.env.check(TokenType.HASH):
                    self.env.advance()
            else:
                arguments = None
        else:
            arguments = None

        if not arguments:
            arguments = None

        # ── Extract condition from the first IfNode (RC3-08G) ────────
        # If the first body statement is an IfNode, extract its condition
        # into what.condition so execute_what can evaluate it as a
        # precondition. The if_body gets the IfNode's then_body, and
        # else_body gets the IfNode's else_body (if present).
        #
        # If there are elseif branches, keep the full IfNode in if_body
        # so that the elseif chain is preserved (the IfNode handles them).
        # In that case, condition is NOT extracted (stays None).
        if_body: list[Node] = list(body_stmts)
        else_body: list[Node] = []
        condition: Optional[Node] = None

        if body_stmts:
            first = body_stmts[0]
            if isinstance(first, IfNode) and not first.elseifs:
                # Simple if/else (no elif chain) — extract condition
                condition = first.condition
                if_body = list(first.then_body)
                if first.else_node is not None:
                    else_body = list(first.else_node.body)
            elif isinstance(first, IfNode) and first.elseifs:
                # With elseif chain — keep full IfNode in if_body
                # (do not extract, so elseif chain is preserved)
                pass

        return WhatPreconditionNode(
            if_body=if_body,
            else_body=else_body,
            condition=condition,
            arguments=arguments,
            line=q_tok.line,
            auto_close=False,
        )
