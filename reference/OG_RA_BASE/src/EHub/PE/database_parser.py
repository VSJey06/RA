"""DatabaseParser — Db and Sdb block parsing.

Handles database blocks and operations:
  - Db blocks:  Db:, Db.Personal:, Db.save, Db.load, Db.update
  - Sdb blocks: Sdb.Employee:, Sdb.save, Sdb.load, Sdb.update
  - Sdb qualified API: at, row, col, table, move, width, height, display, info
"""

from __future__ import annotations

from typing import Optional, Any

from lexer.tokens import Token, TokenType
from parser.ra_ast import (
    DbBreakNode,
    DbLoadNode,
    DbNode,
    DbNextNode,
    DbSaveNode,
    DbUpdateNode,
    Node,
    SdbHeightNode,
    SdbLoadNode,
    SdbMoveNode,
    SdbNode,
    SdbSaveNode,
    SdbUpdateNode,
    SdbWidthNode,
    SdbCursorSetNode,
    PropertyAccessNode,
    IdentifierNode,
    MethodCallNode,
    LiteralNode,
)
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class DatabaseParser:
    """Parses database (Db) and structured database (Sdb) blocks."""

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry
        self._parse_body_func: Optional[callable] = None
        self._expression_parser: Optional[callable] = None

    # ── Sdb block ───────────────────────────────────────────────────────

    def parse_sdb(self) -> Node:
        """Parse an Sdb block or save/load/update command."""
        tok = self.env.consume(
            TokenType.SDB,
            "Expected 'Sdb' to open a structured database block",
        )
        self.env.consume(TokenType.DOT, "Expected '.' after 'Sdb'")
        name_tok = self.env.consume(
            TokenType.IDENTIFIER,
            "Expected table name after 'Sdb.'",
        )
        table_name = name_tok.value

        if self.env.check(TokenType.DOT):
            self.env.advance()
            cmd_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected 'save', 'load', 'update', 'at', 'row', 'col', "
                "'table', 'move', 'width', 'height', 'wrap', 'merge', "
                "or 'group' after '.'",
            )
            cmd = cmd_tok.value
            if cmd == "save":
                return SdbSaveNode(table_name=table_name, line=tok.line)
            if cmd == "load":
                return SdbLoadNode(table_name=table_name, line=tok.line)
            if cmd == "update":
                return SdbUpdateNode(table_name=table_name, line=tok.line)
            # Qualified API forms
            return self._parse_sdb_qualified_chain(
                table_name=table_name, cmd=cmd, tok=tok,
            )

        self.env.consume(TokenType.COLON, "Expected ':' after table name")

        body = self._parse_body(terminators=frozenset({TokenType.SDB_CLOSE}))
        has_explicit_close = self.env.check(TokenType.SDB_CLOSE)
        if has_explicit_close:
            self.env.advance()

        return SdbNode(
            name=table_name, body=body, line=tok.line,
            auto_close=not has_explicit_close,
        )

    def _parse_sdb_qualified_chain(
        self, table_name: str, cmd: str, tok: Token,
    ) -> Node:
        """Continue parsing a qualified Sdb API property chain.

        Called after Sdb.<TableName>.<cmd> has been consumed.
        Handles the remaining dot-property/coordinate/colon tokens
        and produces the same AST node that the unqualified form
        (TableName.<cmd>...) would produce.

        Supported commands:
            at, row, col, table, move, width, height,
            wrap, merge, group, display, info
        """
        prop_parts: list[str] = [cmd]

        while self.env.check(TokenType.DOT):
            self.env.advance()  # consume '.'

            # Coordinate syntax: .INTEGER,INTEGER  (at.R,C, wrap.R,C, etc.)
            if (self.env.current().type in (TokenType.INTEGER, TokenType.IDENTIFIER)
                    and self.env.pos + 1 < len(self.env.tokens)
                    and self.env.tokens[self.env.pos + 1].type == TokenType.COMMA):
                x_tok = self.env.advance()
                self.env.consume(TokenType.COMMA, "Expected ',' after X coordinate")
                y_tok = self.env.advance()
                coord = f"{x_tok.value},{y_tok.value}"
                prop_parts.append(coord)

                if self.env.check(TokenType.COLON):
                    self.env.advance()

                    # move.R,C : DR,DC  ->  SdbMoveNode
                    if cmd == "move":
                        dest_parts = self._parse_coordinate_pair()
                        if dest_parts is not None:
                            dest_row, dest_col = dest_parts
                            src_parts = coord.split(",")
                            if len(src_parts) == 2:
                                return SdbMoveNode(
                                    table_name=table_name,
                                    src_row=int(src_parts[0]),
                                    src_col=int(src_parts[1]),
                                    dest_row=dest_row,
                                    dest_col=dest_col,
                                    line=tok.line,
                                )

                    # at.R,C : value  ->  MethodCallNode (cursor set)
                    arg = self._parse_expression()
                    return MethodCallNode(
                        method=f"{table_name}.{'.'.join(prop_parts)}",
                        argument=arg, line=tok.line,
                    )
                continue

            sub_prop = self._parse_dot_property()
            prop_parts.append(sub_prop)

            if self.env.check(TokenType.COLON):
                self.env.advance()
                method_name = f"{table_name}.{'.'.join(prop_parts)}"

                # width.col : size  ->  SdbWidthNode
                if cmd == "width":
                    col_str = sub_prop
                    try:
                        col = int(col_str)
                    except ValueError:
                        col = col_str
                    size_tok = self.env.consume(
                        TokenType.INTEGER,
                        "Expected integer width after ':'",
                    )
                    return SdbWidthNode(
                        table_name=table_name,
                        column=col,
                        size=size_tok.value,
                        line=tok.line,
                    )

                # height.row : size  ->  SdbHeightNode
                if cmd == "height":
                    row = int(prop_parts[1])
                    size_tok = self.env.consume(
                        TokenType.INTEGER,
                        "Expected integer height after ':'",
                    )
                    return SdbHeightNode(
                        table_name=table_name,
                        row=row,
                        size=size_tok.value,
                        line=tok.line,
                    )

                # ── Multi-assignment cursor set: ident, ident = expr, expr
                #    Also handles single-variable: ident = expr ──
                if (method_name.endswith(".set")
                        and self.env.check(TokenType.IDENTIFIER)
                        and self.env.pos + 1 < len(self.env.tokens)
                        and self.env.tokens[self.env.pos + 1].type
                            in (TokenType.COMMA, TokenType.ASSIGN)):
                    return self._parse_sdb_cursor_set_body(
                        method_name=method_name,
                        name_tok=tok,
                    )

                # All other forms: at.row.N:val, col.Name:val, table.display, etc.
                arg = self._parse_expression()
                return MethodCallNode(
                    method=method_name,
                    argument=arg, line=tok.line,
                )

        # No colon: table.display, table.info, wrap.R,C, merge.row.N:M, group.R,C:DR,DC
        if cmd == "table" and len(prop_parts) >= 2:
            sub = prop_parts[1]
            if sub in ("display", "info"):
                return PropertyAccessNode(
                    object=IdentifierNode(name=table_name, line=tok.line),
                    property=f"table.{sub}",
                    line=tok.line,
                )

        if cmd in ("display", "info"):
            return PropertyAccessNode(
                object=IdentifierNode(name=table_name, line=tok.line),
                property=f"table.{cmd}",
                line=tok.line,
            )

        # Fallback: build a generic MethodCallNode from the chain
        method_name = f"{table_name}.{'.'.join(prop_parts)}"
        return MethodCallNode(
            method=method_name,
            argument=LiteralNode(value=None, kind=TokenType.STRING, line=tok.line),
            line=tok.line,
        )

    def _parse_dot_property(self) -> str:
        """Parse property name after '.' and return it as a string.

        Delegates to the expression parser's dot property parser.
        """
        if self._expression_parser is not None:
            return self._expression_parser._parse_dot_property()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())



    def _parse_sdb_cursor_set_body(
        self, method_name: str, name_tok: Token,
    ) -> SdbCursorSetNode:
        """Parse the multi-assignment cursor set body after .set:.

        Expects the token stream to be positioned just after the : of
        <method>.set: and produces an SdbCursorSetNode with the
        parsed names and values.

        Handles both single-variable and multi-variable forms:
            ident = expr
            ident, ident = expr, expr
        """
        names = [self.env.advance().value]
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
                name_tok,
            )
        return SdbCursorSetNode(
            method=method_name,
            names=names,
            values=values,
            line=name_tok.line,
        )

    # ── Db block ────────────────────────────────────────────────────────

    def parse_db(self, at_tok: Optional[Token] = None) -> Node:
        """Parse a Db block or save/load/update command."""
        if at_tok is not None:
            tok = at_tok
            self.env.consume(TokenType.DB, "Expected 'Db' after '@'")
        else:
            tok = self.env.consume(
                TokenType.DB, "Expected 'Db' to open a database block",
            )

        if self.env.check(TokenType.DOT):
            self.env.advance()
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected database name after 'Db.'",
            )
            db_name = name_tok.value
        else:
            db_name = "db"

        if self.env.check(TokenType.DOT):
            self.env.advance()
            cmd_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected 'save', 'load', or 'update' after '.'",
            )
            if cmd_tok.value == "save":
                return DbSaveNode(database_name=db_name, line=tok.line)
            if cmd_tok.value == "load":
                return DbLoadNode(database_name=db_name, line=tok.line)
            if cmd_tok.value == "update":
                return DbUpdateNode(database_name=db_name, line=tok.line)
            from parser.parser import ParseError
            raise ParseError(
                f"Expected 'save', 'load', or 'update' after '.', "
                f"got '{cmd_tok.value}'",
                cmd_tok,
            )

        self.env.consume(TokenType.COLON, "Expected ':' after database name")

        body = self._parse_body(terminators=frozenset({TokenType.DB_CLOSE}))
        has_explicit_close = self.env.check(TokenType.DB_CLOSE)
        if has_explicit_close:
            self.env.advance()

        return DbNode(
            name=db_name, body=body, line=tok.line,
            auto_close=not has_explicit_close,
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    def _parse_body(self, terminators=frozenset()) -> list[Node]:
        if self._parse_body_func is not None:
            return self._parse_body_func(terminators=terminators)
        return []

    def _parse_expression(self) -> Node:
        if self._expression_parser is not None:
            return self._expression_parser.parse_expression()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())

    def _parse_coordinate_pair(self) -> Optional[tuple[int, int]]:
        if self.env.check(TokenType.INTEGER):
            first = self.env.advance()
            if self.env.check(TokenType.COMMA):
                self.env.advance()
                if self.env.check(TokenType.INTEGER):
                    second = self.env.advance()
                    return (int(first.value), int(second.value))
        return None
