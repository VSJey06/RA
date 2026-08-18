"""DeclarationParser — Typed assignment parsing.

Handles all declaration forms:
  - Standard typed assignments:  S name = value, I name = value
  - Multi-declarations:          I a, b, c = 1, 2, 3
  - Relation assignments:        I.age.Jey : value
  - Complex variants:            Cx, Cs, Ca, Cm
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    AssignmentNode,
    BooleanNode,
    CaNode,
    CmNode,
    CsNode,
    CxNode,
    LiteralNode,
    MultiAssignmentNode,
    Node,
    RelationAssignmentNode,
)
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class DeclarationParser:
    """Parses typed variable declarations and relation assignments."""

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry
        self._expression_parser: Optional[callable] = None

    def parse_typed_assignment(self) -> Node:
        """Parse a typed assignment or relation assignment."""
        type_tok = self.env.advance()

        # C Complex Family: C.a = expr  or  C a = expr
        if type_tok.type == TokenType.C:
            if self.env.check(TokenType.DOT):
                self.env.advance()  # consume '.'
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected identifier after 'C.'",
                )
                self.env.consume(
                    TokenType.ASSIGN,
                    "Expected '=' after 'C.<var>'",
                )
                value = self._parse_expression()
            else:
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected identifier after 'C'",
                )
                if self.env.check(TokenType.ASSIGN):
                    self.env.advance()
                    value = self._parse_expression()
                else:
                    value = LiteralNode(
                        value=0j, kind=TokenType.IMAGINARY,
                        line=type_tok.line,
                    )
            return AssignmentNode(
                var_type=type_tok.type, name=name_tok.value,
                value=value, line=type_tok.line,
            )

        if not self.env.check(TokenType.DOT):
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                f"Expected identifier after '{type_tok.value}'",
            )

            # Multi-declaration: I a, b, c = 1, 2, 3
            if self.env.check(TokenType.COMMA):
                names = [name_tok.value]
                while self.env.check(TokenType.COMMA):
                    self.env.advance()
                    ntok = self.env.consume(
                        TokenType.IDENTIFIER,
                        "Expected identifier after ','",
                    )
                    names.append(ntok.value)
                self.env.consume(
                    TokenType.ASSIGN,
                    "Expected '=' after variable list",
                )
                values = [self._parse_expression()]
                while self.env.check(TokenType.COMMA):
                    self.env.advance()
                    values.append(self._parse_expression())
                if len(names) != len(values):
                    from parser.parser import ParseError
                    raise ParseError(
                        "Variable/value count mismatch: "
                        f"{len(names)} variables but {len(values)} values",
                        type_tok,
                    )
                return MultiAssignmentNode(
                    var_type=type_tok.type,
                    names=names, values=values,
                    line=type_tok.line,
                )

            # Cs / Ca equation syntax
            if type_tok.type in (TokenType.CS, TokenType.CA):
                self.env.consume(
                    TokenType.ASSIGN,
                    f"Expected '=' after {type_tok.value} declaration",
                )
                lhs = self._parse_primary_chain()
                lhs = self._parse_binary_rhs(lhs)
                if self.env.check(TokenType.BOOLEAN_TF):
                    self.env.advance()
                    lhs = BooleanNode(expr=lhs, line=lhs.line)
                self.env.consume(
                    TokenType.COLON,
                    f"Expected ':' after LHS in {type_tok.value} equation",
                )
                rhs = self._parse_expression()
                if type_tok.type == TokenType.CS:
                    return CsNode(name=name_tok.value, value=lhs, rhs=rhs,
                                  line=type_tok.line)
                else:
                    return CaNode(name=name_tok.value, value=lhs, rhs=rhs,
                                  line=type_tok.line)

            # Cm magnitude syntax
            if type_tok.type == TokenType.CM:
                self.env.consume(
                    TokenType.ASSIGN,
                    "Expected '=' after Cm declaration",
                )
                value = self._parse_expression()
                return AssignmentNode(
                    var_type=type_tok.type, name=name_tok.value,
                    value=value, line=type_tok.line,
                )

            # Cx complex number syntax
            if type_tok.type == TokenType.CX:
                if self.env.check(TokenType.COLON):
                    self.env.advance()
                elif self.env.check(TokenType.ASSIGN):
                    self.env.advance()
                else:
                    value = LiteralNode(value=0, kind=TokenType.INTEGER, line=type_tok.line)
                    return CxNode(name=name_tok.value, value=value, line=type_tok.line)
                value = self._parse_expression()
                return CxNode(name=name_tok.value, value=value, line=type_tok.line)

            # Standard single assignment
            if self.env.check(TokenType.COLON):
                self.env.advance()
                value = self._parse_expression()
            elif self.env.check(TokenType.ASSIGN):
                self.env.advance()
                value = self._parse_expression()
            else:
                if type_tok.type == TokenType.I:
                    value = LiteralNode(value=0, kind=TokenType.INTEGER, line=type_tok.line)
                elif type_tok.type == TokenType.F:
                    value = LiteralNode(value=0.0, kind=TokenType.FLOAT, line=type_tok.line)
                elif type_tok.type == TokenType.D:
                    value = LiteralNode(value=0.0, kind=TokenType.FLOAT, line=type_tok.line)
                elif type_tok.type == TokenType.TF:
                    value = LiteralNode(value=False, kind=TokenType.BOOLEAN_LITERAL, line=type_tok.line)
                elif type_tok.type == TokenType.YN_KW:
                    value = LiteralNode(value=False, kind=TokenType.BOOLEAN_LITERAL, line=type_tok.line)
                elif type_tok.type == TokenType.CM:
                    value = LiteralNode(value=0, kind=TokenType.INTEGER, line=type_tok.line)
                else:
                    value = LiteralNode(value=None, kind=TokenType.STRING, line=type_tok.line)
            return AssignmentNode(
                var_type=type_tok.type, name=name_tok.value,
                value=value, line=type_tok.line,
            )

        # Dot-prefixed form: S.prop or I.prop.entity
        parts: list[str] = []
        while self.env.check(TokenType.DOT):
            self.env.advance()
            parts.append(
                self.env.consume(TokenType.IDENTIFIER, "Expected identifier after '.'").value,
            )
        self.env.consume(TokenType.COLON, "Expected ':' after property path")
        value = self._parse_expression()

        if len(parts) == 1:
            return AssignmentNode(
                var_type=type_tok.type, name=parts[0],
                value=value, line=type_tok.line,
            )
        if len(parts) > 2:
            from parser.parser import ParseError
            raise ParseError(
                "Relation assignment requires exactly one property and one entity "
                "(e.g. 'I.age.Jey : value')",
                type_tok,
            )
        return RelationAssignmentNode(
            var_type=type_tok.type,
            property_name=parts[0],
            entity_name=parts[1],
            value=value,
            line=type_tok.line,
        )

    # ── Delegate helpers ────────────────────────────────────────────────

    def _parse_expression(self) -> Node:
        if self._expression_parser is not None:
            return self._expression_parser.parse_expression()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())

    def _parse_primary_chain(self) -> Node:
        if self._expression_parser is not None:
            return self._expression_parser._parse_primary_chain()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())

    def _parse_binary_rhs(self, left: Node) -> Node:
        if self._expression_parser is not None:
            return self._expression_parser._parse_binary_rhs(left)
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())
