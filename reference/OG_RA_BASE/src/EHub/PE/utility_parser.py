"""UtilityParser — Shared parsing utilities and helper methods.

Provides reusable parsing helpers for use by all specialized parsers,
including body parsing with terminator propagation.
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class UtilityParser:
    """Shared parsing utilities.

    Provides ``parse_body()`` which handles terminator propagation
    for nested block constructs.
    """

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry
        self._stmt_parser: Optional[callable] = None

    def parse_body(
        self,
        terminators: frozenset[TokenType] = frozenset(),
    ) -> list:
        """Parse a sequence of statements until a terminator or EOF.

        Propagates structural terminators from enclosing constructs
        so that nested blocks correctly respect parent boundaries.

        Parameters
        ----------
        terminators : token types that should stop this body.

        Returns
        -------
        list of Node
        """
        from parser.ra_ast import Node

        body: list[Node] = []
        active = self.env.body_terminators | terminators
        saved = self.env.body_terminators
        self.env.body_terminators = active
        saved_depth = self.env.nested_block_depth
        self.env.nested_block_depth += 1
        try:
            while not self.env.check(TokenType.EOF):
                if self.env.check(*active):
                    break
                if self._stmt_parser is not None:
                    stmt = self._stmt_parser.parse_stmt()
                else:
                    stmt = None
                if stmt is not None:
                    body.append(stmt)
        finally:
            self.env.nested_block_depth = saved_depth
            self.env.body_terminators = saved
        return body
