"""pf_parser_mixin.py — Parser mixin for Program Flow (PF) parsing.

Moves PF/pH/fF parsing logic from parser.py into a dedicated mixin,
as required by the Distributed Parser Architecture.

Ownership:
  - PF (keyword to activate the built-in PF library)
  - pH: ... pH.close (Program Handler block)
  - fF: ... f.close (Function Flow block)
  - fF.<target>: ... f.close (explicit target mode)
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    ClassNode,
    FunctionFlowNode,
    MethodInvokeNode,
    MethodNode,
    Node,
    ObjectDeclarationNode,
    ProgramHandlerNode,
)


class PFParserMixin:
    """Mixin that adds PF/pH/fF parsing to ``Parser``.

    Methods moved from parser.py during RC1 Parser Delegation sprint.
    Uses ``self._consume()``, ``self._check()``, ``self._advance()``,
    ``self._current()``, ``self.pos``, ``self.tokens``,
    ``self._in_ff_flow``, ``self._parse_body()``, ``self._parse_check()``,
    ``self._parse_key()``, provided by the Parser class.
    """

    # ── Program Handler (pH) block ──────────────────────────────────────

    def _parse_ph(self) -> ProgramHandlerNode:
        """Parse a Program Handler block:

            pH:
                @Cls.Name
                Obj.Class.Var
                M.Name
            pH.close
        """
        from parser.parser import ParseError
        tok = self._consume(TokenType.PH, "Expected 'pH'")
        self._consume(TokenType.COLON, "Expected ':' after 'pH'")

        body: list[Node] = []
        while not self._check(TokenType.PH_CLOSE, TokenType.EOF):
            item = self._parse_ph_item()
            if item is not None:
                body.append(item)

        has_close = self._check(TokenType.PH_CLOSE)
        if has_close:
            self._advance()

        return ProgramHandlerNode(
            body=body, line=tok.line, auto_close=not has_close,
        )

    def _parse_ph_item(self) -> Optional[Node]:
        """Parse a single entry inside a pH block.

        Supported forms:

            @Cls.Name       ->  ClassNode (reference only)
            Obj.Cls.Var     ->  ObjectDeclarationNode
            M.Name          ->  MethodNode (reference only)
        """
        from parser.parser import ParseError
        # Detect .run: or .fun: and reject
        if (self._check(TokenType.DOT)
                and self.pos + 2 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.IDENTIFIER
                and self.tokens[self.pos + 1].value in ("run", "fun")
                and self.tokens[self.pos + 2].type == TokenType.COLON):
            raise ParseError(
                ".run and .fun are not allowed inside pH blocks",
                self._current(),
            )

        tok = self._current()
        tt  = tok.type

        if tt == TokenType.AT:
            self._advance()
            self._consume(TokenType.CLS, "Expected 'Cls' after '@' in pH block")
            self._consume(TokenType.DOT, "Expected '.' after 'Cls' in pH block")
            name_tok = self._consume(
                TokenType.IDENTIFIER,
                "Expected class name after 'Cls.' in pH block",
            )
            return ClassNode(name=name_tok.value, line=tok.line, members=[])

        if tt == TokenType.OBJ:
            self._advance()
            self._consume(TokenType.DOT, "Expected '.' after 'Obj' in pH block")
            cls_tok = self._consume(
                TokenType.IDENTIFIER,
                "Expected class name after 'Obj.' in pH block",
            )
            self._consume(
                TokenType.DOT,
                "Expected '.' after class name in pH block",
            )
            var_tok = self._consume(
                TokenType.IDENTIFIER,
                "Expected variable name in pH block",
            )
            return ObjectDeclarationNode(
                object_name=var_tok.value, class_name=cls_tok.value, line=tok.line,
            )

        if tt == TokenType.M:
            self._advance()
            self._consume(TokenType.DOT, "Expected '.' after 'M' in pH block")
            name_tok = self._consume(
                TokenType.IDENTIFIER,
                "Expected method name after 'M.' in pH block",
            )
            return MethodNode(name=name_tok.value, line=tok.line, body=[])

        raise ParseError(
            "Expected '@Cls.', 'Obj.', or 'M.' in pH block",
            tok,
        )

    # ── Function Flow (fF) block ────────────────────────────────────────

    def _parse_ff(self) -> FunctionFlowNode:
        """Parse a Function Flow block:

        Mode A (unbound):
            fF:
                Object.Method
            f.close

        Mode B (explicit target):
            fF.M.Login:
                User.Validate
                User.Login
            f.close
        """
        from parser.parser import ParseError
        tok = self._consume(TokenType.FF, "Expected 'fF'")

        # Detect Mode B: fF.<target>:
        target: str | None = None
        if self._check(TokenType.DOT):
            self._advance()  # consume '.'
            parts: list[str] = []
            while not self._check(TokenType.COLON, TokenType.EOF):
                t = self._current()
                if t.type == TokenType.AT:
                    parts.append("@")
                    self._advance()
                elif t.type == TokenType.DOT:
                    parts.append(".")
                    self._advance()
                else:
                    parts.append(str(t.value))
                    self._advance()
            target = "".join(parts)

        self._consume(TokenType.COLON, "Expected ':' after 'fF'")

        body: list[Node] = []
        saved_in_ff = self._in_ff_flow
        self._in_ff_flow = True
        try:
            while not self._check(TokenType.FUN_CLOSE, TokenType.EOF):
                item = self._parse_ff_item()
                if item is not None:
                    body.append(item)
        finally:
            self._in_ff_flow = saved_in_ff

        has_close = self._check(TokenType.FUN_CLOSE)
        if has_close:
            self._advance()

        return FunctionFlowNode(
            body=body, line=tok.line, auto_close=not has_close, target=target,
        )

    def _parse_ff_item(self) -> Optional[Node]:
        """Parse a single entry inside an fF block.

        Supported forms:

            Object.Method       ->  MethodInvokeNode
            Check: … Check.close  ->  CheckNode
            Key.expr: … Key.close ->  SwitchNode

        Raises a clear error for .run: inside fF.
        """
        from parser.parser import ParseError
        # Detect .run: or .fun: and reject
        if (self._check(TokenType.DOT)
                and self.pos + 2 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.IDENTIFIER
                and self.tokens[self.pos + 1].value in ("run", "fun")
                and self.tokens[self.pos + 2].type == TokenType.COLON):
            raise ParseError(
                ".run and .fun are not allowed inside fF blocks",
                self._current(),
            )

        # Check / Key blocks inside fF
        if self._check(TokenType.CHECK):
            return self._parse_check()
        if self._check(TokenType.KEY):
            return self._parse_key()

        # Object.Method (default)
        obj_tok = self._consume(
            TokenType.IDENTIFIER,
            "Expected object name in fF block",
        )
        self._consume(TokenType.DOT, "Expected '.' after object name in fF block")
        method_tok = self._consume(
            TokenType.IDENTIFIER,
            "Expected method name after '.' in fF block",
        )
        return MethodInvokeNode(
            method_name=method_tok.value,
            object_name=obj_tok.value,
            line=obj_tok.line,
        )
