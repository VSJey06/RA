"""parser_function.py — Function Family parser for the RA language.

Constitutionally required specialized parser for all Function constructs:

  Primary Functions:
    - .fun: body f.close                        (anonymous function block)
    - .fun.<name>: body f.close                 (named function declaration)
    - .fun.<name>.<p1>.<p2>: body f.close       (named function with params)

  Nested Functions (inside executable blocks only):
    - fun.<name>: body #                        (nested named function)
    - fun.<name>.<p1>.<p2>: body #              (nested function with params)

  Function Calls (statement & expression positions):
    - .<name>                                   (call with no args)
    - .<name>.<arg1>,<arg2>                     (call with positional args)
    - .<name>.<key>=<value>                     (call with named args)

  Return handling:
    - R.expression                              (return statement)

FunctionParser produces AST nodes only.
No runtime logic. No semantic analysis.
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    BinaryOpNode,
    FunctionBlockNode,
    FunctionCallNode,
    Node,
)
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class FunctionParser:
    """Parses all Function Family constructs.

    FunctionParser is the SOLE owner of:

      - Primary Functions:   .fun:, .fun.<name>:, .fun.<name>.<params>:
      - Nested Functions:    fun.<name>:, fun.<name>.<params>:
      - Function Calls:      .<name>, .<name>.<args>
      - Parameters & Arguments parsing

    All other parser modules (statement_parser, parser.py, expression_parser)
    shall ONLY dispatch to this parser — never implement function grammar.

    FunctionParser produces AST nodes only.
    """

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry

        # ── Delegates set by the facade (parser.py) ────────────────────
        self._parse_body_func: Optional[callable] = None
        self._expression_parser: Optional[object] = None
        self._function_arg_depth: int = 0

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
        """Save and suppress method-call ':' consumption in expression parser."""
        saved = getattr(
            self._expression_parser, '_suppress_method_call_suffix', False,
        )
        if self._expression_parser is not None:
            self._expression_parser._suppress_method_call_suffix = True
        return saved

    def _restore_expression_method_call(self, saved: bool) -> None:
        """Restore method-call ':' consumption in expression parser."""
        if self._expression_parser is not None:
            self._expression_parser._suppress_method_call_suffix = saved

    # ── Dot-prefixed .fun entry point (from statement_parser._parse_dot_stmt) ─

    def parse_dot_fun(self, dot_tok: Token) -> FunctionBlockNode:
        """Parse a .fun-prefixed statement from the dot-statement handler.

        Handles all forms:

            .fun: body f.close                  ->  anonymous block
            .fun.<name>: body f.close           ->  named function
            .fun.<name>.<p1>.<p2>: body f.close ->  named function with params
        """
        # After this, the 'fun' identifier has already been consumed
        # by the caller (_parse_dot_stmt). We just need to check for
        # ':' (anonymous) or '.' (named with optional params).

        if self.env.check(TokenType.COLON):
            self.env.advance()
            return self.parse_function_block(dot_tok)

        if self.env.check(TokenType.DOT):
            self.env.advance()
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected function name after '.fun.'",
            )
            params: list[str] = []
            if self.env.check(TokenType.DOT):
                self.env.advance()
                params = self.parse_function_params(name_tok.value)
            self.env.consume(
                TokenType.COLON,
                "Expected ':' after function declaration",
            )
            return self.parse_function_block(
                dot_tok, name=name_tok.value, params=params,
            )

        from parser.parser import ParseError
        raise ParseError(
            "Expected '.fun:<name>:' or '.fun.<name>.<params>:'",
            dot_tok,
        )

    # ── Function block (.fun:, .fun.<name>:) ─────────────────────────────

    def parse_function_block(
        self,
        dot_tok: Token,
        name: Optional[str] = None,
        params: Optional[list[str]] = None,
    ) -> FunctionBlockNode:
        """Parse a function block:

            .fun: body... f.close               (anonymous)
            .fun.<name>: body... f.close        (named)
            .fun.<name>.<p1>,<p2>: body f.close (named with params)

        Nested form (terminated by HASH instead of FUN_CLOSE) should
        use parse_nested_fun() instead.
        """
        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.FUN_CLOSE}))
        else:
            body = []
        has_close = self.env.check(TokenType.FUN_CLOSE)
        if has_close:
            self.env.advance()
        return FunctionBlockNode(
            name=name,
            params=params or [],
            body=body,
            line=dot_tok.line,
            auto_close=not has_close,
        )

    # ── Nested fun (inside executable blocks) ───────────────────────────

    def parse_nested_fun(self) -> FunctionBlockNode:
        """Parse a nested function definition inside an executable block.

        Syntax:

            fun.add:
                body
            #

            fun.add.param1.param2:
                body
            #

        Reuses FunctionBlockNode (same AST as primary .fun).
        Raises NestedBlockSyntaxError if not inside a block.
        """
        from EHub.PE.statement_parser import NestedBlockSyntaxError

        if self.env.nested_block_depth == 0:
            raise NestedBlockSyntaxError(
                "'fun' is only valid inside an executable block. "
                "Use '.fun' at the top level instead."
            )

        fun_tok = self.env.advance()  # consume 'fun'

        name: Optional[str] = None
        params: list[str] = []

        if self.env.check(TokenType.DOT):
            self.env.advance()
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected function name after 'fun.'",
            )
            name = name_tok.value
            if self.env.check(TokenType.DOT):
                self.env.advance()
                params = self.parse_function_params(name)

        self.env.consume(
            TokenType.COLON,
            "Expected ':' after function declaration",
        )

        # Parse body with HASH terminator (nested convention, not FUN_CLOSE)
        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
        else:
            body = []

        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return FunctionBlockNode(
            name=name, params=params, body=body,
            line=fun_tok.line, auto_close=not has_close,
        )

    # ── Function call (.name, .name.args) — statement level ────────────

    def parse_function_call(self, dot_tok: Token) -> FunctionCallNode:
        """Parse a function call at statement level.

        The leading '.' has already been consumed by the caller
        (statement_parser._parse_dot_stmt).

        Syntax:

            .name               ->  call with no args
            .name.arg1,arg2     ->  call with positional args
            .name.key=value     ->  call with named args
        """
        name_tok = self.env.consume(
            TokenType.IDENTIFIER,
            "Expected function name after '.'",
        )
        args: list[Node] = []
        named_arguments: list[tuple[str, Node]] = []
        # Only consume DOT as argument separator on the SAME line
        if self.env.check(TokenType.DOT) and self.env.current().line == name_tok.line:
            self.env.advance()
            arg_index = 0
            if self._is_named_function_argument_start():
                named_arguments.append(
                    self._parse_named_function_argument(arg_index)
                )
            else:
                args.append(self._parse_function_argument(arg_index=arg_index))
            while self.env.check(TokenType.COMMA):
                self.env.advance()
                arg_index += 1
                if self._is_named_function_argument_start():
                    named_arguments.append(
                        self._parse_named_function_argument(arg_index)
                    )
                else:
                    args.append(self._parse_function_argument(arg_index=arg_index))
        return FunctionCallNode(
            name=name_tok.value,
            args=args,
            named_arguments=named_arguments,
            line=dot_tok.line,
        )

    # ── Function call — expression level (consumes the leading dot) ─────

    def parse_function_call_from_expr(self) -> FunctionCallNode:
        """Parse a function call at expression level.

        Called when a '.' is encountered in expression position
        (expression_parser._parse_primary).

        This method consumes the leading '.' token and the function name.

        Syntax:

            .name               ->  call with no args
            .name.arg1,arg2     ->  call with positional args
            .name.key=value     ->  call with named args
        """
        nested_call = self._function_arg_depth > 0
        dot_tok = self.env.advance()  # consume '.'
        cur = self.env.current()
        if cur.type not in (
            TokenType.IDENTIFIER,
            TokenType.FUN_NESTED, TokenType.RUN_NESTED,
            TokenType.PRINT_NESTED, TokenType.FOR_NESTED,
            TokenType.WHILE_NESTED,
        ):
            from parser.parser import ParseError
            raise ParseError("Expected function name after '.'", cur)
        name_tok = self.env.advance()
        args: list[Node] = []
        named_arguments: list[tuple[str, Node]] = []
        # Only consume DOT as argument separator on the SAME line
        if self.env.check(TokenType.DOT) and self.env.current().line == name_tok.line:
            self.env.advance()
            arg_index = 0
            if self._is_named_function_argument_start():
                named_arguments.append(
                    self._parse_named_function_argument(arg_index)
                )
            else:
                args.append(self._parse_function_argument(arg_index=arg_index))
            while not nested_call and self.env.check(TokenType.COMMA):
                self.env.advance()
                arg_index += 1
                if self._is_named_function_argument_start():
                    named_arguments.append(
                        self._parse_named_function_argument(arg_index)
                    )
                else:
                    args.append(self._parse_function_argument(arg_index=arg_index))
        return FunctionCallNode(
            name=name_tok.value,
            args=args,
            named_arguments=named_arguments,
            line=dot_tok.line,
        )

    # ── Function parameters ──────────────────────────────────────────────

    def parse_function_params(self, function_name: str) -> list[str]:
        """Parse comma-separated function parameters.

        Syntax (after .fun.<name>. has been consumed):

            param1,param2,param3
        """
        params: list[str] = []
        first = self.env.consume(
            TokenType.IDENTIFIER,
            f"Expected parameter name after '.fun.{function_name}.'",
        )
        params.append(first.value)
        while self.env.check(TokenType.COMMA):
            self.env.advance()
            param = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected parameter name after ','",
            )
            params.append(param.value)
        return params

    # ── Named function argument detection ───────────────────────────────

    def _is_named_function_argument_start(self) -> bool:
        """Check if the current position starts a named argument (key=value)."""
        return (
            self.env.check(TokenType.IDENTIFIER)
            and self.env.pos + 1 < len(self.env.tokens)
            and self.env.tokens[self.env.pos + 1].type == TokenType.ASSIGN
        )

    # ── Named function argument parsing ─────────────────────────────────

    def _parse_named_function_argument(self, arg_index: int) -> tuple[str, Node]:
        """Parse a named function argument: key=value."""
        name_tok = self.env.advance()
        self.env.consume(
            TokenType.ASSIGN,
            "Expected '=' after named function argument",
        )
        return (
            name_tok.value,
            self._parse_function_argument(arg_index=arg_index),
        )

    # ── Function argument parsing ───────────────────────────────────────

    def _parse_function_argument(self, arg_index: int = 0) -> Node:
        """Parse a function argument expression.

        Tracks nesting depth to prevent comma confusion in nested calls.
        """
        self._function_arg_depth += 1
        try:
            return self._parse_function_argument_expression(
                stop_additive=arg_index > 0,
            )
        finally:
            self._function_arg_depth -= 1

    def _parse_function_argument_expression(self, stop_additive: bool) -> Node:
        """Parse an argument expression.

        When stop_additive is True (arg_index > 0), additive operators
        (+/-) are not consumed, allowing commas to be used as argument
        separators within additive expressions.
        """
        left = self._parse_primary_chain()
        while (
            not stop_additive
            and self.env.check(TokenType.PLUS, TokenType.MINUS)
        ):
            op_tok = self.env.advance()
            right = self._parse_primary_chain()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left,
                right=right,
                line=op_tok.line,
            )
        return left
