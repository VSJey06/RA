"""
tokens.py — Token type definitions for the RA language.

Provides the TokenType enumeration, the Token dataclass, and
lookup tables for keywords and symbols.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from parser.source_location import SourceLocation


# ---------------------------------------------------------------------------
# Token Types
# ---------------------------------------------------------------------------

class TokenType(Enum):
    """Every token category recognised by the RA lexer."""

    # ── Keywords ──────────────────────────────────────────────────────────
    S        = auto()   # String type declaration
    I        = auto()   # Integer type declaration
    L        = auto()   # List type declaration
    TF       = auto()   # Boolean type declaration
    BOOLEAN_TF = auto()   # Boolean .TF suffix
    RUN_CLOSE   = auto()   # r.close (run-block terminator)
    FUN_CLOSE   = auto()   # f.close (function-block terminator)
    OOP      = auto()   # OOP library activation
    CON      = auto()   # Constructor block open  (Con)
    CON_CLOSE = auto()  # con.close / Con.close
    EN       = auto()   # Encapsulation block open  (En)
    EN_CLOSE  = auto()  # en.close / En.close
    CLS      = auto()   # Class definition  (@Cls)
    OBJ      = auto()   # Object instantiation  (Obj)
    M        = auto()   # Method definition  (M)
    DB       = auto()   # Database block open  (Db)
    DB_NEXT  = auto()   # db.next
    DB_BREAK = auto()   # db.break
    DB_CLOSE  = auto()   # db.close
    SDB      = auto()   # Structured Database block open  (Sdb)
    SDB_CLOSE = auto()  # sdb.close
    AT_CLOSE   = auto()   # @.close
    METHOD_CLOSE = auto()   # /.close
    P        = auto()   # Print / output (with newline)
    PL       = auto()   # Print line  (without newline)
    R        = auto()   # Return
    CHECK    = auto()   # Check block open
    CHECK_CLOSE = auto()  # Check.close
    VALID    = auto()   # Valid section
    INVALID  = auto()   # Invalid section
    KEY      = auto()   # Key (switch) block open
    KEY_CLOSE = auto()  # Key.close
    PF       = auto()   # PF library activation
    PH       = auto()   # Program Handler pH
    PH_CLOSE = auto()   # pH.close
    FF       = auto()   # Function Flow fF
    CF       = auto()   # Control Flow library activation
    FUN_BLOCK = auto()  # Fun: keyword (uppercase Function block)

    # ── Symbols / operators ──────────────────────────────────────────────
    ASSIGN       = auto()   # =
    NEQ          = auto()   # !=
    DOT          = auto()   # .
    COLON        = auto()   # :
    EQ           = auto()   # ==
    COMMA        = auto()   # ,
    AT           = auto()   # @
    BANG         = auto()   # !
    QUESTION     = auto()   # ?
    HASH         = auto()   # #
    SLASH        = auto()   # /

    # Compound assignment operators
    PLUS_ASSIGN   = auto()   # +=
    MINUS_ASSIGN  = auto()   # -=
    STAR_ASSIGN   = auto()   # *=
    SLASH_ASSIGN  = auto()   # /=
    PERCENT_ASSIGN = auto() # %=
    CARET_ASSIGN  = auto()   # ^=

    # Arithmetic / comparison operators (no longer UNKNOWN)
    PLUS     = auto()   # +
    MINUS    = auto()   # -
    STAR     = auto()   # *
    PERCENT  = auto()   # %
    DSLASH   = auto()   # //
    DPERCENT = auto()   # %%
    DSTAR    = auto()   # **
    CARET    = auto()   # ^
    GT       = auto()   # >
    LT       = auto()   # <
    GTE      = auto()   # >=
    LTE      = auto()   # <=
    SEMICOLON = auto()  # ;

    # ── Literals ─────────────────────────────────────────────────────────
    STRING          = auto()   # "hello"  or  'hello'
    INTEGER         = auto()   # 42
    FLOAT           = auto()   # 3.14
    BOOLEAN_LITERAL = auto()   # True / False
    IDENTIFIER      = auto()   # variable / symbol names

    # ── Block Family keywords (RC2-04A) ──────────────────────────────────
    PRINT_BLOCK  = auto()   # Print (top-level block declaration)
    IP_BLOCK     = auto()   # Ip (top-level input block declaration)
    IP_CLOSE     = auto()   # ip.close (input block terminator)
    PF_PRINT     = auto()   # pf (formatted print)

    # ── Nested Block keywords ───────────────────────────────────────────
    IF_NESTED    = auto()   # if (nested inside block)
    ELIF_NESTED  = auto()   # elif (nested inside block)
    ELSE_NESTED  = auto()   # else (nested inside block)
    FUN_NESTED   = auto()   # fun (nested inside block)
    PRINT_NESTED = auto()   # print (nested inside block)
    FOR_NESTED   = auto()   # for (nested inside block)
    WHILE_NESTED = auto()   # while (nested inside block)
    RUN_NESTED   = auto()   # run (nested inside block)

    # ── What Block (Type Decision Engine) ────────────────────────────────
    WHAT     = auto()   # !What (Type Decision Engine block)

    # ── Complex Family tokens ──────────────────────────────────────────────
    C        = auto()   # Complex Family identifier (C) — canonical
    CX       = auto()   # Complex Number (Cx) — reserved
    CS       = auto()   # Complex Standard Equation (Cs) — reserved
    CA       = auto()   # Complex Algebra Equation (Ca) — reserved
    CM       = auto()   # Complex Magnitude (Cm) — reserved
    IMAGINARY = auto()   # Imaginary number literal (e.g. 5i)

    # ── IO / Input tokens ────────────────────────────────────────────────
    INPUT_SPEC   = auto()   # Generic .in / I.in / c.in etc.
    PR           = auto()   # Paragraph print (pr)
    F            = auto()   # Float type declaration
    D            = auto()   # Double type declaration

    # ── Logical operator symbols ─────────────────────────────────────────
    AMPERSAND   = auto()   # &  (part of &&)
    PIPE        = auto()   # |  (part of ||)
    LOGICAL_AND = auto()   # &&
    LOGICAL_OR  = auto()   # ||
    LOGICAL_XOR = auto()   # ^||
    LOGICAL_NOR = auto()   # ^|^
    LOGICAL_NAND = auto()  # ^&^
    LOGICAL_XNOR = auto()  # ^||^

    # ── Logical keyword tokens ───────────────────────────────────────────
    AND_KW  = auto()   # and / AND
    OR_KW   = auto()   # or / OR
    NOT_KW  = auto()   # not / NOT
    XOR_KW  = auto()   # xor / XOR
    NOR_KW  = auto()   # nor / NOR
    NAND_KW = auto()   # nand / NAND
    XNOR_KW = auto()   # xnor / XNOR
    YES_KW  = auto()   # Yes
    NO_KW   = auto()   # No
    YN_KW   = auto()   # YN

    # ── Bitwise operator keywords ──────────────────────────────────────
    BAND_KW   = auto()   # band / BAND
    BOR_KW    = auto()   # bor / BOR
    BNOT_KW   = auto()   # bnot / BNOT
    BXOR_KW   = auto()   # bxor / BXOR
    BLSHIFT_KW = auto()  # blshift / BLSHIFT
    BRSHIFT_KW = auto()  # brshift / BRSHIFT

    # ── Bitwise operator symbols ───────────────────────────────────────
    BITWISE_LSHIFT = auto()  # <<
    BITWISE_RSHIFT = auto()  # >>
    BITWISE_NOT    = auto()  # ~

    # ── Comparison operator tokens ─────────────────────────────────────
    STRICT_EQ = auto()  # ===
    FLOW_FWD      = auto()  # -->
    FLOW_REV      = auto()  # <--
    FLOW_TREE_FWD = auto()  # --->
    FLOW_TREE_REV = auto()  # <---

    # ── Brackets / Collection Container ─────────────────────────────────
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]

    # ── Braces ───────────────────────────────────────────────────────────
    LBRACE = auto()   # {
    RBRACE = auto()   # }

    # ── Parentheses ──────────────────────────────────────────────────────
    LPAREN = auto()   # (
    RPAREN = auto()   # )

    # ── Meta ─────────────────────────────────────────────────────────────
    EOF     = auto()   # end-of-file sentinel
    UNKNOWN = auto()   # unrecognised character (error recovery)


# ---------------------------------------------------------------------------
# Keyword lookup table
# ---------------------------------------------------------------------------

KEYWORDS: dict[str, TokenType] = {
    "S"        : TokenType.S,
    "I"        : TokenType.I,
    "L"        : TokenType.L,
    "TF"       : TokenType.TF,
    "True"     : TokenType.BOOLEAN_LITERAL,
    "False"    : TokenType.BOOLEAN_LITERAL,
    "Cls"      : TokenType.CLS,
    "Obj"      : TokenType.OBJ,
    "M"        : TokenType.M,
    "Db"       : TokenType.DB,
    "db.next"  : TokenType.DB_NEXT,
    "db.break" : TokenType.DB_BREAK,
    "db.close" : TokenType.DB_CLOSE,
    "Sdb"      : TokenType.SDB,
    "sdb.close": TokenType.SDB_CLOSE,
    "@.close"  : TokenType.AT_CLOSE,
    "/.close"  : TokenType.METHOD_CLOSE,
    "p"        : TokenType.P,
    "pf"       : TokenType.PF_PRINT,
    "pl"       : TokenType.PL,
    "R"        : TokenType.R,
    "r.close"  : TokenType.RUN_CLOSE,
    "f.close"  : TokenType.FUN_CLOSE,
    "OOP"      : TokenType.OOP,
    "Con"      : TokenType.CON,
    "Con.close": TokenType.CON_CLOSE,
    "con.close": TokenType.CON_CLOSE,
    "En"       : TokenType.EN,
    "En.close"  : TokenType.EN_CLOSE,
    "en.close"  : TokenType.EN_CLOSE,
    "Check"     : TokenType.CHECK,
    "Check.close" : TokenType.CHECK_CLOSE,
    "Valid"     : TokenType.VALID,
    "Invalid"   : TokenType.INVALID,
    "Key"       : TokenType.KEY,
    "Key.close"  : TokenType.KEY_CLOSE,
    "PF"        : TokenType.PF,
    "pH"        : TokenType.PH,
    "pH.close"  : TokenType.PH_CLOSE,
    "fF"        : TokenType.FF,
    "CF"        : TokenType.CF,
    "pr"        : TokenType.PR,
    "F"         : TokenType.F,
    "D"         : TokenType.D,
    # What is NOT a keyword — it's parsed as IDENTIFIER("What") after "!",
    # matching how "If", "Else", "Elseif", "For", "While" are handled.
    "I.in"      : TokenType.INPUT_SPEC,
    "S.in"      : TokenType.INPUT_SPEC,
    "F.in"      : TokenType.INPUT_SPEC,
    "D.in"      : TokenType.INPUT_SPEC,
    "L.in"      : TokenType.INPUT_SPEC,
    "Byte.in"   : TokenType.INPUT_SPEC,
    "Char.in"   : TokenType.INPUT_SPEC,
    "c.in"      : TokenType.INPUT_SPEC,
    "dchar.in"  : TokenType.INPUT_SPEC,
    "tchar.in"  : TokenType.INPUT_SPEC,
    "line.in"   : TokenType.INPUT_SPEC,
    "b.in"      : TokenType.INPUT_SPEC,
    "bl.in"     : TokenType.INPUT_SPEC,
    "par.in"    : TokenType.INPUT_SPEC,
    # Complex Family keywords
    "C"         : TokenType.C,
    "Cx"        : TokenType.CX,
    "Cs"        : TokenType.CS,
    "Ca"        : TokenType.CA,
    "Cm"        : TokenType.CM,
    # Nested block keywords (RC2-01 — conditional)
    "if"        : TokenType.IF_NESTED,
    "elif"      : TokenType.ELIF_NESTED,
    "else"      : TokenType.ELSE_NESTED,
    # Nested block keywords (RC2-02 — executable blocks)
    "fun"       : TokenType.FUN_NESTED,
    "Fun"       : TokenType.FUN_BLOCK,
    "Print"     : TokenType.PRINT_BLOCK,
    "Ip"        : TokenType.IP_BLOCK,
    "ip.close"  : TokenType.IP_CLOSE,
    "print"     : TokenType.PRINT_NESTED,
    "for"       : TokenType.FOR_NESTED,
    "while"     : TokenType.WHILE_NESTED,
    "run"       : TokenType.RUN_NESTED,
    # Logical operator keywords
    "and"       : TokenType.AND_KW,
    "AND"       : TokenType.AND_KW,
    "or"        : TokenType.OR_KW,
    "OR"        : TokenType.OR_KW,
    "not"       : TokenType.NOT_KW,
    "NOT"       : TokenType.NOT_KW,
    "xor"       : TokenType.XOR_KW,
    "XOR"       : TokenType.XOR_KW,
    "nor"       : TokenType.NOR_KW,
    "NOR"       : TokenType.NOR_KW,
    "nand"      : TokenType.NAND_KW,
    "NAND"      : TokenType.NAND_KW,
    "xnor"      : TokenType.XNOR_KW,
    "XNOR"      : TokenType.XNOR_KW,
    "Yes"       : TokenType.YES_KW,
    "No"        : TokenType.NO_KW,
    "YN"        : TokenType.YN_KW,
    # Bitwise operator keywords
    "band"      : TokenType.BAND_KW,
    "BAND"      : TokenType.BAND_KW,
    "bor"       : TokenType.BOR_KW,
    "BOR"       : TokenType.BOR_KW,
    "bnot"      : TokenType.BNOT_KW,
    "BNOT"      : TokenType.BNOT_KW,
    "bxor"      : TokenType.BXOR_KW,
    "BXOR"      : TokenType.BXOR_KW,
    "blshift"   : TokenType.BLSHIFT_KW,
    "BLSHIFT"   : TokenType.BLSHIFT_KW,
    "brshift"   : TokenType.BRSHIFT_KW,
    "BRSHIFT"   : TokenType.BRSHIFT_KW,
}

# ---------------------------------------------------------------------------
# Symbol lookup table
# (longest-match ordering: 2-char entries before 1-char suffixes)
# ---------------------------------------------------------------------------

SYMBOLS: dict[str, TokenType] = {
    "==" : TokenType.EQ,
    "!=" : TokenType.NEQ,
    ">=" : TokenType.GTE,
    "<=" : TokenType.LTE,
    "//" : TokenType.DSLASH,
    "%%" : TokenType.DPERCENT,
    "**" : TokenType.DSTAR,
    "+=" : TokenType.PLUS_ASSIGN,
    "-=" : TokenType.MINUS_ASSIGN,
    "*=" : TokenType.STAR_ASSIGN,
    "/=" : TokenType.SLASH_ASSIGN,
    "%=" : TokenType.PERCENT_ASSIGN,
    "^=" : TokenType.CARET_ASSIGN,
    "="  : TokenType.ASSIGN,
    "."  : TokenType.DOT,
    ":"  : TokenType.COLON,
    ","  : TokenType.COMMA,
    "@"  : TokenType.AT,
    "!"  : TokenType.BANG,
    "?"  : TokenType.QUESTION,
    "#"  : TokenType.HASH,
    "^"  : TokenType.CARET,
    "/"  : TokenType.SLASH,
    "+"  : TokenType.PLUS,
    "-"  : TokenType.MINUS,
    "*"  : TokenType.STAR,
    "%"  : TokenType.PERCENT,
    ">"  : TokenType.GT,
    "<"  : TokenType.LT,
    ";"  : TokenType.SEMICOLON,
    "&&" : TokenType.LOGICAL_AND,
    "||" : TokenType.LOGICAL_OR,
    "===" : TokenType.STRICT_EQ,
    "--->" : TokenType.FLOW_TREE_FWD,
    "<---" : TokenType.FLOW_TREE_REV,
    "-->" : TokenType.FLOW_FWD,
    "<--" : TokenType.FLOW_REV,
    "<<" : TokenType.BITWISE_LSHIFT,
    ">>" : TokenType.BITWISE_RSHIFT,
    "&"  : TokenType.AMPERSAND,
    "|"  : TokenType.PIPE,
    "~"  : TokenType.BITWISE_NOT,
    "("  : TokenType.LPAREN,
    ")"  : TokenType.RPAREN,
    "["  : TokenType.LBRACKET,
    "]"  : TokenType.RBRACKET,
    "{"  : TokenType.LBRACE,
    "}"  : TokenType.RBRACE,
}


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

@dataclass
class Token:
    """A single lexical unit produced by the RA tokenizer.

    Attributes
    ----------
    type      : TokenType — category of this token.
    value     : Any       — raw source text (or coerced Python value).
    line      : int       — 1-based line number.
    column    : int       — 1-based column number.
    end_line  : int       — 1-based end line (inclusive).
    end_column: int       — 1-based end column (inclusive).
    was_measurement : bool — True when an INTEGER/FLOAT token was produced
                             from a numeric literal with a measurement suffix
                             (e.g. ``5K``, ``3Cr``).  Default ``False``.
    """

    type:       TokenType
    value:      Any
    line:       int
    column:     int
    end_line:   int = 0
    end_column: int = 0
    was_measurement: bool = False

    @property
    def source_location(self) -> SourceLocation:
        return SourceLocation(
            line=self.line, column=self.column,
            end_line=self.end_line or self.line,
            end_column=self.end_column or self.column,
        )

    def is_keyword(self) -> bool:
        """Return True if this token is any RA keyword."""
        return self.type in _KEYWORD_SET

    def is_literal(self) -> bool:
        """Return True if this token is a literal value."""
        return self.type in _LITERAL_SET

    def is_symbol(self) -> bool:
        """Return True if this token is a symbol / operator."""
        return self.type in _SYMBOL_SET

    def __repr__(self) -> str:
        return (
            f"Token(type={self.type.name}, value={self.value!r}, "
            f"line={self.line}, col={self.column}, "
            f"end=({self.end_line},{self.end_column}))"
        )


# ── Pre-built sets ──────────────────────────────────────────────────────

_KEYWORD_SET: frozenset[TokenType] = frozenset({
    TokenType.S, TokenType.I, TokenType.L, TokenType.TF,
    TokenType.BOOLEAN_LITERAL,
    TokenType.BOOLEAN_TF, TokenType.RUN_CLOSE,
    TokenType.FUN_CLOSE,
    TokenType.OOP, TokenType.CON, TokenType.CON_CLOSE,
    TokenType.EN, TokenType.EN_CLOSE,
    TokenType.CLS, TokenType.OBJ, TokenType.M,
    TokenType.DB, TokenType.DB_NEXT, TokenType.DB_BREAK, TokenType.DB_CLOSE,
    TokenType.SDB, TokenType.SDB_CLOSE,
    TokenType.AT_CLOSE, TokenType.METHOD_CLOSE,
    TokenType.P, TokenType.R,
    TokenType.CHECK, TokenType.CHECK_CLOSE,
    TokenType.VALID, TokenType.INVALID,
    TokenType.KEY, TokenType.KEY_CLOSE,
    TokenType.PF, TokenType.PH, TokenType.PH_CLOSE, TokenType.FF, TokenType.CF,
    TokenType.PR, TokenType.F, TokenType.D, TokenType.PF_PRINT,
    TokenType.CX, TokenType.CS, TokenType.CA, TokenType.CM,
    TokenType.INPUT_SPEC,
    TokenType.AND_KW, TokenType.OR_KW, TokenType.NOT_KW,
    TokenType.XOR_KW, TokenType.NOR_KW, TokenType.NAND_KW, TokenType.XNOR_KW,
    TokenType.YES_KW, TokenType.NO_KW, TokenType.YN_KW,
    TokenType.BAND_KW, TokenType.BOR_KW, TokenType.BNOT_KW,
    TokenType.BXOR_KW, TokenType.BLSHIFT_KW, TokenType.BRSHIFT_KW,
    TokenType.PRINT_BLOCK, TokenType.IP_BLOCK,
    TokenType.IP_CLOSE,
    TokenType.IF_NESTED, TokenType.ELIF_NESTED, TokenType.ELSE_NESTED,
    TokenType.FUN_BLOCK, TokenType.FUN_NESTED, TokenType.PRINT_NESTED,
    TokenType.FOR_NESTED, TokenType.WHILE_NESTED, TokenType.RUN_NESTED,
})

_LITERAL_SET: frozenset[TokenType] = frozenset({
    TokenType.STRING,
    TokenType.INTEGER,
    TokenType.FLOAT,
    TokenType.BOOLEAN_LITERAL,
    TokenType.IDENTIFIER,
    TokenType.IMAGINARY,
})

_SYMBOL_SET: frozenset[TokenType] = frozenset({
    TokenType.ASSIGN, TokenType.NEQ,   TokenType.DOT,
    TokenType.COLON,  TokenType.EQ,    TokenType.COMMA,
    TokenType.AT,     TokenType.BANG,  TokenType.QUESTION,
    TokenType.HASH,   TokenType.SLASH,
    TokenType.PLUS,   TokenType.MINUS, TokenType.STAR,
    TokenType.PERCENT, TokenType.DSLASH, TokenType.DPERCENT,
    TokenType.DSTAR,  TokenType.CARET,
    TokenType.GT,   TokenType.LT,
    TokenType.GTE,    TokenType.LTE,   TokenType.SEMICOLON,
    TokenType.PLUS_ASSIGN,   TokenType.MINUS_ASSIGN,
    TokenType.STAR_ASSIGN,   TokenType.SLASH_ASSIGN,
    TokenType.PERCENT_ASSIGN, TokenType.CARET_ASSIGN,
    TokenType.LOGICAL_AND, TokenType.LOGICAL_OR,
    TokenType.AMPERSAND, TokenType.PIPE,
    TokenType.BITWISE_LSHIFT, TokenType.BITWISE_RSHIFT,
    TokenType.BITWISE_NOT,
    TokenType.STRICT_EQ,
    TokenType.FLOW_FWD,
    TokenType.FLOW_REV,
    TokenType.FLOW_TREE_FWD,
    TokenType.FLOW_TREE_REV,
    TokenType.LBRACKET,
    TokenType.RBRACKET,
    TokenType.LBRACE,
    TokenType.RBRACE,
})
