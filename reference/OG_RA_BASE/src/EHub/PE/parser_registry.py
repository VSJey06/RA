"""ParserRegistry — Registry of shared parser helpers and utilities.

Stores module-level constants and helper methods that are shared
across all specialized parsers.
"""

from __future__ import annotations

from lexer.tokens import Token, TokenType

# ── Logical keyword types (used by statement dispatcher) ────────────────

LOGICAL_KEYWORD_TYPES: frozenset[TokenType] = frozenset({
    TokenType.AND_KW, TokenType.OR_KW, TokenType.XOR_KW,
    TokenType.NOR_KW, TokenType.NAND_KW, TokenType.XNOR_KW,
})

# ── Bitwise keyword types ────────────────────────────────────────────────

BITWISE_KEYWORD_TYPES: frozenset[TokenType] = frozenset({
    TokenType.BAND_KW, TokenType.BOR_KW, TokenType.BXOR_KW,
    TokenType.BLSHIFT_KW, TokenType.BRSHIFT_KW,
})

# ── Compound assignment operator text map ───────────────────────────────

COMPOUND_ASSIGN_OPS: dict[TokenType, str] = {
    TokenType.PLUS_ASSIGN:   "+=",
    TokenType.MINUS_ASSIGN:  "-=",
    TokenType.STAR_ASSIGN:   "*=",
    TokenType.SLASH_ASSIGN:  "/=",
    TokenType.PERCENT_ASSIGN: "%=",
    TokenType.CARET_ASSIGN:  "^=",
}

# 3-char compound assignment patterns: (first_token, second_token) -> operator text
COMPOUND_3CHAR: dict[tuple[TokenType, TokenType], str] = {
    (TokenType.DSTAR,   TokenType.ASSIGN): "**=",
    (TokenType.DSLASH,  TokenType.ASSIGN): "//=",
    (TokenType.DPERCENT, TokenType.ASSIGN): "%%=",
}

# ── Token type sets for operator precedence ────────────────────────────

COMPARISON_OPS: frozenset[TokenType] = frozenset({
    TokenType.EQ, TokenType.NEQ,
    TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE,
})

ADDITIVE_OPS: frozenset[TokenType] = frozenset({
    TokenType.PLUS, TokenType.MINUS,
})

MULTIPLICATIVE_OPS: frozenset[TokenType] = frozenset({
    TokenType.STAR, TokenType.SLASH, TokenType.PERCENT,
    TokenType.DSLASH, TokenType.DPERCENT,
})

POWER_OPS: frozenset[TokenType] = frozenset({
    TokenType.DSTAR, TokenType.CARET,
})

BINARY_OPS: frozenset[TokenType] = frozenset({
    TokenType.EQ,    TokenType.NEQ,
    TokenType.GT,    TokenType.LT,   TokenType.GTE, TokenType.LTE,
    TokenType.PLUS,  TokenType.MINUS,
    TokenType.STAR,  TokenType.SLASH, TokenType.PERCENT,
    TokenType.DSLASH, TokenType.DPERCENT,
    TokenType.DSTAR, TokenType.CARET,
    TokenType.SEMICOLON,
})


class ParserRegistry:
    """Holds shared parsing utilities accessible to all specialized parsers.

    Provides module-level constants as instance attributes so that
    specialized parsers can access them via ``self.registry.<X>``.
    """

    def __init__(self) -> None:
        self.LOGICAL_KEYWORD_TYPES = LOGICAL_KEYWORD_TYPES
        self.BITWISE_KEYWORD_TYPES = BITWISE_KEYWORD_TYPES
        self.COMPOUND_ASSIGN_OPS = COMPOUND_ASSIGN_OPS
        self.COMPOUND_3CHAR = COMPOUND_3CHAR
        self.COMPARISON_OPS = COMPARISON_OPS
        self.ADDITIVE_OPS = ADDITIVE_OPS
        self.MULTIPLICATIVE_OPS = MULTIPLICATIVE_OPS
        self.POWER_OPS = POWER_OPS
        self.BINARY_OPS = BINARY_OPS
