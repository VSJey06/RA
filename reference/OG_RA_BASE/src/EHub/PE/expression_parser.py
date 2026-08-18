"""ExpressionParser — Full operator-precedence expression parsing.

Handles all expression forms including primaries, property chains,
binary operators (power, multiplicative, additive, comparison, bitwise,
logical, flow), unary operators, method-call suffix, and .TF suffix.
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    BinaryOpNode,
    BitwiseExpressionNode,
    BooleanNode,
    CmNode,
    FunctionCallNode,
    HighlightNode,
    ImaginaryNode,
    IdentifierNode,
    InputNode,
    ListNode,
    LiteralNode,
    LogicalExpressionNode,
    MethodCallNode,
    ParagraphNode,
    PropertyAccessNode,
    SetNode,
    StrictComparisonNode,
    TupleNode,
    UnaryBitwiseNode,
    UnaryLogicalNode,
    Node,
)
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class ExpressionParser:
    """Parses expressions with full operator precedence.

    Precedence (highest to lowest):
      1. **, ^         (power)
      2. *, /, //, %, %%  (multiplicative)
      3. +, -           (additive)
      4. ==, !=, >, <, >=, <=, ===  (comparison / strict)
      5. &, |, <<, >>, band, bor, ...  (bitwise)
      6. and, &&, nor, nand  (logical AND-level)
      7. or, ||, xor, xnor  (logical OR-level)
      8. -->, <--       (comparison flow — lowest)
    """

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry
        # Delegate for dot-statement parsing (set by the facade)
        self._dot_stmt_parser: Optional[callable] = None
        # Delegate for make_input_node (set by the facade)
        self._make_input_node_func: Optional[callable] = None
        # Suppress the method-call suffix consumption (':') — set by
        # _parse_if during pre-action parsing so that ':' is not consumed
        # as a method-call suffix on the last value of the pre-action.
        self._suppress_method_call_suffix: bool = False
        # Function Family callback — set by the facade for .name function calls
        self._function_parser: Optional[callable] = None
        self._function_arg_depth: int = 0

    # ── Public entry point ──────────────────────────────────────────────

    def parse_expression(self) -> Node:
        """Parse an expression:
            primary ( '.' ident )* ( binary_op primary ( '.' ident )* )*
            optionally followed by .TF boolean suffix or :arg method call
        """
        left = self._parse_primary_chain()
        left = self._parse_binary_rhs(left)

        # Handle method call syntax: object.prop : arg  (e.g., D.find:5)
        # BUT skip this when _suppress_method_call_suffix is set (pre-action mode)
        if not self._suppress_method_call_suffix and self.env.check(TokenType.COLON):
            self.env.advance()
            arg = self.parse_expression()
            # RC3-09B.1: Multi-argument colon syntax (e.g., name.replace:"old","new")
            if self.env.check(TokenType.COMMA):
                self.env.advance()
                arg2 = self.parse_expression()
                from parser.ra_ast import ListNode
                arg = ListNode(items=[arg, arg2], line=left.line)
            flat = self._flatten_prop_chain(left)
            if flat is not None:
                return MethodCallNode(
                    method=f"{flat[0]}.{flat[1]}",
                    argument=arg, line=left.line,
                )
            from parser.parser import ParseError
            raise ParseError(
                "Expected a property chain before ':'", self.env.current(),
            )

        if self.env.check(TokenType.BOOLEAN_TF):
            self.env.advance()
            left = BooleanNode(expr=left, line=left.line)
        return left

    # ── Primary expression ──────────────────────────────────────────────

    def _parse_primary(self) -> Node:
        """Parse a primary expression."""
        tok = self.env.current()
        if tok.type == TokenType.STRING:
            self.env.advance()
            return LiteralNode(value=tok.value, kind=TokenType.STRING, line=tok.line)
        if tok.type == TokenType.INTEGER:
            self.env.advance()
            return LiteralNode(value=tok.value, kind=TokenType.INTEGER, line=tok.line,
                               was_measurement=tok.was_measurement)
        if tok.type == TokenType.FLOAT:
            self.env.advance()
            return LiteralNode(value=tok.value, kind=TokenType.FLOAT, line=tok.line,
                               was_measurement=tok.was_measurement)
        if tok.type == TokenType.IMAGINARY:
            self.env.advance()
            return ImaginaryNode(value=tok.value, line=tok.line)
        if tok.type == TokenType.BOOLEAN_LITERAL:
            self.env.advance()
            return LiteralNode(value=tok.value == "True", kind=TokenType.BOOLEAN_LITERAL, line=tok.line)
        if tok.type == TokenType.IDENTIFIER:
            name = tok.value
            # Check for Set{...} syntax — peek at next token
            next_tok = self.env.peek(1)
            if name == "Set" and next_tok is not None and next_tok.type == TokenType.LBRACE:
                self.env.advance()  # consume 'Set'
                self.env.advance()  # consume '{'
                items: list[Node] = []
                if not self.env.check(TokenType.RBRACE):
                    items.append(self.parse_expression())
                    while self.env.check(TokenType.COMMA):
                        self.env.advance()
                        if self.env.check(TokenType.RBRACE):
                            break
                        items.append(self.parse_expression())
                self.env.consume(
                    TokenType.RBRACE,
                    "Expected '}' after set items",
                )
                return SetNode(items=items, line=tok.line)
            self.env.advance()
            return IdentifierNode(name=name, line=tok.line)
        if tok.type == TokenType.MINUS:
            self.env.advance()
            nxt = self.env.current()
            if nxt.type == TokenType.INTEGER:
                self.env.advance()
                return LiteralNode(value=-nxt.value, kind=TokenType.INTEGER, line=tok.line,
                                   was_measurement=nxt.was_measurement)
            if nxt.type == TokenType.FLOAT:
                self.env.advance()
                return LiteralNode(value=-nxt.value, kind=TokenType.FLOAT, line=tok.line,
                                   was_measurement=nxt.was_measurement)
            from parser.parser import ParseError
            raise ParseError("Expected a number after '-'", tok)
        if tok.type == TokenType.BANG:
            self.env.advance()
            expr = self.parse_expression()
            return UnaryLogicalNode(operator="not", expr=expr, line=tok.line)
        if tok.type == TokenType.NOT_KW:
            self.env.advance()
            expr = self.parse_expression()
            return UnaryLogicalNode(operator="not", expr=expr, line=tok.line)
        if tok.type == TokenType.BNOT_KW:
            self.env.advance()
            expr = self.parse_expression()
            return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)
        if tok.type == TokenType.BITWISE_NOT:
            self.env.advance()
            expr = self.parse_expression()
            return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)
        if tok.type == TokenType.CARET:
            # Check for ^^ highlight operator (two consecutive CARET tokens)
            nxt = self.env.peek(1)
            if nxt is not None and nxt.type == TokenType.CARET:
                self.env.advance()  # consume first ^
                self.env.advance()  # consume second ^
                expr = self.parse_expression()
                return HighlightNode(value=expr, line=tok.line)
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected single '^'. Use ^^ for highlight operator.",
                tok,
            )
        if tok.type in (TokenType.YES_KW, TokenType.NO_KW):
            self.env.advance()
            value = tok.type == TokenType.YES_KW
            return LiteralNode(value=value, kind=TokenType.BOOLEAN_LITERAL, line=tok.line)
        if tok.type == TokenType.DOT:
            nxt = self.env.pos + 1
            if (nxt < len(self.env.tokens)
                    and self.env.tokens[nxt].type == TokenType.IDENTIFIER
                    and self.env.tokens[nxt].value in ("run", "fun")):
                from parser.parser import ParseError
                raise ParseError(
                    "'.run:' and '.fun:' cannot be used as a value", tok
                )
            if self._is_dot_query_or_input():
                if self._dot_stmt_parser is not None:
                    return self._dot_stmt_parser()
                from parser.parser import ParseError
                raise ParseError("Unexpected '.' in expression position", tok)
            if self._function_parser is not None:
                return self._function_parser.parse_function_call_from_expr()
            from parser.parser import ParseError
            raise ParseError("Function parser not configured for expression call", tok)
        if tok.type == TokenType.PIPE:
            open_tok = self.env.advance()
            inner = self._parse_primary_chain()
            inner = self._parse_comparison_rhs(inner)
            self.env.consume(
                TokenType.PIPE,
                "Expected closing '|' for absolute value expression",
            )
            return CmNode(value=inner, line=open_tok.line)
        if tok.type == TokenType.INPUT_SPEC:
            self.env.advance()
            if tok.value == "par.in":
                if self.env.check(TokenType.COLON):
                    self.env.advance()
                    content = self.parse_expression()
                    return ParagraphNode(content=content, line=tok.line)
                return InputNode(input_type="paragraph", line=tok.line)
            if self._make_input_node_func is not None:
                node = self._make_input_node_func(tok.value, tok.line)
            else:
                node = InputNode(input_type="generic", line=tok.line)
            if self.env.check(TokenType.COLON):
                self.env.advance()
                node.prompt = self.parse_expression()
            return node
        if tok.type == TokenType.LPAREN:
            self.env.advance()
            # Check for tuple literal: (expr, expr, ...)
            if self.env.check(TokenType.RPAREN):
                # Empty tuple ()
                self.env.advance()
                return TupleNode(items=[], line=tok.line)
            first = self.parse_expression()
            if self.env.check(TokenType.COMMA):
                # Tuple: (expr, expr, ...)
                items = [first]
                while self.env.check(TokenType.COMMA):
                    self.env.advance()
                    if self.env.check(TokenType.RPAREN):
                        # Trailing comma allowed
                        break
                    items.append(self.parse_expression())
                self.env.consume(
                    TokenType.RPAREN,
                    "Expected ')' after tuple items",
                )
                return TupleNode(items=items, line=tok.line)
            # Single parenthesized expression (not a tuple)
            self.env.consume(
                TokenType.RPAREN,
                "Expected ')' after parenthesized expression",
            )
            return first
        if tok.type == TokenType.LBRACKET:
            # List literal: [expr, expr, ...]
            self.env.advance()
            items: list[Node] = []
            if not self.env.check(TokenType.RBRACKET):
                items.append(self.parse_expression())
                while self.env.check(TokenType.COMMA):
                    self.env.advance()
                    if self.env.check(TokenType.RBRACKET):
                        # Trailing comma allowed
                        break
                    items.append(self.parse_expression())
            self.env.consume(
                TokenType.RBRACKET,
                "Expected ']' after list items",
            )
            return ListNode(items=items, line=tok.line)
        if tok.type == TokenType.LBRACE:
            # Reserved {} syntax (RC3-02A)
            self.env.advance()
            peek = self.env.current()
            self.env.consume(
                TokenType.RBRACE,
                "Expected '}' after '{'",
            )
            from parser.parser import ParseError
            raise ParseError(
                "{} is reserved for the future Deque implementation."
                f" (line {tok.line})",
                tok,
            )
        from parser.parser import ParseError
        raise ParseError(
            f"Expected a value (string, number, or identifier), "
            f"but found '{tok.value}'",
            tok,
        )

    # ── Property chain ──────────────────────────────────────────────────

    def _parse_primary_chain(self) -> Node:
        """Parse a primary expression followed by zero or more property accesses."""
        left = self._parse_primary()
        while self.env.check(TokenType.DOT):
            if isinstance(left, (LiteralNode, FunctionCallNode)):
                break
            nxt = self.env.pos + 1
            if (nxt < len(self.env.tokens)
                    and self.env.tokens[nxt].type in (TokenType.IDENTIFIER,
                                                       TokenType.FUN_NESTED,
                                                       TokenType.RUN_NESTED)
                    and self.env.tokens[nxt].value in ("fun", "run", "type", "len",
                                                        "upper", "lower", "trim",
                                                        "char")
                    and nxt + 1 < len(self.env.tokens)
                    and self.env.tokens[nxt + 1].type == TokenType.COLON):
                break
            dot_tok = self.env.advance()
            if (self.env.current().type in (TokenType.INTEGER, TokenType.IDENTIFIER)
                    and self.env.pos + 1 < len(self.env.tokens)
                    and self.env.tokens[self.env.pos + 1].type == TokenType.COMMA):
                x_tok = self.env.advance()
                self.env.consume(TokenType.COMMA, "Expected ',' after coordinate X")
                y_tok = self.env.advance()
                coord = f"{x_tok.value},{y_tok.value}"
                if isinstance(left, PropertyAccessNode):
                    left = PropertyAccessNode(
                        object=left.object,
                        property=f"{left.property}.{coord}",
                        line=dot_tok.line,
                    )
                else:
                    left = PropertyAccessNode(
                        object=left, property=coord,
                        line=dot_tok.line,
                    )
            else:
                prop = self._parse_dot_property()
                left = PropertyAccessNode(
                    object=left, property=prop, line=dot_tok.line,
                )
        return left

    def _is_dot_query_or_input(self) -> bool:
        nxt = self.env.pos + 1
        if nxt >= len(self.env.tokens):
            return False
        tok = self.env.tokens[nxt]
        if tok.type not in (TokenType.IDENTIFIER,
                            TokenType.FUN_NESTED, TokenType.RUN_NESTED,
                            TokenType.PRINT_NESTED, TokenType.FOR_NESTED,
                            TokenType.WHILE_NESTED):
            return False
        if tok.value in ("in", "take"):
            return True
        if tok.value in (
            "type", "len", "upper", "lower", "trim", "reverse", "char", "first",
            "last", "count", "find", "replace", "contains", "starts", "ends",
            "split", "repeat", "abs", "round", "is",
        ):
            return (
                nxt + 1 < len(self.env.tokens)
                and self.env.tokens[nxt + 1].type == TokenType.COLON
            )
        return False

    def _parse_function_call(self) -> FunctionCallNode:
        nested_call = self._function_arg_depth > 0
        dot_tok = self.env.advance()
        cur = self.env.current()
        if cur.type not in (TokenType.IDENTIFIER,
                            TokenType.FUN_NESTED, TokenType.RUN_NESTED,
                            TokenType.PRINT_NESTED, TokenType.FOR_NESTED,
                            TokenType.WHILE_NESTED):
            from parser.parser import ParseError
            raise ParseError("Expected function name after '.'", cur)
        name_tok = self.env.advance()
        args: list[Node] = []
        named_arguments: list[tuple[str, Node]] = []
        if self.env.check(TokenType.DOT):
            self.env.advance()
            arg_index = 0
            if self._is_named_argument_start():
                named_arguments.append(
                    self._parse_named_function_argument(arg_index)
                )
            else:
                args.append(self.parse_function_argument(arg_index=arg_index))
            while not nested_call and self.env.check(TokenType.COMMA):
                self.env.advance()
                arg_index += 1
                if self._is_named_argument_start():
                    named_arguments.append(
                        self._parse_named_function_argument(arg_index)
                    )
                else:
                    args.append(self.parse_function_argument(arg_index=arg_index))
        return FunctionCallNode(
            name=name_tok.value,
            args=args,
            named_arguments=named_arguments,
            line=dot_tok.line,
        )

    def _is_named_argument_start(self) -> bool:
        return (
            self.env.check(TokenType.IDENTIFIER)
            and self.env.pos + 1 < len(self.env.tokens)
            and self.env.tokens[self.env.pos + 1].type == TokenType.ASSIGN
        )

    def _parse_named_function_argument(self, arg_index: int) -> tuple[str, Node]:
        name_tok = self.env.advance()
        self.env.consume(
            TokenType.ASSIGN,
            "Expected '=' after named function argument",
        )
        return (
            name_tok.value,
            self.parse_function_argument(arg_index=arg_index),
        )

    def parse_function_argument(self, arg_index: int = 0) -> Node:
        self._function_arg_depth += 1
        try:
            return self._parse_function_argument_expression(
                stop_additive=arg_index > 0,
            )
        finally:
            self._function_arg_depth -= 1

    def _parse_function_argument_expression(self, stop_additive: bool) -> Node:
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

    def _parse_dot_property(self) -> str:
        """Parse property name after '.' and return it as a string."""
        tok = self.env.current()

        if tok.type == TokenType.MINUS:
            self.env.advance()
            first = self.env.consume(
                TokenType.IDENTIFIER, "Expected identifier after '-.'",
            )
            prop = "-" + first.value
            if (self.env.check(TokenType.MINUS)
                    and self.env.pos + 1 < len(self.env.tokens)
                    and self.env.tokens[self.env.pos + 1].type == TokenType.IDENTIFIER):
                self.env.advance()
                second = self.env.advance()
                prop += "-" + second.value
            return prop

        if tok.type == TokenType.INTEGER:
            self.env.advance()
            return str(tok.value)

        if tok.type in (TokenType.IDENTIFIER,
                        TokenType.FUN_NESTED, TokenType.RUN_NESTED,
                        TokenType.PRINT_NESTED, TokenType.FOR_NESTED,
                        TokenType.WHILE_NESTED):
            prop_tok = self.env.advance()
            prop = prop_tok.value
            if (self.env.check(TokenType.MINUS)
                    and self.env.pos + 1 < len(self.env.tokens)
                    and self.env.tokens[self.env.pos + 1].type == TokenType.IDENTIFIER):
                self.env.advance()
                second = self.env.advance()
                prop += "-" + second.value
            return prop

        from parser.parser import ParseError
        raise ParseError("Expected property name after '.'", tok)

    def _flatten_prop_chain(self, node: Node) -> Optional[tuple[str, str]]:
        """Flatten a property chain into (object_name, combined_property)."""
        if isinstance(node, PropertyAccessNode):
            if isinstance(node.object, IdentifierNode):
                return (node.object.name, node.property)
            base = self._flatten_prop_chain(node.object)
            if base is not None:
                return (base[0], f"{base[1]}.{node.property}")
        return None

    # ── Binary operator RHS (precedence chain) ──────────────────────────

    def _parse_binary_rhs(self, left: Node) -> Node:
        """Extend *left* with zero or more binary operators."""
        # Comparison flow operators (-->, <--) are DEPRECATED as expression
        # operators. They are now reserved for branch execution markers
        # inside !If statements (pre_action/post_action).
        return self._parse_logical_or_rhs(left)

    # ── Logical OR-level ────────────────────────────────────────────────

    def _parse_logical_or_rhs(self, left: Node) -> Node:
        """Parse logical OR-level operators (or, ||, xor, xnor)."""
        left = self._parse_logical_and_rhs(left)
        while True:
            op = self._match_or_logical()
            if op is None:
                break
            right = self._parse_or_operand()
            left = LogicalExpressionNode(operator=op, left=left, right=right, line=left.line)
        return left

    def _match_or_logical(self) -> Optional[str]:
        """Check and consume OR-level logical operators."""
        tok = self.env.current()
        if tok.type == TokenType.CARET:
            if self.env.pos + 2 < len(self.env.tokens):
                key3 = (
                    self.env.tokens[self.env.pos].type,
                    self.env.tokens[self.env.pos + 1].type,
                    self.env.tokens[self.env.pos + 2].type,
                )
                if key3 == (TokenType.CARET, TokenType.LOGICAL_OR, TokenType.CARET):
                    op = "xnor"
                    self.env.advance()
                    self.env.advance()
                    self.env.advance()
                    return op
            if self.env.pos + 1 < len(self.env.tokens):
                key2 = (
                    self.env.tokens[self.env.pos].type,
                    self.env.tokens[self.env.pos + 1].type,
                )
                if key2 == (TokenType.CARET, TokenType.LOGICAL_OR):
                    op = "xor"
                    self.env.advance()
                    self.env.advance()
                    return op
        if tok.type in self.reg.LOGICAL_KEYWORD_TYPES:
            val = tok.value.lower()
            if val in ("or", "xor", "xnor"):
                self.env.advance()
                return val
        if tok.type == TokenType.LOGICAL_OR:
            self.env.advance()
            return "or"
        return None

    def _parse_or_operand(self) -> Node:
        """Parse the RHS operand of a logical-OR operator (AND-level precedence)."""
        left = self._parse_primary_chain()
        return self._parse_logical_and_rhs(left)

    # ── Logical AND-level ───────────────────────────────────────────────

    def _parse_logical_and_rhs(self, left: Node) -> Node:
        """Parse logical AND-level operators (and, &&, nor, nand)."""
        left = self._parse_bitwise_rhs(left)
        while True:
            op = self._match_and_logical()
            if op is None:
                break
            right = self._parse_logical_operand()
            left = LogicalExpressionNode(operator=op, left=left, right=right, line=left.line)
        return left

    def _match_and_logical(self) -> Optional[str]:
        """Check and consume AND-level logical operators."""
        tok = self.env.current()
        if tok.type == TokenType.CARET and self.env.pos + 2 < len(self.env.tokens):
            key3 = (
                self.env.tokens[self.env.pos].type,
                self.env.tokens[self.env.pos + 1].type,
                self.env.tokens[self.env.pos + 2].type,
            )
            if key3 == (TokenType.CARET, TokenType.PIPE, TokenType.CARET):
                op = "nor"
                self.env.advance()
                self.env.advance()
                self.env.advance()
                return op
            if key3 == (TokenType.CARET, TokenType.AMPERSAND, TokenType.CARET):
                op = "nand"
                self.env.advance()
                self.env.advance()
                self.env.advance()
                return op
        if tok.type in self.reg.LOGICAL_KEYWORD_TYPES:
            val = tok.value.lower()
            if val in ("and", "nor", "nand"):
                self.env.advance()
                return val
        if tok.type == TokenType.LOGICAL_AND:
            self.env.advance()
            return "and"
        return None

    def _parse_logical_operand(self) -> Node:
        """Parse the RHS operand of a logical-AND operator (bitwise-level precedence)."""
        left = self._parse_primary_chain()
        return self._parse_bitwise_rhs(left)

    # ── Bitwise operators ───────────────────────────────────────────────

    def _parse_bitwise_rhs(self, left: Node) -> Node:
        """Parse bitwise operators (&, |, ^, <<, >>) and keyword forms."""
        left = self._parse_comparison_rhs(left)
        while True:
            op = self._match_bitwise()
            if op is None:
                break
            right = self._parse_bitwise_operand()
            left = BitwiseExpressionNode(operator=op, left=left, right=right, line=left.line)
        return left

    def _match_bitwise(self) -> Optional[str]:
        """Check and consume a bitwise operator."""
        tok = self.env.current()
        if tok.type == TokenType.PIPE and self.env.pos + 2 < len(self.env.tokens):
            key3 = (
                self.env.tokens[self.env.pos].type,
                self.env.tokens[self.env.pos + 1].type,
                self.env.tokens[self.env.pos + 2].type,
            )
            if key3 == (TokenType.PIPE, TokenType.CARET, TokenType.PIPE):
                op = "bxor"
                self.env.advance()
                self.env.advance()
                self.env.advance()
                return op
        if tok.type in self.reg.BITWISE_KEYWORD_TYPES:
            val = tok.value.lower()
            if val in ("band", "bor", "bxor", "blshift", "brshift"):
                self.env.advance()
                return val
        if tok.type == TokenType.AMPERSAND:
            self.env.advance()
            return "band"
        if tok.type == TokenType.PIPE:
            self.env.advance()
            return "bor"
        if tok.type == TokenType.BITWISE_LSHIFT:
            self.env.advance()
            return "blshift"
        if tok.type == TokenType.BITWISE_RSHIFT:
            self.env.advance()
            return "brshift"
        return None

    def _parse_bitwise_operand(self) -> Node:
        """Parse the operand of a bitwise operator (comparison-level precedence)."""
        left = self._parse_primary_chain()
        return self._parse_comparison_rhs(left)

    # ── Comparison operators ────────────────────────────────────────────

    # Type names for `is` and `to` binary operators
    _TYPE_KEYWORDS: frozenset[TokenType] = frozenset({
        TokenType.I, TokenType.S, TokenType.TF, TokenType.YN_KW,
        TokenType.F, TokenType.D, TokenType.L,
        TokenType.CX, TokenType.CS, TokenType.CA, TokenType.CM,
    })

    _SUBTYPE_NAMES: frozenset[str] = frozenset({
        "int", "str", "char", "float", "double", "long", "byte",
        "buffer", "builder", "bool", "Yes", "No", "YN", "yn",
    })

    def _parse_type_reference(self) -> Node:
        """Parse a type name reference for 'is' or 'to' expressions.

        Handles both keyword type tokens (I, S, TF, YN, F, D, L, Cx, Cs, Ca, Cm)
        and subtype identifiers (int, str, char, float, double, long, byte,
        buffer, builder, bool, Yes, No, YN).

        Returns an IdentifierNode with the type name.
        """
        if self.env.check(*self._TYPE_KEYWORDS):
            tok = self.env.advance()
            return IdentifierNode(name=tok.value, line=tok.line)
        if self.env.check(TokenType.IDENTIFIER):
            val = self.env.current().value
            if val in self._SUBTYPE_NAMES:
                tok = self.env.advance()
                return IdentifierNode(name=tok.value, line=tok.line)
        from parser.parser import ParseError
        raise ParseError(
            "Expected a type name (I, S, TF, YN, F, D, int, str, etc.)",
            self.env.current(),
        )

    def _try_parse_type_reference(self) -> Optional[Node]:
        """Try to parse a type reference for ==/!= type comparison (RC3-08C).

        Returns an IdentifierNode with the type/family name if the next token
        is a recognized type-check key or family identifier, otherwise None.
        This does NOT raise ParseError on failure.
        """
        if self.env.check(*self._TYPE_KEYWORDS):
            tok = self.env.advance()
            return IdentifierNode(name=tok.value, line=tok.line)
        if self.env.check(TokenType.IDENTIFIER):
            val = self.env.current().value
            if val in self._SUBTYPE_NAMES:
                tok = self.env.advance()
                return IdentifierNode(name=tok.value, line=tok.line)
        return None

    def _parse_comparison_rhs(self, left: Node) -> Node:
        """Parse comparison operators (==, !=, >, <, >=, <=, ===).

        Also handles ``value is type`` (family checking) and
        ``value to type`` (conversion) as binary operators.

        For ``==`` and ``!=``, when the RHS is a recognized type-check key
        or family identifier, it is parsed as a type reference rather than
        a normal expression.  At runtime the interpreter then dispatches
        exact-type or family comparison instead of value comparison.
        """
        left = self._parse_additive_rhs(left)
        while True:
            if self.env.check(TokenType.STRICT_EQ):
                self.env.advance()
                right = self._parse_additive()
                left = StrictComparisonNode(left=left, right=right, line=left.line)
            elif self.env.check(*self.reg.COMPARISON_OPS):
                op_tok = self.env.advance()
                # RC3-08C: For == and !=, check if RHS is a type reference
                if op_tok.value in ("==", "!="):
                    type_node = self._try_parse_type_reference()
                    if type_node is not None:
                        left = BinaryOpNode(
                            operator=op_tok.value,
                            left=left, right=type_node,
                            line=op_tok.line,
                        )
                        continue
                right = self._parse_additive()
                left = BinaryOpNode(
                    operator=op_tok.value,
                    left=left, right=right,
                    line=op_tok.line,
                )
            elif (self.env.check(TokenType.IDENTIFIER)
                  and self.env.current().value == "is"):
                op_tok = self.env.advance()
                right = self._parse_type_reference()
                left = BinaryOpNode(operator="is", left=left, right=right, line=op_tok.line)
            elif (self.env.check(TokenType.IDENTIFIER)
                  and self.env.current().value == "to"):
                op_tok = self.env.advance()
                right = self._parse_type_reference()
                left = BinaryOpNode(operator="to", left=left, right=right, line=op_tok.line)
            else:
                break
        return left

    # ── Additive operators ──────────────────────────────────────────────

    def _parse_additive_rhs(self, left: Node) -> Node:
        """Parse additive operators (+/-)."""
        left = self._parse_multiplicative_rhs(left)
        while self.env.check(*self.reg.ADDITIVE_OPS):
            op_tok = self.env.advance()
            right = self._parse_multiplicative()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_additive(self) -> Node:
        """Parse an additive expression (for use as RHS of comparison)."""
        left = self._parse_multiplicative()
        while self.env.check(*self.reg.ADDITIVE_OPS):
            op_tok = self.env.advance()
            right = self._parse_multiplicative()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    # ── Multiplicative operators ────────────────────────────────────────

    def _parse_multiplicative_rhs(self, left: Node) -> Node:
        """Parse multiplicative operators (*, /, //, %, %%)."""
        left = self._parse_power_rhs(left)
        while self.env.check(*self.reg.MULTIPLICATIVE_OPS):
            op_tok = self.env.advance()
            right = self._parse_power()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_multiplicative(self) -> Node:
        """Parse a multiplicative expression (for use as RHS of additive)."""
        left = self._parse_power()
        while self.env.check(*self.reg.MULTIPLICATIVE_OPS):
            op_tok = self.env.advance()
            right = self._parse_power()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    # ── Power operators (highest) ───────────────────────────────────────

    def _parse_power_rhs(self, left: Node) -> Node:
        """Parse power operators (**, ^) — highest precedence."""
        while self.env.check(*self.reg.POWER_OPS):
            tok = self.env.current()
            if tok.type == TokenType.CARET and self.env.pos + 1 < len(self.env.tokens):
                nxt = self.env.tokens[self.env.pos + 1].type
                if nxt in (TokenType.LOGICAL_OR, TokenType.PIPE, TokenType.AMPERSAND, TokenType.CARET):
                    break
            op_tok = self.env.advance()
            right = self._parse_primary_chain()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left

    def _parse_power(self) -> Node:
        """Parse a power expression (for use as RHS of multiplicative)."""
        left = self._parse_primary_chain()
        while self.env.check(*self.reg.POWER_OPS):
            tok = self.env.current()
            if tok.type == TokenType.CARET and self.env.pos + 1 < len(self.env.tokens):
                nxt = self.env.tokens[self.env.pos + 1].type
                if nxt in (TokenType.LOGICAL_OR, TokenType.PIPE, TokenType.AMPERSAND, TokenType.CARET):
                    break
            op_tok = self.env.advance()
            right = self._parse_primary_chain()
            left = BinaryOpNode(
                operator=op_tok.value,
                left=left, right=right,
                line=op_tok.line,
            )
        return left
