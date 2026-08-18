"""method_parser.py — Parser mixin for method definition parsing.

Extracted from ``parser.py`` _parse_method.
"""

from __future__ import annotations

from lexer.tokens import TokenType
from parser.ra_ast import MethodNode


class MethodParserMixin:
    """Mixin that adds method-definition parsing to ``Parser``."""

    def _parse_method(self):
        """Parse a method definition:

            M.name:
                body...
            /.close
        """
        from parser.parser import ParseError
        m_tok = self._consume(TokenType.M, "Expected 'M' for method definition")
        self._consume(TokenType.DOT, "Expected '.' after 'M'")
        name_tok = self._consume(
            TokenType.IDENTIFIER, "Expected method name after 'M.'",
        )
        self._consume(TokenType.COLON, "Expected ':' after method name")

        body = self._parse_body(terminators=frozenset({TokenType.METHOD_CLOSE}))
        has_close = self._check(TokenType.METHOD_CLOSE)
        if has_close:
            self._advance()

        return MethodNode(
            name=name_tok.value, body=body,
            line=m_tok.line, auto_close=not has_close,
        )
