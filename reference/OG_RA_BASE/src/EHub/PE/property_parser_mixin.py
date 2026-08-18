"""property_parser_mixin.py — Parser mixin for property access parsing.

Moves property access parsing logic from parser.py into a dedicated mixin,
as required by the Distributed Parser Architecture.

Ownership:
  - object.property
  - object.prop.subprop
  - object.prop.X,Y (coordinate syntax)
  - object.prop:arg (method-call via property)
  - Negative property prefixes: .-x, .-x-y
  - Integer properties: .N
  - Property chain flattening
  - Dot query/input detection
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    FunctionCallNode,
    IdentifierNode,
    LiteralNode,
    Node,
    PropertyAccessNode,
)


class PropertyParserMixin:
    """Mixin that adds property access parsing to ``Parser``.

    Methods moved from parser.py during RC1 Parser Delegation sprint.
    Uses ``self._consume()``, ``self._check()``, ``self._advance()``,
    ``self._current()``, ``self.pos``, ``self.tokens``,
    ``self._parse_primary()``, ``self._parse_dot_property()``,
    provided by the Parser class.
    """

    # ── Dot property parsing ─────────────────────────────────────────────

    def _parse_dot_property(self) -> str:
        """Parse property name after '.' and return it as a string.

        Handles:
        - ``IDENTIFIER``           → ``"x"``
        - ``IDENTIFIER - IDENTIFIER`` → ``"x-y"``
        - ``- IDENTIFIER``         → ``"-x"``
        - ``- IDENTIFIER - IDENTIFIER`` → ``"-x-y"``
        - ``INTEGER``              → ``"3"``
        """
        from parser.parser import ParseError
        tok = self._current()

        # Negative prefix: .-x, .-x-y
        if tok.type == TokenType.MINUS:
            self._advance()
            first = self._consume(
                TokenType.IDENTIFIER, "Expected identifier after '-.'",
            )
            prop = "-" + first.value
            if (self._check(TokenType.MINUS)
                    and self.pos + 1 < len(self.tokens)
                    and self.tokens[self.pos + 1].type == TokenType.IDENTIFIER):
                self._advance()
                second = self._advance()
                prop += "-" + second.value
            return prop

        # Integer property: .N (row.3, colm.5)
        if tok.type == TokenType.INTEGER:
            self._advance()
            return str(tok.value)

        # Regular identifier property, possibly compound
        if tok.type == TokenType.IDENTIFIER:
            prop_tok = self._advance()
            prop = prop_tok.value
            if (self._check(TokenType.MINUS)
                    and self.pos + 1 < len(self.tokens)
                    and self.tokens[self.pos + 1].type == TokenType.IDENTIFIER):
                self._advance()
                second = self._advance()
                prop += "-" + second.value
            return prop

        raise ParseError("Expected property name after '.'", tok)

    # ── Primary chain (primary + property accesses) ──────────────────────

    def _parse_primary_chain(self) -> Node:
        """Parse a primary expression followed by zero or more property accesses.

            primary ( '.' ident )*

        Stops before a DOT that introduces a ``.fun:`` or ``.run:`` block
        (DOT + IDENTIFIER("fun"/"run") + COLON) so the statement-level
        dispatcher can handle those constructs.  Also stops when the left
        side is a literal value (property access only makes sense on
        variables/objects).
        """
        left = self._parse_primary()
        while self._check(TokenType.DOT):
            # Literal values cannot have property chains
            if isinstance(left, (LiteralNode, FunctionCallNode)):
                break
            # Peek ahead: if DOT + IDENTIFIER("fun"/"run"/"type"/"len"/"upper"/"lower"/"trim"/"char") + COLON,
            # this is a dot-statement, not a property access.
            nxt = self.pos + 1
            if (nxt < len(self.tokens)
                    and self.tokens[nxt].type == TokenType.IDENTIFIER
                    and self.tokens[nxt].value in ("fun", "run", "type", "len",
                                                    "upper", "lower", "trim",
                                                    "char")
                    and nxt + 1 < len(self.tokens)
                    and self.tokens[nxt + 1].type == TokenType.COLON):
                break
            dot_tok = self._advance()
            # Coordinate syntax: .INTEGER,INTEGER appended to last property
            if (self._current().type in (TokenType.INTEGER, TokenType.IDENTIFIER)
                    and self.pos + 1 < len(self.tokens)
                    and self.tokens[self.pos + 1].type == TokenType.COMMA):
                x_tok = self._advance()
                self._consume(TokenType.COMMA, "Expected ',' after coordinate X")
                y_tok = self._advance()
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

    # ── Dot query/input detection ────────────────────────────────────────

    def _is_dot_query_or_input(self) -> bool:
        nxt = self.pos + 1
        if nxt >= len(self.tokens):
            return False
        tok = self.tokens[nxt]
        if tok.type != TokenType.IDENTIFIER:
            return False
        if tok.value in ("in", "take"):
            return True
        if tok.value in (
            "type", "len", "upper", "lower", "trim", "reverse", "char", "first",
            "last", "count", "find", "replace", "contains", "starts", "ends",
            "split", "repeat", "abs", "round", "is",
        ):
            return (
                nxt + 1 < len(self.tokens)
                and self.tokens[nxt + 1].type == TokenType.COLON
            )
        return False

    # ── Property chain flattening ────────────────────────────────────────

    def _flatten_prop_chain(self, node: Node) -> Optional[tuple[str, str]]:
        """Flatten a property chain into (object_name, combined_property).

        ``D.find``           → ``("D", "find")``
        ``D.diagonal.x-y``   → ``("D", "diagonal.x-y")``
        """
        if isinstance(node, PropertyAccessNode):
            if isinstance(node.object, IdentifierNode):
                return (node.object.name, node.property)
            base = self._flatten_prop_chain(node.object)
            if base is not None:
                return (base[0], f"{base[1]}.{node.property}")
        return None
