"""constructor_parser.py — Parser mixin for constructor/encapsulation parsing.

Extracted from ``parser.py`` _parse_constructor and _parse_encapsulation.
"""

from __future__ import annotations

from lexer.tokens import TokenType
from parser.ra_ast import ConstructorNode, EncapsulationNode


class ConstructorParserMixin:
    """Mixin that adds constructor/encapsulation parsing to ``Parser``."""

    def _parse_constructor(self):
        """Parse a constructor block:

            Con:
                statements...
            con.close
        """
        from parser.parser import ParseError
        tok = self._consume(TokenType.CON, "Expected 'Con'")
        self._consume(TokenType.COLON, "Expected ':' after 'Con'")
        body = self._parse_body(terminators=frozenset({TokenType.CON_CLOSE}))
        has_close = self._check(TokenType.CON_CLOSE)
        if has_close:
            self._advance()
        return ConstructorNode(
            body=body,
            line=tok.line,
            auto_close=not has_close,
        )

    def _parse_encapsulation(self):
        """Parse an encapsulation block:

            En:
                properties...
            en.close
        """
        from parser.parser import ParseError
        tok = self._consume(TokenType.EN, "Expected 'En'")
        self._consume(TokenType.COLON, "Expected ':' after 'En'")
        body = self._parse_body(terminators=frozenset({TokenType.EN_CLOSE}))
        has_close = self._check(TokenType.EN_CLOSE)
        if has_close:
            self._advance()
        return EncapsulationNode(
            body=body,
            line=tok.line,
            auto_close=not has_close,
        )
