"""
tokenizer.py — Lexer for the RA language
Converts raw source text into a flat list of Token objects.

Supported constructs
--------------------
  Keywords    : S  I  L  Cls  Obj  M  Db  db.next  db.break  db.close  p
  Compound    : @.close  /.close  .TF
  Symbols     : =  .  :  ==  ,  @  !  ?  #  /
  Literals    : STRING  INTEGER  FLOAT  IDENTIFIER
  Comments    : # …  (rest of line is ignored after the HASH token)

Pattern examples correctly tokenized
--------------------------------------
  Db:              → DB  COLON
  @Cls.Person:     → AT  CLS  DOT  IDENTIFIER("Person")  COLON
  M.calculate:     → M   DOT  IDENTIFIER("calculate")    COLON
  db.next          → DB_NEXT
  db.break         → DB_BREAK
  db.close         → DB_CLOSE
"""

from __future__ import annotations

from typing import Any

from lexer.tokens import KEYWORDS, SYMBOLS, Token, TokenType


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TokenizeError(Exception):
    """Raised when the lexer encounters something it cannot handle."""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"[line {line}, col {column}] TokenizeError: {message}")
        self.message = message
        self.line   = line
        self.column = column


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class Tokenizer:
    """
    Single-pass, character-by-character lexer for the RA language.

    Usage
    -----
        t = Tokenizer(source_code)
        tokens = t.tokenize()
    """

    # Recognised suffixes for the compound db.* keywords
    _DB_SUFFIXES: frozenset[str] = frozenset({"next", "break", "close"})

    def __init__(self, source: str) -> None:
        self.source  = source
        self.pos     = 0          # current index into source
        self.line    = 1          # 1-based line counter
        self.column  = 1          # 1-based column counter

    # ── Low-level character helpers ──────────────────────────────────────────

    def _current(self) -> str:
        """Return the character at the current position, or NUL at EOF."""
        return self.source[self.pos] if self.pos < len(self.source) else "\0"

    def _peek(self, offset: int = 1) -> str:
        """Return the character offset positions ahead, or NUL at EOF."""
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else "\0"

    def _advance(self) -> str:
        """Consume and return the current character, updating line/column."""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line  += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _skip_whitespace(self) -> None:
        """Advance past spaces, tabs, carriage returns, and newlines."""
        while self._current() in (" ", "\t", "\r", "\n"):
            self._advance()

    # ── Token factory ────────────────────────────────────────────────────────

    def _tok(
        self,
        ttype:  TokenType,
        value:  Any,
        line:   int,
        column: int,
        was_measurement: bool = False,
    ) -> Token:
        return Token(
            type=ttype, value=value, line=line, column=column,
            end_line=self.line,
            end_column=max(1, self.column - 1),
            was_measurement=was_measurement,
        )

    # ── Scanners ─────────────────────────────────────────────────────────────

    def _scan_comment(self, line: int, col: int) -> Token:
        """
        Emit a HASH token and discard everything up to (not including)
        the newline so the next iteration picks up the next line cleanly.
        """
        self._advance()                          # consume '#'
        while self._current() not in ("\n", "\0"):
            self._advance()
        return self._tok(TokenType.HASH, "#", line, col)

    def _scan_string(self, quote: str, line: int, col: int) -> Token:
        """
        Consume a single- or double-quoted string literal.
        Backslashes are treated as literal characters.
        Raises TokenizeError on an unterminated literal.
        """
        self._advance()          # opening quote
        buf: list[str] = []

        while True:
            ch = self._current()
            if ch == "\0":
                raise TokenizeError("Unterminated string literal", line, col)
            if ch == quote:
                self._advance()  # closing quote
                break
            else:
                buf.append(self._advance())

        return self._tok(TokenType.STRING, "".join(buf), line, col)

    def _scan_number(self, line: int, col: int) -> Token:
        """
        Consume a contiguous run of decimal digits, optionally followed by
        a numeric suffix (K, Lh, Cr, B, Tri, Qd), or a decimal point plus
        more digits for float literals.
        """
        buf: list[str] = []
        while self._current().isdigit():
            buf.append(self._advance())

        # ── Float literal  (digits . digits) ──────────────────────────
        if self._current() == "." and self._peek().isdigit():
            buf.append(self._advance())   # consume '.'
            while self._current().isdigit():
                buf.append(self._advance())
            value = float("".join(buf))
            suffix = self._scan_numeric_suffix()
            was_ms = suffix is not None
            if suffix:
                value *= suffix
            return self._tok(TokenType.FLOAT, value, line, col,
                             was_measurement=was_ms)

        # ── Integer literal (optional suffix) ─────────────────────────
        value = int("".join(buf))

        # Reject identifiers that begin with a digit
        # (e.g. "1age", "5amount") unless it's a valid suffix
        if self._current().isalpha() and not self._looks_like_suffix():
            ch = self._current()
            raise TokenizeError(
                f"Identifier cannot begin with digit: '{value}{ch}...'",
                line, col,
            )

        # Check for imaginary unit suffix (5i, 3i, etc.)
        if self._scan_imaginary_suffix():
            return self._tok(TokenType.IMAGINARY, value, line, col)

        suffix = self._scan_numeric_suffix()
        was_ms = suffix is not None
        if suffix:
            value *= suffix

        return self._tok(TokenType.INTEGER, value, line, col,
                         was_measurement=was_ms)

    # ── Numeric Suffix Map ───────────────────────────────────────────
    # NOTE: This map MUST stay in sync with the canonical scale registry
    # at libraries/Measurement/scales.py (SCALE_REGISTRY).
    # The canonical registry is the SINGLE SOURCE OF TRUTH for all
    # measurement scale definitions.  Updates MUST be made there first,
    # then mirrored here.
    _SUFFIX_MAP: dict[str, int] = {
        "Tri": 1_000_000_000_000,
        "Lh":    100_000,
        "M":     1_000_000,
        "Cr":    10_000_000,
        "B":     1_000_000_000,
        "T":     1_000_000_000_000,
        "K":     1_000,
        "Qd":    1_000_000_000_000_000,
    }

    def _looks_like_suffix(self) -> bool:
        """Check if the current position looks like a valid numeric suffix.

        Used to avoid rejecting identifiers like "1K" (measurement suffix)
        or "5i" (imaginary unit).
        """
        ch = self._current().lower()
        # Single-char suffixes: K, M, B, T, i
        if ch in ("k", "m", "b", "t", "i"):
            return True
        # Multi-char suffix starts
        chunk = self.source[self.pos:self.pos + 3].lower()
        if chunk.startswith("tri") or chunk.startswith("lh") \
                or chunk.startswith("cr") or chunk.startswith("qd"):
            return True
        return False

    def _scan_numeric_suffix(self) -> int | None:
        """Return the multiplier for a numeric suffix, or None."""
        for suffix_len in (3, 2, 1):
            if suffix_len > len(self.source) - self.pos:
                continue
            chunk = self.source[self.pos:self.pos + suffix_len]
            mult = self._SUFFIX_MAP.get(chunk)
            if mult is not None:
                for _ in range(suffix_len):
                    self._advance()
                return mult
        return None

    def _scan_imaginary_suffix(self) -> bool:
        """Check for 'i' suffix (imaginary unit) after a number.

        Returns True if 'i' was consumed.
        """
        if self._current() == "i":
            self._advance()
            return True
        return False
        """Check for 'i' suffix (imaginary unit) after a number.

        Returns True if 'i' was consumed.
        """
        if self._current() == "i":
            self._advance()
            return True
        return False

    def _scan_word(self, line: int, col: int) -> Token:
        """
        Consume a word (letters, digits, underscores) and classify it as:

          1. A compound keyword  (db.next / db.break / db.close / r.close /
             f.close / Con.close / En.close …)
          2. A plain keyword     (Db, Cls, M, Con, En, OOP, …)
          3. An identifier       (everything else)
        """
        buf: list[str] = []
        while self._current().isalnum() or self._current() == "_":
            buf.append(self._advance())
        word = "".join(buf)

        # ── Compound keyword detection (word.suffix) ──────────────────
        #   Try to form a compound keyword by consuming a dot + alphabetic
        #   suffix.  Backtrack on failure so the dot can be consumed as a
        #   separate symbol.
        if self._current() == ".":
            snap_pos = self.pos
            snap_col = self.column
            self._advance()          # consume '.'

            suffix_buf: list[str] = []
            while self._current().isalpha():
                suffix_buf.append(self._advance())
            suffix = "".join(suffix_buf)

            if suffix:
                compound = f"{word}.{suffix}"
                if compound in KEYWORDS:
                    return self._tok(KEYWORDS[compound], compound, line, col)

            # Unknown suffix → backtrack so '.' is a separate symbol
            self.pos    = snap_pos
            self.column = snap_col

        # ── Plain keyword or identifier ──────────────────────────────────
        if word in KEYWORDS:
            return self._tok(KEYWORDS[word], word, line, col)

        return self._tok(TokenType.IDENTIFIER, word, line, col)

    def _scan_symbol(self, line: int, col: int) -> Token:
        """
        Perform longest-match (up to 4 chars) symbol recognition.
        Returns an UNKNOWN token for any unrecognised character, allowing the
        caller to continue rather than crash.
        """
        four = self.source[self.pos: self.pos + 4]
        if len(four) == 4 and four in SYMBOLS:
            for _ in range(4):
                self._advance()
            return self._tok(SYMBOLS[four], four, line, col)

        three = self.source[self.pos: self.pos + 3]
        if len(three) == 3 and three in SYMBOLS:
            self._advance()
            self._advance()
            self._advance()
            return self._tok(SYMBOLS[three], three, line, col)

        two = self.source[self.pos: self.pos + 2]
        if len(two) == 2 and two in SYMBOLS:
            self._advance()
            self._advance()
            return self._tok(SYMBOLS[two], two, line, col)

        one = self._current()
        if one in SYMBOLS:
            self._advance()
            return self._tok(SYMBOLS[one], one, line, col)

        # Unrecognised — consume, log as UNKNOWN (error-recovery)
        ch = self._advance()
        return self._tok(TokenType.UNKNOWN, ch, line, col)

    # ── Main entry point ─────────────────────────────────────────────────────

    def tokenize(self) -> list[Token]:
        """
        Scan the entire source string and return a list of Token objects.
        The last element is always Token(EOF).

        Raises
        ------
        TokenizeError
            On an unterminated string literal.
        """
        tokens: list[Token] = []

        while True:
            self._skip_whitespace()

            line, col = self.line, self.column
            ch = self._current()

            # ── End of file ──────────────────────────────────────────────
            if ch == "\0":
                tokens.append(self._tok(TokenType.EOF, None, line, col))
                break

            # ── Comment / terminator  # … EOL ───────────────────────────
            # #. is a special case: emit HASH + DOT as separate tokens
            # (used for Which/What selector/argument syntax)
            if ch == "#":
                if self._peek() == ".":
                    # #. — emit HASH without consuming rest of line
                    self._advance()  # consume '#'
                    tokens.append(self._tok(TokenType.HASH, "#", line, col))
                    continue
                tokens.append(self._scan_comment(line, col))
                continue

            # ── String literals ──────────────────────────────────────────
            if ch in ('"', "'"):
                tokens.append(self._scan_string(ch, line, col))
                continue

            # ── Integer literals ─────────────────────────────────────────
            if ch.isdigit():
                tokens.append(self._scan_number(line, col))
                continue

            # ── Keywords / identifiers (+ compound db.*) ─────────────────
            if ch.isalpha() or ch == "_":
                tokens.append(self._scan_word(line, col))
                continue

            # ── Compound @.close ─────────────────────────────────────────
            if ch == "@" and self.source[self.pos:self.pos + 7] == "@.close":
                for _ in range(7):
                    self._advance()
                tokens.append(self._tok(TokenType.AT_CLOSE, "@.close", line, col))
                continue

            # ── Compound /.close ──────────────────────────────────────────
            if ch == "/" and self.source[self.pos:self.pos + 7] == "/.close":
                for _ in range(7):
                    self._advance()
                tokens.append(self._tok(TokenType.METHOD_CLOSE, "/.close", line, col))
                continue

            # ── Compound .TF (boolean suffix) ─────────────────────────────
            if ch == "." and self.source[self.pos:self.pos + 3] == ".TF":
                for _ in range(3):
                    self._advance()
                tokens.append(self._tok(TokenType.BOOLEAN_TF, ".TF", line, col))
                continue

            # ── Symbols & operators ───────────────────────────────────────
            tokens.append(self._scan_symbol(line, col))

        return tokens


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def tokenize(source: str) -> list[Token]:
    """Shorthand: ``tokenize(src)`` instead of ``Tokenizer(src).tokenize()``."""
    return Tokenizer(source).tokenize()


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    _SAMPLE = """
# RA language sample
Db:
    db.next
    db.break
    db.close

@Cls.Person:
    S name = "Alice"
    I age  = 30

M.calculate:
    I result = 100
    p result

Obj person = Person
S response = "summarise this"
x == y
x = 42
p a>b.TF
"""

    print("=" * 60)
    print("RA Tokenizer — self-test")
    print("=" * 60)

    _tokens = tokenize(_SAMPLE)
    for tok in _tokens:
        print(tok)
