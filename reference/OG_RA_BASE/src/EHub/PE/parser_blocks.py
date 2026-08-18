"""parser_blocks.py — Block Family parser for the RA language.

Constitutionally required specialized parser for Block Family constructs:

  - .fun: ... f.close             (Function block — delegated to existing parser)
  - Print: ... / Print.<Name>:    (Print/output block — RC2-04A)
  - Ip: ... / Ip.<Name>:          (Input block — RC2-04A)
  - PF                             (Program Flow activation — delegated)
  - Db: ... / Db.<Name>:          (Database block — delegated)
  - Sdb.<Name>: ...               (Structured database block — delegated)

Block Family owns no loop grammar and no decision grammar.
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import TokenType
from parser.ra_ast import Node, PrintBlockNode, InputBlockNode
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class BlockParser:
    """Parses all Block Family constructs.

    Implemented:
      - Print: ... / Print.<Name>:    (Print/output block — RC2-04A)
      - Ip: ... / Ip.<Name>:          (Input block — RC2-04A)

    Delegated to the coordinator / existing parsers:
      - .fun: ... f.close             (Function block — FunctionParserMixin)
      - PF                             (Program Flow activation — PFParserMixin)
      - Db: ... / Db.<Name>:          (Database block — DatabaseParser)
      - Sdb.<Name>: ...               (Structured database block — DatabaseParser)

    TODO (future sprint): Move .fun, PF, Db, Sdb parsing logic
    into this module to fully isolate the Block Family grammar.

    Block Family owns no loop grammar and no decision grammar.
    """

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry
        self._parse_body_func: Optional[callable] = None
        self._stmt_parser: Optional[object] = None  # set by the facade
        self._expression_parser: Optional[object] = None  # set by the facade

    # ── Block parameter parsing (shared by Print and Ip blocks) ────────

    def _parse_block_params(self, accept_expressions: bool = False):
        """Parse comma-separated parameter/argument values after a block name.

        Syntax::

            Block.Name, a, b, c:        (identifiers)
            Block.Pattern, 5:           (integer expression)

        When *accept_expressions* is True, the parser accepts any expression
        (integer literals, identifiers, etc.) instead of only identifiers.
        This is used by Print Loop parameterized args like ``Print.Pattern,5:``.

        Parameters
        ----------
        accept_expressions : bool — when True, parse full expressions
                                     instead of only identifiers.

        Returns
        -------
        list[str | Node] — parameter names or expression nodes.
        """
        if accept_expressions:
            return self._parse_block_param_exprs()
        params: list = []
        while not self.env.check(TokenType.COLON, TokenType.EOF):
            param_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected parameter name after ','",
            )
            params.append(param_tok.value)
            if self.env.check(TokenType.COMMA):
                self.env.advance()
            else:
                break
        return params

    def _parse_block_param_exprs(self) -> list:
        """Parse comma-separated expression arguments after a block name.

        Syntax::

            Block.Pattern, 5:
            Block.Pattern, count:

        Returns
        -------
        list[Node] — parsed expression nodes.
        """
        args: list = []
        # Suppress method-call : so the : after params isn't consumed
        saved_suppress = False
        if self._expression_parser is not None:
            saved_suppress = getattr(
                self._expression_parser, '_suppress_method_call_suffix', False,
            )
            self._expression_parser._suppress_method_call_suffix = True
        try:
            while not self.env.check(TokenType.COLON, TokenType.EOF):
                if self._expression_parser is not None:
                    expr = self._expression_parser.parse_expression()
                else:
                    expr = self._parse_param_primary()
                args.append(expr)
                if self.env.check(TokenType.COMMA):
                    self.env.advance()
                else:
                    break
        finally:
            if self._expression_parser is not None:
                self._expression_parser._suppress_method_call_suffix = saved_suppress
        return args

    def _parse_param_primary(self):
        """Parse a primary expression for parameter lists."""
        from parser.ra_ast import LiteralNode, IdentifierNode
        tok = self.env.current()
        if tok.type == TokenType.INTEGER:
            self.env.advance()
            return LiteralNode(value=tok.value, kind=TokenType.INTEGER, line=tok.line)
        if tok.type == TokenType.IDENTIFIER:
            self.env.advance()
            return IdentifierNode(name=tok.value, line=tok.line)
        if tok.type == TokenType.STRING:
            self.env.advance()
            return LiteralNode(value=tok.value, kind=TokenType.STRING, line=tok.line)
        from parser.parser import ParseError
        raise ParseError(
            "Expected parameter value (number, identifier, or string)",
            tok,
        )

    # ── Print block ─────────────────────────────────────────────────────

    def parse_print_block(self) -> PrintBlockNode:
        """Parse a Print block.

        Syntax
        ------
            Print:
                body...

            Print.Greeting:
                body...

            Print.Pattern,5:
                body...

        Print Loop terminates at an empty executable source line
        (a blank line gap in the token stream).  Unlike other RA blocks,
        Print Loop does NOT use ``#`` as a terminator.
        """
        tok = self.env.consume(
            TokenType.PRINT_BLOCK,
            "Expected 'Print' to open a Print block",
        )

        name: Optional[str] = None
        params: list[str] = []
        if self.env.check(TokenType.DOT):
            self.env.advance()
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected block name after 'Print.'",
            )
            name = name_tok.value
            # Check for parameter list: Print.Name, a, b, c:  or Print.Pattern,5:
            if self.env.check(TokenType.COMMA):
                self.env.advance()
                # Use expression-accepting mode for Print args (supports
                # integer arguments like Print.Pattern,5:)
                params = self._parse_block_params(accept_expressions=True)

        self.env.consume(
            TokenType.COLON,
            "Expected ':' after Print block declaration",
        )

        # ── Parse body with empty-line termination ───────────────────
        # Print Loop terminates at an empty executable source line, NOT
        # at HASH.  We track the last body statement's line and check
        # if the next token has a blank-line gap (> 1 line gap) or EOF.
        body: list[Node] = []
        last_body_line: int = tok.line

        while not self.env.check(TokenType.EOF):
            cur = self.env.current()

            # If we encounter a sibling block start, stop early
            if self.env.check(TokenType.PRINT_BLOCK, TokenType.IP_BLOCK):
                break

            # Check for empty-line gap: if the next token is on a line
            # that is at least 2 greater than the last body statement's
            # line, there's a blank line — terminate the Print Loop.
            if body and cur.line > last_body_line + 1:
                break

            # If we encounter HASH, do NOT consume it — leave it for
            # the next statement parser (it's NOT a Print Loop terminator).
            if self.env.check(TokenType.HASH):
                break

            # Parse a statement using the configured statement parser
            if self._stmt_parser is not None:
                stmt = self._stmt_parser.parse_stmt()
            elif self._parse_body_func is not None:
                body_remaining = self._parse_body_func(
                    terminators=frozenset({TokenType.EOF}),
                )
                body.extend(body_remaining)
                break
            else:
                break

            if stmt is not None:
                body.append(stmt)
                last_body_line = stmt.line
            else:
                break

        # Do NOT consume HASH — it belongs to the next construct

        return PrintBlockNode(
            name=name,
            params=params,
            body=body,
            line=tok.line,
            auto_close=True,  # Print Loop always terminates naturally
        )

    # ── Input block ─────────────────────────────────────────────────────

    def parse_input_block(self) -> InputBlockNode:
        """Parse an Input block (Ip block).

        Syntax
        ------
            Ip:
                body...

            Ip.UserInput:
                body...

            Ip.Name, a, b, c:
                body...

            Ip.Name>a,b,c:
                body...

        Uses ``ip.close`` as body terminator when present, but the block
        also closes automatically at EOF.
        """
        tok = self.env.consume(
            TokenType.IP_BLOCK,
            "Expected 'Ip' to open an Input block",
        )

        name: Optional[str] = None
        params: list[str] = []
        if self.env.check(TokenType.DOT):
            self.env.advance()
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected block name after 'Ip.'",
            )
            name = name_tok.value
            # Check for '>' parameter syntax: Ip.Name>a,b,c:
            if self.env.check(TokenType.GT):
                self.env.advance()  # consume '>'
                params = self._parse_greater_params()
            # Check for ',' parameter syntax: Ip.Name, a, b, c:
            elif self.env.check(TokenType.COMMA):
                self.env.advance()
                params = self._parse_block_params()

        self.env.consume(
            TokenType.COLON,
            "Expected ':' after Ip block declaration",
        )

        body: list[Node] = []
        if self._parse_body_func is not None:
            body = self._parse_body_func(
                terminators=frozenset({
                    TokenType.IP_CLOSE,
                    TokenType.HASH,  # RC3-08I1: backward-compatible Ip.close via #
                    TokenType.PRINT_BLOCK,
                    TokenType.IP_BLOCK,
                    TokenType.EOF,
                }),
            )

        has_close = self.env.check(TokenType.IP_CLOSE)
        if has_close:
            self.env.advance()
        # RC3-08I1: consume HASH as backward-compatible Ip block terminator
        elif self.env.check(TokenType.HASH):
            self.env.advance()

        return InputBlockNode(
            name=name,
            params=params,
            body=body,
            line=tok.line,
            auto_close=not has_close,
        )

    # ── '>' parameter parsing for Ip blocks ────────────────────────────

    def _parse_greater_params(self) -> list[str]:
        """Parse parameter names after '>' in Ip.Name>a,b,c:

        Delegates to ``_parse_block_params()`` (shared identifier logic).

        Returns
        -------
        list[str] — the parameter names.
        """
        return self._parse_block_params(accept_expressions=False)
