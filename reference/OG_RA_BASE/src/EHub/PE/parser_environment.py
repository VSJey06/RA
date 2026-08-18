"""ParserEnvironment — Centralized parser state and shared token API.

Every parser (specialized or facade) accesses tokens through this
environment.  All shared token helpers live here:

    advance() / current() / check() / match() / consume()
    loc() / loc_range()

Plus body-parsing state (_body_terminators, _in_ff_flow) that is
shared by all parsers.
"""

from __future__ import annotations

from typing import Optional, Any

from lexer.tokens import Token, TokenType
from parser.ra_ast import Node
from parser.source_location import SourceLocation


class ParserEnvironment:
    """Mutable state shared by the parser facade and all specialized parsers.

    Parameters
    ----------
    tokens : list[Token]
        Flat token stream from ``tokenizer.tokenize()``.
    """

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos: int = 0
        self._body_terminators: frozenset[TokenType] = frozenset()
        self._in_ff_flow: bool = False
        self._current_line: int = 1
        self._nested_block_depth: int = 0

    # ── Token helpers ────────────────────────────────────────────────────

    def current(self) -> Token:
        """Return the token at the current position, or an EOF sentinel."""
        if self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            self._current_line = tok.line
            return tok
        last = self.tokens[-1] if self.tokens else None
        return Token(TokenType.EOF, None, getattr(last, "line", 1), 0)

    def check(self, *types: TokenType) -> bool:
        """Return True if the current token type matches any of *types*."""
        return self.current().type in types

    def match(self, *types: TokenType) -> Optional[Token]:
        """If the current token matches any of *types*, consume and return it.

        Returns None when no match.
        """
        if self.check(*types):
            return self.advance()
        return None

    def advance(self) -> Token:
        """Consume and return the current token."""
        tok = self.current()
        self.pos += 1
        return tok

    def consume(self, expected: TokenType, message: str) -> Token:
        """Assert the current token is *expected*, consume it, and return it.

        Raises ``ParseError`` with *message* on mismatch.
        """
        if self.check(expected):
            return self.advance()
        from parser.parser import ParseError
        raise ParseError(message, self.current())

    # ── Source-location helpers ─────────────────────────────────────────

    @staticmethod
    def loc(node: Node, token: Token) -> Node:
        """Populate *node* with column/end positions from *token* and return it."""
        node.col = token.column
        node.end_line = token.end_line
        node.end_column = token.end_column
        return node

    @staticmethod
    def loc_range(
        node: Node,
        start_token: Token,
        end_token: Optional[Token] = None,
    ) -> Node:
        """Populate *node* with location spanning *start_token* … *end_token*."""
        node.col = start_token.column
        node.end_line = end_token.end_line if end_token else start_token.end_line
        node.end_column = end_token.end_column if end_token else start_token.end_column
        return node

    # ── Body-parsing helpers ────────────────────────────────────────────

    @property
    def body_terminators(self) -> frozenset[TokenType]:
        return self._body_terminators

    @body_terminators.setter
    def body_terminators(self, value: frozenset[TokenType]) -> None:
        self._body_terminators = value

    @property
    def in_ff_flow(self) -> bool:
        return self._in_ff_flow

    @in_ff_flow.setter
    def in_ff_flow(self, value: bool) -> None:
        self._in_ff_flow = value

    # ── Nested block context ────────────────────────────────────────────

    @property
    def nested_block_depth(self) -> int:
        return self._nested_block_depth

    @nested_block_depth.setter
    def nested_block_depth(self, value: int) -> None:
        self._nested_block_depth = value

    # ── Convenience ─────────────────────────────────────────────────────

    def peek(self, offset: int = 1) -> Optional[Token]:
        """Peek ahead *offset* positions without consuming."""
        idx = self.pos + offset
        if 0 <= idx < len(self.tokens):
            return self.tokens[idx]
        return None

    def expect(self, expected: TokenType, message: str) -> Token:
        """Alias for ``consume()``."""
        return self.consume(expected, message)

    def snapshot(self) -> int:
        """Return the current position (for rollback)."""
        return self.pos

    def restore(self, saved_pos: int) -> None:
        """Restore a previously saved position."""
        self.pos = saved_pos
