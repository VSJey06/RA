"""class_parser.py — Parser mixin for class definition parsing.

Extracted from ``parser.py`` _parse_at_stmt and _parse_class_body.
"""

from __future__ import annotations

from lexer.tokens import TokenType
from parser.ra_ast import ClassNode, IdentifierNode


class ClassParserMixin:
    """Mixin that adds class-definition parsing to ``Parser``."""

    def _parse_at_stmt(self):
        """Parse a class definition, Db block, or standalone ``@`` marker.

            @Cls.Name:      ->  ClassNode
            @Db:            ->  DbNode
            @               ->  IdentifierNode("@")  (close marker)
        """
        at_tok = self._consume(TokenType.AT, "Expected '@'")
        if self._check(TokenType.CLS):
            self._advance()
            self._consume(TokenType.DOT, "Expected '.' after 'Cls'")
            name_tok = self._consume(
                TokenType.IDENTIFIER, "Expected class name after 'Cls.'",
            )
            self._consume(TokenType.COLON, "Expected ':' after class name")
            members = self._parse_class_body()
            if self._check(TokenType.AT, TokenType.AT_CLOSE):
                if self._check(TokenType.AT):
                    next_idx = self.pos + 1
                    if next_idx < len(self.tokens):
                        next_tt = self.tokens[next_idx].type
                        is_explicit = next_tt not in (TokenType.CLS, TokenType.DB)
                    else:
                        is_explicit = True
                else:  # AT_CLOSE — always explicit
                    is_explicit = True
                if is_explicit:
                    self._advance()
                return ClassNode(
                    name=name_tok.value, members=members,
                    line=at_tok.line, auto_close=not is_explicit,
                )
            return ClassNode(
                name=name_tok.value, members=members,
                line=at_tok.line, auto_close=True,
            )
        if self._check(TokenType.DB):
            return self._parse_db(at_tok)
        return IdentifierNode(name="@", line=at_tok.line)

    def _parse_class_body(self):
        """Parse statements inside ``@Cls.Name:``.

        Stops at ``@`` or ``@.close`` (class terminator) or EOF.
        """
        return self._parse_body(terminators=frozenset({TokenType.AT, TokenType.AT_CLOSE}))
