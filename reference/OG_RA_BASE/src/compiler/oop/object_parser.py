"""object_parser.py — Parser mixin for object instantiation parsing.

Extracted from ``parser.py`` _parse_object and _consume_name.
"""

from __future__ import annotations

from lexer.tokens import TokenType
from parser.ra_ast import ObjectDeclarationNode


class ObjectParserMixin:
    """Mixin that adds object-instantiation parsing to ``Parser``."""

    _NAME_TOKENS = frozenset({
        TokenType.IDENTIFIER,
        TokenType.P, TokenType.R,
        TokenType.DB_NEXT, TokenType.DB_BREAK, TokenType.DB_CLOSE,
        TokenType.S, TokenType.I, TokenType.L, TokenType.TF,
        TokenType.CLS, TokenType.OBJ, TokenType.M, TokenType.DB,
        TokenType.BOOLEAN_TF,
    })

    def _consume_name(self, message: str):
        """Consume a token that can be used as a name (identifier or keyword)."""
        if self._check(*self._NAME_TOKENS):
            return self._advance()
        from parser.parser import ParseError
        raise ParseError(message, self._current())

    def _parse_object(self):
        """Parse an object instantiation:

            Obj.ClassName.VariableName
        """
        from parser.parser import ParseError
        tok = self._consume(TokenType.OBJ, "Expected 'Obj' for object instantiation")
        self._consume(TokenType.DOT, "Expected '.' after 'Obj'")
        cls_tok = self._consume_name("Expected class name after 'Obj.'")
        self._consume(TokenType.DOT, "Expected '.' after class name")
        var_tok = self._consume_name("Expected variable name after class name")
        return ObjectDeclarationNode(object_name=var_tok.value, class_name=cls_tok.value, line=tok.line)
