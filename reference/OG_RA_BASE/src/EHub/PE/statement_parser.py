"""StatementParser — Statement-level parsing including dispatch, control flow,
Check/Key blocks, pH/fF blocks, and dot-prefixed statements.
"""

from __future__ import annotations

from typing import Optional

from lexer.tokens import Token, TokenType


class NestedBlockSyntaxError(Exception):
    """Raised when a nested-block keyword (if/elif/else) appears outside
    an executable block body.
    """
    pass
from parser.ra_ast import (
    AbsNode,
    AssignmentNode,
    BreakNode,
    CaseNode,
    CharMethodNode,
    CharNode,
    CheckNode,
    ClassNode,
    CompoundAssignmentNode,
    ContinueNode,
    DbBreakNode,
    DbNextNode,

    FlowFragmentNode,
    FunctionBlockNode,
    FunctionFlowNode,
    InputBlockNode,
    InputNode,
    IsNode,
    LenNode,
    MethodCallNode,
    MethodInvokeNode,
    MethodNode,
    Node,
    ObjectDeclarationNode,
    OOPNode,
    PFNode,
    ParagraphNode,
    PrintBlockNode,
    PriorityHandlerNode,
    ProgramHandlerNode,
    PropertyAccessNode,
    ReturnNode,
    RoundNode,
    RunBlockNode,
    StringTransformNode,
    SwitchNode,
    TypeInfoNode,
    UnaryBitwiseNode,
    UnaryLogicalNode,
    IdentifierNode,
    BooleanNode,
    SdbHeightNode,
    SdbMoveNode,
    SdbWidthNode,
    SdbCursorSetNode,
    PrintNode,
    MultiPrintNode,
    PrintParagraphNode,
    FormattedPrintNode,
)
from EHub.PE.parser_environment import ParserEnvironment
from EHub.PE.parser_registry import ParserRegistry


class StatementParser:
    """Parses all statement-level constructs.

    Handles the main statement dispatch, dot-prefixed statements,
    control flow (if/for/while), Check/Key blocks, pH/fF blocks,
    print/return statements, unary operations, and identifier statements.
    """

    def __init__(self, env: ParserEnvironment, registry: ParserRegistry) -> None:
        self.env = env
        self.reg = registry
        # Delegates set by the facade
        self._expression_parser: Optional[callable] = None
        self._declaration_parser: Optional[callable] = None
        self._database_parser: Optional[callable] = None
        self._utility_parser: Optional[callable] = None
        self._parse_body_func: Optional[callable] = None
        # Mixin callbacks — set by the facade for OOP/constructor/encapsulation dispatch
        self._parse_at_stmt_callback: Optional[callable] = None
        self._parse_object_callback: Optional[callable] = None
        self._parse_method_callback: Optional[callable] = None
        self._parse_constructor_callback: Optional[callable] = None
        self._parse_encapsulation_callback: Optional[callable] = None
        # Block Family callback — set by the facade for Print/Ip block dispatch
        self._parse_block_callback: Optional[callable] = None
        # Decision Family callback — set by the facade for If/What/if/elif/else dispatch
        self._parse_decision_callback: Optional[callable] = None
        # Loop Family callback — set by the facade for For/While/for/while dispatch
        self._parse_loop_callback: Optional[callable] = None
        # Function Family callback — set by the facade for .fun:/fun:/function call dispatch
        self._parse_function_callback: Optional[callable] = None
        # RC3-08J: CF (Control Flow) gating flag — set when CF is loaded
        self._cf_active: bool = False

    # ── Top-level statement dispatch ────────────────────────────────────

    def parse_stmt(self) -> Optional[Node]:
        """Dispatch to the appropriate parse method based on current token."""
        tok = self.env.current()
        tt = tok.type

        # ── Mixin-handled tokens — delegated via callbacks ──────────────
        if tt == TokenType.AT and self._parse_at_stmt_callback is not None:
            return self._parse_at_stmt_callback()
        if tt == TokenType.OBJ and self._parse_object_callback is not None:
            return self._parse_object_callback()
        if tt == TokenType.M and self._parse_method_callback is not None:
            return self._parse_method_callback()
        if tt == TokenType.CON and self._parse_constructor_callback is not None:
            return self._parse_constructor_callback()
        if tt == TokenType.EN and self._parse_encapsulation_callback is not None:
            return self._parse_encapsulation_callback()

        if tt == TokenType.DB:
            if self._database_parser is not None:
                return self._database_parser.parse_db()
        if tt == TokenType.SDB:
            if self._database_parser is not None:
                return self._database_parser.parse_sdb()

        if tt == TokenType.P:
            return self._parse_print()
        if tt == TokenType.PL:
            return self._parse_print_line()
        if tt == TokenType.PF_PRINT:
            return self._parse_print_formatted()
        if tt == TokenType.PR:
            return self._parse_print_paragraph()
        if tt == TokenType.R:
            return self._parse_return()
        if tt == TokenType.NOT_KW:
            return self._parse_unary_logical_stmt()
        if tt == TokenType.BNOT_KW:
            return self._parse_unary_bitwise_stmt()

        if tt in (TokenType.S, TokenType.I, TokenType.L, TokenType.TF,
                   TokenType.YN_KW,
                   TokenType.F, TokenType.D,
                   TokenType.C, TokenType.CX,
                   TokenType.CS, TokenType.CA, TokenType.CM):
            if self._declaration_parser is not None:
                return self._declaration_parser.parse_typed_assignment()

        if tt == TokenType.IDENTIFIER:
            return self._parse_identifier_stmt()
        if tt == TokenType.BANG:
            return self._parse_bang_stmt()
        if tt == TokenType.BITWISE_NOT:
            return self._parse_unary_bitwise_not_stmt()
        if tt == TokenType.QUESTION:
            if self._parse_loop_callback is not None:
                return self._parse_loop_callback.parse_question_stmt()
            from parser.parser import ParseError
            raise ParseError(
                "Loop parser not configured for '?'",
                self.env.current(),
            )
        if tt == TokenType.DB_NEXT:
            self.env.advance()
            return DbNextNode(line=tok.line)
        if tt == TokenType.DB_BREAK:
            self.env.advance()
            return DbBreakNode(line=tok.line)
        if tt == TokenType.DB_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'db.close' outside of a Db block. "
                "Did you forget 'Db:' ?",
                tok,
            )
        if tt == TokenType.SDB_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'sdb.close' outside of an Sdb block. "
                "Did you forget 'Sdb.Name:' ?",
                tok,
            )
        if tt == TokenType.METHOD_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected '/.close' outside of a method body. "
                "Did you forget 'M.name:' ?",
                tok,
            )
        if tt == TokenType.COMMA:
            self.env.advance()
            return None
        if tt == TokenType.OOP:
            self.env.advance()
            return OOPNode(line=tok.line)
        if tt == TokenType.PF:
            self.env.advance()
            return PFNode(line=tok.line)
        if tt == TokenType.PH:
            return self._parse_ph()
        if tt == TokenType.FF:
            return self._parse_ff()
        if tt == TokenType.CF:
            self.env.advance()
            self._cf_active = True
            return PFNode(line=tok.line)
        if tt == TokenType.FUN_BLOCK:
            return self._parse_fun_block(tok)
        if tt == TokenType.CON:
            return self._parse_constructor()
        if tt == TokenType.EN:
            return self._parse_encapsulation()
        if tt == TokenType.DOT:
            return self._parse_dot_stmt()
        # ── Nested block keywords ──────────────────────────────────────
        # ── Block Family (Print / Ip) — dispatched via callback ────────
        if tt == TokenType.PRINT_BLOCK:
            if self._parse_block_callback is not None:
                return self._parse_block_callback.parse_print_block()
            from parser.parser import ParseError
            raise ParseError(
                "Block parser not configured for 'Print'",
                self.env.current(),
            )
        if tt == TokenType.IP_BLOCK:
            if self._parse_block_callback is not None:
                return self._parse_block_callback.parse_input_block()
            from parser.parser import ParseError
            raise ParseError(
                "Block parser not configured for 'Ip'",
                self.env.current(),
            )

        # ── Nested block keywords ──────────────────────────────────────
        if tt == TokenType.FUN_NESTED:
            if self._parse_function_callback is not None:
                return self._parse_function_callback.parse_nested_fun()
            from parser.parser import ParseError
            raise ParseError(
                "Function parser not configured for nested 'fun'",
                self.env.current(),
            )
        if tt == TokenType.PRINT_NESTED:
            return self._parse_nested_print()
        if tt == TokenType.FOR_NESTED:
            if self._parse_loop_callback is not None:
                return self._parse_loop_callback.parse_nested_for()
            from parser.parser import ParseError
            raise ParseError(
                "Loop parser not configured for nested 'for'",
                self.env.current(),
            )
        if tt == TokenType.WHILE_NESTED:
            if self._parse_loop_callback is not None:
                return self._parse_loop_callback.parse_nested_while()
            from parser.parser import ParseError
            raise ParseError(
                "Loop parser not configured for nested 'while'",
                self.env.current(),
            )
        if tt == TokenType.RUN_NESTED:
            return self._parse_nested_run()
        if tt == TokenType.IF_NESTED:
            if self._parse_decision_callback is not None:
                return self._parse_decision_callback.parse_nested_if()
            from parser.parser import ParseError
            raise ParseError(
                "Decision parser not configured for nested 'if'",
                self.env.current(),
            )
        if tt == TokenType.ELIF_NESTED:
            raise NestedBlockSyntaxError(
                "'elif' is only valid after 'if' inside an executable block. "
                "Use '!!ElseIf' at the top level instead."
            )
        if tt == TokenType.ELSE_NESTED:
            raise NestedBlockSyntaxError(
                "'else' is only valid after 'if' inside an executable block. "
                "Use '!Else' at the top level instead."
            )

        if tt == TokenType.INPUT_SPEC:
            return self._parse_input_stmt()
        if tt == TokenType.RUN_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'r.close' outside of a .run: block. "
                "Did you forget '.run:' ?",
                tok,
            )
        if tt == TokenType.FUN_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'f.close' outside of a .fun: or fF: block. "
                "Did you forget '.fun:' or 'fF:' ?",
                tok,
            )
        if tt == TokenType.CON_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'con.close' outside of a constructor block. "
                "Did you forget 'Con:' ?",
                tok,
            )
        if tt == TokenType.CHECK:
            return self._parse_check()
        if tt == TokenType.KEY:
            return self._parse_key()
        if tt == TokenType.EN_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'en.close' outside of an encapsulation block. "
                "Did you forget 'En:' ?",
                tok,
            )
        if tt == TokenType.AT_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected '@.close' outside of a class block. "
                "Did you forget '@Cls.Name:' ?",
                tok,
            )
        if tt == TokenType.CHECK_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'Check.close' outside of a Check block. "
                "Did you forget 'Check:' ?",
                tok,
            )
        if tt == TokenType.KEY_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'Key.close' outside of a Key block. "
                "Did you forget 'Key.value:' ?",
                tok,
            )
        if tt == TokenType.PH_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'pH.close' outside of a pH block. "
                "Did you forget 'pH:' ?",
                tok,
            )
        if tt == TokenType.IP_CLOSE:
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected 'ip.close' outside of an Ip block. "
                "Did you forget 'Ip:' ?",
                tok,
            )

        if tt == TokenType.CARET:
            # Standalone ^^ highlight operator (two consecutive CARET tokens)
            nxt = self.env.peek(1)
            if nxt is not None and nxt.type == TokenType.CARET:
                self.env.advance()  # consume first ^
                self.env.advance()  # consume second ^
                expr = self._parse_expression()
                from parser.ra_ast import HighlightNode
                return HighlightNode(value=expr, line=tok.line)
            from parser.parser import ParseError
            raise ParseError(
                "Unexpected single '^'. Use ^^ for highlight operator.",
                tok,
            )

        if tt == TokenType.HASH:
            nxt = self.env.peek(1)
            if nxt is not None and nxt.type == TokenType.DOT:
                # Orphan '#.' without a containing ? Do / ? Which / ? What block
                # This catches ``#.while:i<5`` at top level.
                nxt2 = self.env.peek(2)
                context = ""
                if nxt2 is not None:
                    if nxt2.type == TokenType.WHILE_NESTED:
                        context = "while"
                    elif nxt2.type == TokenType.IDENTIFIER:
                        context = nxt2.value
                if context:
                    raise NestedBlockSyntaxError(
                        f"'{context}' is only valid inside an executable block. "
                        f"Use a containing '? Do:', '? Which:', or '? What:' structure "
                        f"with '#.{context}:' at the top level."
                    )
                raise NestedBlockSyntaxError(
                    "'#.' is only valid inside a '? Do:', '? Which:', or '? What:' block. "
                    "Use a containing structure at the top level instead."
                )

        from parser.parser import ParseError
        raise ParseError(f"Unexpected token '{tok.value}'", tok)

    # ── OOP statement delegates ─────────────────────────────────────────

    def _parse_at_stmt(self) -> Node:
        """Parse @-prefixed statement (class definition or Db)."""
        from compiler.oop.class_parser import ClassParserMixin
        # Note: at_stmt is handled by the parser facade via mixin
        from parser.parser import ParseError
        raise ParseError(
            "@ statement requires ClassParserMixin integration", self.env.current(),
        )

    def _parse_object(self) -> Node:
        """Parse object declaration via mixin."""
        from parser.parser import ParseError
        raise ParseError(
            "Object statement requires ObjectParserMixin integration",
            self.env.current(),
        )

    def _parse_method(self) -> Node:
        """Parse method declaration via mixin."""
        from parser.parser import ParseError
        raise ParseError(
            "Method statement requires MethodParserMixin integration",
            self.env.current(),
        )

    def _parse_constructor(self) -> Node:
        """Parse constructor via mixin."""
        from parser.parser import ParseError
        raise ParseError(
            "Constructor requires ConstructorParserMixin integration",
            self.env.current(),
        )

    def _parse_encapsulation(self) -> Node:
        """Parse encapsulation via mixin."""
        from parser.parser import ParseError
        raise ParseError(
            "Encapsulation requires EncapsulationParserMixin integration",
            self.env.current(),
        )

    # ── Dot-prefixed statements (.run:, .fun.name:, .type:, calls, etc.) ────

    def _parse_dot_stmt(self) -> Node:
        """Parse a statement that starts with '.'."""
        dot_tok = self.env.advance()
        if self.env.check(TokenType.IDENTIFIER, TokenType.FUN_NESTED) and self.env.current().value == "fun":
            self.env.advance()
            if self._parse_function_callback is not None:
                return self._parse_function_callback.parse_dot_fun(dot_tok)
            from parser.parser import ParseError
            raise ParseError(
                "Function parser not configured for '.fun'",
                dot_tok,
            )

        if (self.env.check(TokenType.IDENTIFIER, TokenType.RUN_NESTED)
                and self.env.current().value in ("run", "type", "len",
                                                  "upper", "lower", "trim", "reverse",
                                                  "char", "first", "last",
                                                  "count", "find", "replace",
                                                  "contains", "starts", "ends",
                                                  "split", "repeat",
                                                  "abs", "round", "is")
                and self.env.pos + 1 < len(self.env.tokens)
                and self.env.tokens[self.env.pos + 1].type == TokenType.COLON):
            kind = self.env.advance().value
            self.env.advance()
            if kind == "run":
                return self._parse_run_block(dot_tok)
            if kind == "fun":
                if self._parse_function_callback is not None:
                    return self._parse_function_callback.parse_function_block(dot_tok)
                from parser.parser import ParseError
                raise ParseError(
                    "Function parser not configured for '.fun'",
                    dot_tok,
                )
            if kind == "abs":
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.abs:'",
                )
                return AbsNode(name=name_tok.value, line=dot_tok.line)
            if kind == "round":
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.round:'",
                )
                return RoundNode(name=name_tok.value, line=dot_tok.line)
            if kind == "is":
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.is:'",
                )
                return IsNode(name=name_tok.value, line=dot_tok.line)
            if kind == "type":
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.type:'",
                )
                return TypeInfoNode(name=name_tok.value, line=dot_tok.line)
            if kind == "len":
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.len:'",
                )
                return LenNode(name=name_tok.value, line=dot_tok.line)
            if kind in ("upper", "lower", "trim", "reverse"):
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    f"Expected variable name after '.{kind}:'",
                )
                return StringTransformNode(
                    name=name_tok.value, method=kind, line=dot_tok.line,
                )
            if kind == "char":
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.char:'",
                )
                self.env.consume(
                    TokenType.COMMA,
                    "Expected ',' after variable name in '.char:variable,index'",
                )
                idx_tok = self.env.consume(
                    TokenType.INTEGER,
                    "Expected integer index after '.char:variable,'",
                )
                return CharNode(
                    name=name_tok.value,
                    index=idx_tok.value,
                    line=dot_tok.line,
                )
            if kind in ("first", "last"):
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    f"Expected variable name after '.{kind}:'",
                )
                return CharMethodNode(
                    name=name_tok.value, method=kind, line=dot_tok.line,
                )
            if kind in ("count", "find", "contains", "starts", "ends"):
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    f"Expected variable name after '.{kind}:'",
                )
                self.env.consume(
                    TokenType.COMMA,
                    f"Expected ',' after variable name in '.{kind}:variable,\"c\"'",
                )
                char_tok = self.env.consume(
                    TokenType.STRING,
                    f"Expected string argument after '.{kind}:variable,'",
                )
                return CharMethodNode(
                    name=name_tok.value, method=kind,
                    arg=char_tok.value, line=dot_tok.line,
                )
            if kind in ("split", "repeat"):
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    f"Expected variable name after '.{kind}:'",
                )
                self.env.consume(
                    TokenType.COMMA,
                    f"Expected ',' after variable name in '.{kind}:variable,arg'",
                )
                arg_tok = self.env.advance()
                return CharMethodNode(
                    name=name_tok.value, method=kind,
                    arg=arg_tok.value, line=dot_tok.line,
                )
            if kind == "replace":
                name_tok = self.env.consume(
                    TokenType.IDENTIFIER,
                    "Expected variable name after '.replace:'",
                )
                self.env.consume(
                    TokenType.COMMA,
                    "Expected ',' after variable name in '.replace:variable,\"a\",\"b\"'",
                )
                old_tok = self.env.consume(
                    TokenType.STRING,
                    "Expected old string after '.replace:variable,'",
                )
                self.env.consume(
                    TokenType.COMMA,
                    "Expected ',' after old string in '.replace:variable,\"a\",\"b\"'",
                )
                new_tok = self.env.consume(
                    TokenType.STRING,
                    "Expected new string after '.replace:variable,\"a\",'",
                )
                return CharMethodNode(
                    name=name_tok.value, method="replace",
                    arg=old_tok.value, arg2=new_tok.value,
                    line=dot_tok.line,
                )

        if (self.env.check(TokenType.IDENTIFIER)
                and self.env.current().value == "in"):
            self.env.advance()
            node_obj = InputNode(input_type="generic", line=dot_tok.line)
            if self.env.check(TokenType.COLON):
                self.env.advance()
                node_obj.prompt = self._parse_expression()
            return node_obj

        if (self.env.check(TokenType.IDENTIFIER)
                and self.env.current().value == "take"):
            self.env.advance()
            node_obj = InputNode(input_type="take", line=dot_tok.line)
            if self.env.check(TokenType.COLON):
                self.env.advance()
                node_obj.prompt = self._parse_expression()
            return node_obj

        if self.env.check(TokenType.IDENTIFIER):
            if self._parse_function_callback is not None:
                return self._parse_function_callback.parse_function_call(dot_tok)
            from parser.parser import ParseError
            raise ParseError(
                "Function parser not configured for function call",
                dot_tok,
            )

        from parser.parser import ParseError
        raise ParseError(
            "Expected '.run:', '.fun.<name>:', '.type:variable', '.len:variable', "
            "'.upper:variable', '.lower:variable', '.trim:variable', '.reverse:variable', "
            "'.char:variable,index', '.first:variable', '.last:variable', "
            "'.count:variable,\"c\"', '.find:variable,\"c\"', "
            "'.replace:variable,\"a\",\"b\"', '"
            ".contains:variable,\"c\"', '.starts:variable,\"c\"', '.ends:variable,\"c\"', "
            ".split:variable,sep', '.repeat:variable,count', "
            "'.in', or '.<function>'",
            dot_tok,
        )



    def _parse_input_stmt(self) -> Node:
        """Parse a statement-level input spec."""
        tok = self.env.advance()
        if tok.value == "par.in":
            if self.env.check(TokenType.COLON):
                self.env.advance()
                content = self._parse_expression()
                return ParagraphNode(content=content, line=tok.line)
            return InputNode(input_type="paragraph", line=tok.line)
        node_obj = self._make_input_node(tok.value, tok.line)
        if self.env.check(TokenType.COLON):
            self.env.advance()
            node_obj.prompt = self._parse_expression()
        return node_obj

    def _make_input_node(self, input_spec: str, line: int) -> InputNode:
        """Create an InputNode from an input spec string."""
        mapping = {
            "I.in": "integer",
            "F.in": "float",
            "D.in": "double",
            "L.in": "long",
            "Byte.in": "byte",
            "S.in": "string",
            "Char.in": "char_single",
            "c.in": "char",
            "par.in": "paragraph",
            "line.in": "line",
            "Buf.in": "buffer",
            "Bui.in": "builder",
        }
        return InputNode(input_type=mapping.get(input_spec, "generic"), line=line)

    # ── Run/Fun blocks ──────────────────────────────────────────────────

    def _parse_run_block(self, dot_tok: Token) -> RunBlockNode:
        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.RUN_CLOSE}))
        else:
            body = []
        has_close = self.env.check(TokenType.RUN_CLOSE)
        if has_close:
            self.env.advance()
        return RunBlockNode(body=body, line=dot_tok.line, auto_close=not has_close)

    # ── Check block ─────────────────────────────────────────────────────

    def _parse_check(self) -> CheckNode:
        tok = self.env.consume(TokenType.CHECK, "Expected 'Check'")
        self.env.consume(TokenType.COLON, "Expected ':' after 'Check'")

        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({
                TokenType.VALID, TokenType.INVALID, TokenType.CHECK_CLOSE,
            }))
        else:
            body = []

        valid_body: list[Node] = []
        if self.env.check(TokenType.VALID):
            self.env.advance()
            self.env.consume(TokenType.COLON, "Expected ':' after 'Valid'")
            if self._parse_body_func is not None:
                valid_body = self._parse_body_func(terminators=frozenset({
                    TokenType.INVALID, TokenType.CHECK_CLOSE,
                }))

        invalid_body: list[Node] = []
        if self.env.check(TokenType.INVALID):
            self.env.advance()
            self.env.consume(TokenType.COLON, "Expected ':' after 'Invalid'")
            if self._parse_body_func is not None:
                invalid_body = self._parse_body_func(terminators=frozenset({
                    TokenType.CHECK_CLOSE,
                }))

        has_close = self.env.check(TokenType.CHECK_CLOSE)
        if has_close:
            self.env.advance()

        return CheckNode(
            body=body, valid_body=valid_body, invalid_body=invalid_body,
            line=tok.line, auto_close=not has_close,
        )

    # ── Key / case / def (switch) block ─────────────────────────────────

    def _parse_key(self) -> SwitchNode:
        key_tok = self.env.consume(TokenType.KEY, "Expected 'Key'")
        self.env.consume(TokenType.DOT, "Expected '.' after 'Key'")
        value = self._parse_switch_expression()
        self.env.consume(TokenType.COLON, "Expected ':' after Key value")

        cases: list[CaseNode] = []
        default_body: list[Node] = []

        while not self.env.check(TokenType.KEY_CLOSE, TokenType.EOF):
            if self.env.check(TokenType.IDENTIFIER) and self.env.current().value == "def":
                nxt = self.env.pos + 1
                if nxt < len(self.env.tokens) and self.env.tokens[nxt].type == TokenType.COLON:
                    self.env.advance()
                    self.env.advance()
                    if self._parse_body_func is not None:
                        default_body = self._parse_body_func(terminators=frozenset({
                            TokenType.KEY_CLOSE,
                        }))
                    break

            if self.env.check(TokenType.IDENTIFIER) and self.env.current().value == "c":
                nxt = self.env.pos + 1
                if nxt < len(self.env.tokens) and self.env.tokens[nxt].type == TokenType.DOT:
                    c_tok = self.env.advance()
                    self.env.advance()
                    condition = self._parse_switch_expression()
                    self.env.consume(
                        TokenType.COLON, "Expected ':' after case condition",
                    )
                    case_body = self._parse_key_case_body()
                    cases.append(CaseNode(
                        condition=condition, body=case_body, line=c_tok.line,
                    ))
                    continue

            from parser.parser import ParseError
            raise ParseError(
                "Expected case ('c.condition:') or default ('def:') in Key block",
                self.env.current(),
            )

        has_close = self.env.check(TokenType.KEY_CLOSE)
        if has_close:
            self.env.advance()

        return SwitchNode(
            value=value, cases=cases, default_body=default_body,
            line=key_tok.line, auto_close=not has_close,
        )

    def _parse_key_case_body(self) -> list[Node]:
        body: list[Node] = []
        while not self.env.check(TokenType.EOF):
            if self.env.check(TokenType.KEY_CLOSE):
                break
            if self.env.check(TokenType.IDENTIFIER):
                val = self.env.current().value
                nxt = self.env.pos + 1
                if nxt < len(self.env.tokens):
                    nxt_tt = self.env.tokens[nxt].type
                    if val == "c" and nxt_tt == TokenType.DOT:
                        break
                    if val == "def" and nxt_tt == TokenType.COLON:
                        break
            stmt = self.parse_stmt()
            if stmt is not None:
                body.append(stmt)
        return body

    def _parse_switch_expression(self) -> Node:
        left = self._parse_primary_chain()
        left = self._parse_binary_rhs(left)
        if self.env.check(TokenType.BOOLEAN_TF):
            self.env.advance()
            left = BooleanNode(expr=left, line=left.line)
        return left

    # ── pH (Program Handler) block ──────────────────────────────────────

    def _parse_ph(self) -> ProgramHandlerNode:
        tok = self.env.consume(TokenType.PH, "Expected 'pH'")
        self.env.consume(TokenType.COLON, "Expected ':' after 'pH'")

        body: list[Node] = []
        while not self.env.check(TokenType.PH_CLOSE, TokenType.EOF):
            item = self._parse_ph_item()
            if item is not None:
                body.append(item)

        has_close = self.env.check(TokenType.PH_CLOSE)
        if has_close:
            self.env.advance()

        return ProgramHandlerNode(body=body, line=tok.line, auto_close=not has_close)

    def _parse_ph_item(self) -> Optional[Node]:
        if (self.env.check(TokenType.DOT)
                and self.env.pos + 2 < len(self.env.tokens)
                and self.env.tokens[self.env.pos + 1].type == TokenType.IDENTIFIER
                and self.env.tokens[self.env.pos + 1].value in ("run", "fun")
                and self.env.tokens[self.env.pos + 2].type == TokenType.COLON):
            from parser.parser import ParseError
            raise ParseError(
                ".run and .fun are not allowed inside pH blocks",
                self.env.current(),
            )

        tok = self.env.current()
        tt = tok.type

        if tt == TokenType.AT:
            self.env.advance()
            self.env.consume(TokenType.CLS, "Expected 'Cls' after '@' in pH block")
            self.env.consume(TokenType.DOT, "Expected '.' after 'Cls' in pH block")
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected class name after 'Cls.' in pH block",
            )
            return ClassNode(name=name_tok.value, line=tok.line, members=[])

        if tt == TokenType.OBJ:
            self.env.advance()
            self.env.consume(TokenType.DOT, "Expected '.' after 'Obj' in pH block")
            cls_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected class name after 'Obj.' in pH block",
            )
            self.env.consume(TokenType.DOT, "Expected '.' after class name in pH block")
            var_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected variable name in pH block",
            )
            return ObjectDeclarationNode(
                object_name=var_tok.value, class_name=cls_tok.value, line=tok.line,
            )

        if tt == TokenType.M:
            self.env.advance()
            self.env.consume(TokenType.DOT, "Expected '.' after 'M' in pH block")
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected method name after 'M.' in pH block",
            )
            return MethodNode(name=name_tok.value, line=tok.line, body=[])

        from parser.parser import ParseError
        raise ParseError("Expected '@Cls.', 'Obj.', or 'M.' in pH block", tok)

    # ── fF (Function Flow) block ────────────────────────────────────────

    def _parse_ff(self) -> FunctionFlowNode:
        tok = self.env.consume(TokenType.FF, "Expected 'fF'")

        target: Optional[str] = None
        if self.env.check(TokenType.DOT):
            self.env.advance()
            parts: list[str] = []
            while not self.env.check(TokenType.COLON, TokenType.EOF):
                t = self.env.current()
                if t.type == TokenType.AT:
                    parts.append("@")
                    self.env.advance()
                elif t.type == TokenType.DOT:
                    parts.append(".")
                    self.env.advance()
                else:
                    parts.append(str(t.value))
                    self.env.advance()
            target = "".join(parts)

        self.env.consume(TokenType.COLON, "Expected ':' after 'fF'")

        body: list[Node] = []
        saved_in_ff = self.env.in_ff_flow
        self.env.in_ff_flow = True
        try:
            while not self.env.check(TokenType.FUN_CLOSE, TokenType.EOF):
                item = self._parse_ff_item()
                if item is not None:
                    body.append(item)
        finally:
            self.env.in_ff_flow = saved_in_ff

        has_close = self.env.check(TokenType.FUN_CLOSE)
        if has_close:
            self.env.advance()

        return FunctionFlowNode(
            body=body, line=tok.line, auto_close=not has_close, target=target,
        )

    def _parse_ff_item(self) -> Optional[Node]:
        if (self.env.check(TokenType.DOT)
                and self.env.pos + 2 < len(self.env.tokens)
                and self.env.tokens[self.env.pos + 1].type == TokenType.IDENTIFIER
                and self.env.tokens[self.env.pos + 1].value in ("run", "fun")
                and self.env.tokens[self.env.pos + 2].type == TokenType.COLON):
            from parser.parser import ParseError
            raise ParseError(
                ".run and .fun are not allowed inside fF blocks",
                self.env.current(),
            )

        if self.env.check(TokenType.CHECK):
            return self._parse_check()
        if self.env.check(TokenType.KEY):
            return self._parse_key()

        obj_tok = self.env.consume(
            TokenType.IDENTIFIER, "Expected object name in fF block",
        )
        self.env.consume(TokenType.DOT, "Expected '.' after object name in fF block")
        method_tok = self.env.consume(
            TokenType.IDENTIFIER, "Expected method name after '.' in fF block",
        )
        return MethodInvokeNode(
            method_name=method_tok.value,
            object_name=obj_tok.value,
            line=obj_tok.line,
        )

    # ── RC3-08J: Fun: / Fun.Name: / f.close block ────────────────────────

    def _parse_fun_block(self, fun_tok: Token) -> FunctionBlockNode:
        """Parse a Fun: / Fun.Name: / f.close block.

        Syntax::

            Fun:
                body...
            f.close

            Fun.add:
                body...
            f.close

        Reuses existing FunctionBlockNode and FunctionRegistry.
        """
        # Advance past the FUN_BLOCK token consumed by parse_stmt
        self.env.advance()
        name: Optional[str] = None
        if self.env.check(TokenType.DOT):
            self.env.advance()
            name_tok = self.env.consume(
                TokenType.IDENTIFIER,
                "Expected function name after 'Fun.'",
            )
            name = name_tok.value
        self.env.consume(
            TokenType.COLON,
            "Expected ':' after Fun block declaration",
        )
        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.FUN_CLOSE}))
        else:
            body = []
        has_close = self.env.check(TokenType.FUN_CLOSE)
        if has_close:
            self.env.advance()
        return FunctionBlockNode(
            name=name, params=[], body=body,
            line=fun_tok.line, auto_close=not has_close,
        )

    # ── RC3-08J: CF-specific pH.Name: (Priority Handler) ───────────────

    def _parse_cf_ph(self, ph_tok: Token) -> PriorityHandlerNode:
        """Parse a CF Priority Handler block: pH.<Name>: ... pH.close

        Syntax::

            pH.user:
                fF.call
                fF.enter
            pH.close

        pH stores ordered fF references — NOT executable code.
        """
        self.env.consume(TokenType.DOT, "Expected '.' after 'pH' in CF context")
        name_tok = self.env.consume(
            TokenType.IDENTIFIER,
            "Expected pH block name after 'pH.'",
        )
        self.env.consume(
            TokenType.COLON,
            "Expected ':' after pH block name",
        )

        # Parse flow references (fF.Name on each line)
        saved_depth = self.env.nested_block_depth
        self.env.nested_block_depth += 1
        references: list[str] = []
        try:
            while not self.env.check(TokenType.PH_CLOSE, TokenType.EOF):
                # Each line should contain fF.Name
                if self.env.check(TokenType.FF):
                    self.env.advance()
                    self.env.consume(
                        TokenType.DOT,
                        "Expected '.' after 'fF' in pH block",
                    )
                    ref_tok = self.env.consume(
                        TokenType.IDENTIFIER,
                        "Expected fF block name after 'fF.' in pH block",
                    )
                    references.append(ref_tok.value)
                else:
                    break
        finally:
            self.env.nested_block_depth = saved_depth

        has_close = self.env.check(TokenType.PH_CLOSE)
        if has_close:
            self.env.advance()

        return PriorityHandlerNode(
            name=name_tok.value, flow_references=references,
            line=ph_tok.line, auto_close=not has_close,
        )

    # ── RC3-08J: CF-specific fF.Name: (Flow Fragment) ─────────────────

    def _parse_cf_ff(self, ff_tok: Token) -> FlowFragmentNode:
        """Parse a CF Flow Fragment block: fF.<Name>: ... fF.close

        Syntax::

            fF.call:
                ken.User
            fF.close

        fF stores executable instructions.
        """
        self.env.consume(TokenType.DOT, "Expected '.' after 'fF' in CF context")
        name_tok = self.env.consume(
            TokenType.IDENTIFIER,
            "Expected fF block name after 'fF.'",
        )
        self.env.consume(
            TokenType.COLON,
            "Expected ':' after fF block name",
        )

        # Parse body until fF.close (which tokenizes as FF DOT IDENTIFIER("close"))
        body: list[Node] = []
        try:
            while not self.env.check(TokenType.EOF):
                # Check for fF.close: FF DOT IDENTIFIER("close")
                if self.env.check(TokenType.FF):
                    nxt1 = self.env.peek(1)
                    nxt2 = self.env.peek(2)
                    if (nxt1 is not None and nxt1.type == TokenType.DOT
                            and nxt2 is not None and nxt2.type == TokenType.IDENTIFIER
                            and nxt2.value == "close"):
                        break
                stmt = self.parse_stmt()
                if stmt is not None:
                    body.append(stmt)
                else:
                    break
        finally:
            pass

        # Consume fF.close
        has_close = False
        if self.env.check(TokenType.FF):
            nxt1 = self.env.peek(1)
            nxt2 = self.env.peek(2)
            if (nxt1 is not None and nxt1.type == TokenType.DOT
                    and nxt2 is not None and nxt2.type == TokenType.IDENTIFIER
                    and nxt2.value == "close"):
                self.env.advance()  # fF
                self.env.advance()  # .
                self.env.advance()  # close
                has_close = True

        return FlowFragmentNode(
            name=name_tok.value, body=body,
            line=ff_tok.line, auto_close=not has_close,
        )

    # ── RC3-08J: CF-aware pH/fF dispatch ───────────────────────────────

    def _try_parse_cf_block(self) -> Optional[Node]:
        """Try to parse a CF-specific block (pH.<Name>: or fF.<Name>:).

        Returns None if the current token is not a CF block start.
        Only works when _cf_active is True.
        """
        if not self._cf_active:
            return None
        if self.env.check(TokenType.PH):
            tok = self.env.current()
            nxt1 = self.env.peek(1)
            if nxt1 is not None and nxt1.type == TokenType.DOT:
                self.env.advance()  # consume PH
                return self._parse_cf_ph(tok)
            return None
        if self.env.check(TokenType.FF):
            tok = self.env.current()
            nxt1 = self.env.peek(1)
            if nxt1 is not None and nxt1.type == TokenType.DOT:
                nxt2 = self.env.peek(2)
                if nxt2 is not None and nxt2.type == TokenType.IDENTIFIER and nxt2.value != "close":
                    self.env.advance()  # consume FF
                    return self._parse_cf_ff(tok)
            return None
        return None

    # ── RC3-08J: CF-aware Which.Name: parsing hook ─────────────────────

    def _parse_cf_which_body(
        self,
        which_name: str,
        which_node: 'WhichControlNode',
    ) -> None:
        """Parse CF syntax inside a named Which block.

        Populates the WhichControlNode with priority_handlers and
        flow_fragments.
        """
        saved_depth = self.env.nested_block_depth
        self.env.nested_block_depth += 1
        try:
            while not self.env.check(TokenType.EOF):
                # Check for closing #. (HASH followed by DOT)
                if self.env.check(TokenType.HASH):
                    nxt = self.env.peek(1)
                    if nxt is not None and nxt.type == TokenType.DOT:
                        break
                    self.env.advance()
                    continue

                # Try pH.Name: block
                if self.env.check(TokenType.PH) and self._cf_active:
                    tok = self.env.current()
                    nxt1 = self.env.peek(1)
                    if nxt1 is not None and nxt1.type == TokenType.DOT:
                        self.env.advance()  # consume PH
                        ph_node = self._parse_cf_ph(tok)
                        which_node.priority_handlers.append(ph_node)
                        continue

                # Try fF.Name: block
                if self.env.check(TokenType.FF) and self._cf_active:
                    tok = self.env.current()
                    nxt1 = self.env.peek(1)
                    if nxt1 is not None and nxt1.type == TokenType.DOT:
                        nxt2 = self.env.peek(2)
                        if nxt2 is not None and nxt2.type == TokenType.IDENTIFIER and nxt2.value != "close":
                            self.env.advance()  # consume FF
                            ff_node = self._parse_cf_ff(tok)
                            which_node.flow_fragments.append(ff_node)
                            continue

                break
        finally:
            self.env.nested_block_depth = saved_depth

        # Parse closure argument: #.expression or #.name=expression
        if self.env.check(TokenType.HASH):
            self.env.advance()  # consume #
            if self.env.check(TokenType.DOT):
                self.env.advance()  # consume .
                # Check for #.name=expression assignment form
                if (self.env.check(TokenType.IDENTIFIER)
                        and self.env.pos + 1 < len(self.env.tokens)
                        and self.env.tokens[self.env.pos + 1].type == TokenType.ASSIGN):
                    # Assignment form: #.name=expression
                    name_tok = self.env.advance()  # consume name
                    self.env.advance()  # consume =
                    which_node.dispatch_var_name = name_tok.value
                    which_node.closure_argument = self._parse_expression()
                else:
                    # Simple expression form: #.expression
                    which_node.closure_argument = self._parse_expression()
                # Consume trailing HASH if present
                if self.env.check(TokenType.HASH):
                    self.env.advance()

    # ── Print statements ────────────────────────────────────────────────

    def _parse_print(self) -> Node:
        tok = self.env.consume(TokenType.P, "Expected 'p'")
        if (
            self.env.check(TokenType.DOT)
            and self.env.current().column == tok.end_column + 1
        ):
            self.env.advance()
        values = self._parse_print_values()
        if len(values) == 1:
            return PrintNode(value=values[0], line=tok.line, no_newline=False)
        return MultiPrintNode(values=values, line=tok.line, no_newline=False)

    def _parse_print_line(self) -> Node:
        tok = self.env.consume(TokenType.PL, "Expected 'pl'")
        if (
            self.env.check(TokenType.DOT)
            and self.env.current().column == tok.end_column + 1
        ):
            self.env.advance()
        values = self._parse_print_values()
        if len(values) == 1:
            return PrintNode(value=values[0], line=tok.line, no_newline=True)
        return MultiPrintNode(values=values, line=tok.line, no_newline=True)

    def _parse_print_values(self) -> list[Node]:
        values = [self._parse_expression()]
        while self.env.check(TokenType.COMMA):
            self.env.advance()
            values.append(self._parse_expression())
        return values

    def _parse_print_paragraph(self) -> PrintParagraphNode:
        tok = self.env.consume(TokenType.PR, "Expected 'pr'")
        if (
            self.env.check(TokenType.DOT)
            and self.env.current().column == tok.end_column + 1
        ):
            self.env.advance()
        value = self._parse_expression()
        return PrintParagraphNode(value=value, line=tok.line)

    def _parse_print_formatted(self) -> FormattedPrintNode:
        """Parse a formatted print statement:

            pf "format string", arg1, arg2, ...

        Uses Python-style ``%%`` formatting internally.
        """
        tok = self.env.consume(TokenType.PF_PRINT, "Expected 'pf'")
        if (
            self.env.check(TokenType.DOT)
            and self.env.current().column == tok.end_column + 1
        ):
            self.env.advance()
        fmt = self._parse_expression()
        args: list[Node] = []
        while self.env.check(TokenType.COMMA):
            self.env.advance()
            args.append(self._parse_expression())
        return FormattedPrintNode(format_string=fmt, args=args, line=tok.line)

    # ── Return statement ────────────────────────────────────────────────

    def _parse_return(self) -> ReturnNode:
        r_tok = self.env.consume(TokenType.R, "Expected 'R' for return statement")
        if (
            self.env.check(TokenType.DOT)
            and self.env.current().column == r_tok.end_column + 1
        ):
            self.env.advance()
        value = self._parse_expression()
        return ReturnNode(value=value, line=r_tok.line)

    # ── Unary logical statement ─────────────────────────────────────────

    def _parse_unary_logical_stmt(self) -> Node:
        tok = self.env.advance()
        expr = self._parse_expression()
        return UnaryLogicalNode(operator="not", expr=expr, line=tok.line)

    def _parse_unary_bitwise_stmt(self) -> Node:
        tok = self.env.advance()
        expr = self._parse_expression()
        return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)

    def _parse_unary_bitwise_not_stmt(self) -> Node:
        tok = self.env.advance()
        expr = self._parse_expression()
        return UnaryBitwiseNode(operator="bnot", expr=expr, line=tok.line)

    # ── Bang statement (!) ──────────────────────────────────────────────

    def _parse_bang_stmt(self) -> Node:
        bang_tok = self.env.advance()
        if self.env.check(TokenType.IDENTIFIER):
            val = self.env.current().value
            if val == "If":
                if self._parse_decision_callback is not None:
                    return self._parse_decision_callback.parse_if(bang_tok)
                from parser.parser import ParseError
                raise ParseError(
                    "Decision parser not configured for '!If'",
                    self.env.current(),
                )
            if val == "What":
                if self._parse_decision_callback is not None:
                    return self._parse_decision_callback.parse_what(bang_tok)
                from parser.parser import ParseError
                raise ParseError(
                    "Decision parser not configured for '!What'",
                    self.env.current(),
                )
        expr = self._parse_expression()
        return UnaryLogicalNode(operator="not", expr=expr, line=bang_tok.line)

    # ── If / elseif / else ──────────────────────────────────────────────

    # ── Line-column map for indentation validation ───────────────────────

    def _build_line_column_map(self) -> dict[int, int]:
        """Build a mapping from source line numbers to their leading column.

        Returns a dict ``{line_number: column}`` where *column* is the
        column of the first token on that line.  This is used by
        ``_validate_indentation()`` to check that block statements are
        properly indented.
        """
        line_map: dict[int, int] = {}
        for tok in self.env.tokens:
            if tok.line not in line_map:
                line_map[tok.line] = tok.column
        return line_map

    def _validate_indentation(
        self,
        body: list[Node],
        parent_col: int,
        line_map: dict[int, int],
        opening_line: int,
    ) -> None:
        """Validate that all statements in *body* are properly indented.

        Rules (matching Python-like indentation):

        1. Every statement inside the block must have a column greater
           than the parent column (i.e. indented by at least 1 space).
        2. All sibling statements must share the same leading column.
        3. Statements on the same line as the opening construct
           (e.g. ``!If.a==10: p "inline"``) are allowed.
        """
        if not body:
            return
        columns: list[int] = []
        for node in body:
            col = line_map.get(node.line, 0)
            if node.line == opening_line:
                continue  # same-line statements are allowed
            if col <= parent_col:
                from parser.parser import ParseError
                raise ParseError(
                    f"Block statement must be indented by one level "
                    f"(> {parent_col} spaces). Found column {col}.",
                    self.env.current(),
                )
            columns.append(col)
        if not columns:
            return
        first_col = columns[0]
        for col in columns[1:]:
            if col != first_col:
                from parser.parser import ParseError
                raise ParseError(
                    f"Incorrect indentation. "
                    f"Expected {first_col}-space indentation inside the block, "
                    f"but found column {col}.",
                    self.env.current(),
                )

    # ── Parse helpers using the indent foot-print ────────────────────────





    def _parse_nested_print(self) -> RunBlockNode:
        """Parse a nested print section inside an executable block.

        Syntax:

            print.label:
                p "message 1"
                p "message 2"
            #

        The label is optional. Body contains `p` statements.
        Reuses RunBlockNode as a generic body container.
        Raises NestedBlockSyntaxError if not inside a block.
        """
        if self.env.nested_block_depth == 0:
            raise NestedBlockSyntaxError(
                "'print' is only valid inside an executable block."
            )

        tok = self.env.advance()  # consume 'print'

        # Optional label: print.label:
        if self.env.check(TokenType.DOT):
            self.env.advance()
            self.env.consume(
                TokenType.IDENTIFIER,
                "Expected label name after 'print.'",
            )

        self.env.consume(TokenType.COLON, "Expected ':' after 'print'")

        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
        else:
            body = []

        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return RunBlockNode(body=body, line=tok.line, auto_close=not has_close)

    def _parse_nested_run(self) -> RunBlockNode:
        """Parse a nested run block inside an executable block.

        Syntax:

            run:
                body
            #

        Reuses RunBlockNode (same AST as primary .run).
        Raises NestedBlockSyntaxError if not inside a block.
        """
        if self.env.nested_block_depth == 0:
            raise NestedBlockSyntaxError(
                "'run' is only valid inside an executable block. "
                "Use '.run' at the top level instead."
            )

        run_tok = self.env.advance()  # consume 'run'
        self.env.consume(TokenType.COLON, "Expected ':' after 'run'")

        if self._parse_body_func is not None:
            body = self._parse_body_func(terminators=frozenset({TokenType.HASH}))
        else:
            body = []

        has_close = self.env.check(TokenType.HASH)
        if has_close:
            self.env.advance()

        return RunBlockNode(body=body, line=run_tok.line, auto_close=not has_close)

    # ── Identifier statement ────────────────────────────────────────────

    def _parse_identifier_stmt(self) -> Node:
        """Parse a statement that starts with an identifier."""
        name_tok = self.env.advance()
        if self.env.check(TokenType.COLON):
            self.env.advance()
            if (self.env.check(TokenType.OBJ)
                    and self.env.pos + 2 < len(self.env.tokens)
                    and self.env.tokens[self.env.pos + 1].type == TokenType.DOT
                    and self.env.tokens[self.env.pos + 2].type == TokenType.IDENTIFIER):
                self.env.advance()
                self.env.advance()
                cls_tok = self.env.advance()
                return ObjectDeclarationNode(
                    object_name=name_tok.value,
                    class_name=cls_tok.value,
                    line=name_tok.line,
                )
            value = self._parse_expression()
            return MethodCallNode(method=name_tok.value, argument=value, line=name_tok.line)

        compound_op = self._check_compound_assign()
        if compound_op is not None:
            value = self._parse_expression()
            return CompoundAssignmentNode(
                name=name_tok.value, operator=compound_op,
                value=value, line=name_tok.line,
            )

        if self.env.check(TokenType.ASSIGN):
            self.env.advance()
            value = self._parse_expression()
            return AssignmentNode(
                var_type=None, name=name_tok.value,
                value=value, line=name_tok.line,
            )

        if self.env.check(TokenType.DOT):
            return self._parse_identifier_property_chain(name_tok)

        left: Node = IdentifierNode(name=name_tok.value, line=name_tok.line)
        return self._parse_binary_rhs(left)

    def _parse_identifier_property_chain(self, name_tok: Token) -> Node:
        """Parse property chain after an identifier: name.prop.subprop."""
        dot_tok = self.env.advance()
        cur = self.env.current()
        if cur.type not in (TokenType.IDENTIFIER, TokenType.FUN_NESTED,
                            TokenType.RUN_NESTED, TokenType.PRINT_NESTED,
                            TokenType.FOR_NESTED, TokenType.WHILE_NESTED):
            from parser.parser import ParseError
            raise ParseError("Expected identifier after '.'", cur)
        next_tok = self.env.advance()
        if next_tok.value == "run":
            return MethodInvokeNode(
                method_name=name_tok.value, line=name_tok.line,
            )
        if self.env.check(TokenType.COLON):
            self.env.advance()
            arg = self._parse_expression()
            # RC3-09B: Multi-argument colon syntax (e.g., items.insert:1,2)
            # Check for COMMA after the first argument to handle multi-arg
            if self.env.check(TokenType.COMMA):
                self.env.advance()
                arg2 = self._parse_expression()
                # Wrap both args in a list so the interpreter can unpack them
                from parser.ra_ast import ListNode
                arg = ListNode(items=[arg, arg2], line=name_tok.line)
            return MethodCallNode(
                method=f"{name_tok.value}.{next_tok.value}",
                argument=arg, line=name_tok.line,
            )

        prop_parts: list[str] = [next_tok.value]
        while self.env.check(TokenType.DOT):
            self.env.advance()
            if (self.env.current().type in (TokenType.INTEGER, TokenType.IDENTIFIER)
                    and self.env.pos + 1 < len(self.env.tokens)
                    and self.env.tokens[self.env.pos + 1].type == TokenType.COMMA):
                x_tok = self.env.advance()
                self.env.consume(TokenType.COMMA, "Expected ',' after coordinate X")
                y_tok = self.env.advance()
                coord = f"{x_tok.value},{y_tok.value}"
                prop_parts.append(coord)
                if self.env.check(TokenType.COLON):
                    self.env.advance()
                    sdb_result = self._try_parse_sdb_operation(
                        name_tok, prop_parts,
                    )
                    if sdb_result is not None:
                        return sdb_result
                    arg = self._parse_expression()
                    return MethodCallNode(
                        method=f"{name_tok.value}.{'.'.join(prop_parts)}",
                        argument=arg, line=name_tok.line,
                    )
                continue

            sub_prop = self._parse_dot_property()
            if sub_prop == "run" and len(prop_parts) == 1:
                return MethodInvokeNode(
                    method_name=prop_parts[0],
                    object_name=name_tok.value,
                    line=name_tok.line,
                )
            prop_parts.append(sub_prop)
            if self.env.check(TokenType.COLON):
                self.env.advance()
                method_name = f"{name_tok.value}.{'.'.join(prop_parts)}"
                sdb_result = self._try_parse_sdb_operation(
                    name_tok, prop_parts,
                )
                if sdb_result is not None:
                    return sdb_result
                if (method_name.endswith(".set")
                        and self.env.check(TokenType.IDENTIFIER)
                        and self.env.pos + 1 < len(self.env.tokens)
                        and self.env.tokens[self.env.pos + 1].type
                            in (TokenType.COMMA, TokenType.ASSIGN)):
                    names = [self.env.advance().value]
                    while self.env.check(TokenType.COMMA):
                        self.env.advance()
                        ntok = self.env.consume(
                            TokenType.IDENTIFIER,
                            "Expected identifier after ','",
                        )
                        names.append(ntok.value)
                    self.env.consume(
                        TokenType.ASSIGN, "Expected '=' after variable list",
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
                        method=method_name, names=names, values=values,
                        line=name_tok.line,
                    )
                arg = self._parse_expression()
                return MethodCallNode(
                    method=method_name, argument=arg, line=name_tok.line,
                )

        if self.env.in_ff_flow and len(prop_parts) == 1:
            return MethodInvokeNode(
                method_name=prop_parts[0],
                object_name=name_tok.value,
                line=name_tok.line,
            )
        if (name_tok.value[:1].isupper()
                and prop_parts
                and prop_parts[0][:1].isupper()
                and len(prop_parts) > 1):
            from parser.parser import ParseError
            # ── Detect @Cls.Name missing '@' — produce RA2001 ──
            if name_tok.value == "Cls":
                raise ParseError(
                    "RA2001: Missing '@' before class declaration. "
                    f"Expected: @{name_tok.value}.{prop_parts[0]}:, "
                    "not Cls.Name: (class declarations require '@' prefix)",
                    dot_tok,
                )
            raise ParseError(
                "Expected '.run' after method name", dot_tok,
            )
        return PropertyAccessNode(
            object=IdentifierNode(name=name_tok.value, line=name_tok.line),
            property=".".join(prop_parts), line=dot_tok.line,
        )

    def _try_parse_sdb_operation(
        self, name_tok: Token, prop_parts: list[str],
    ) -> Optional[Node]:
        """Try to parse an Sdb operation (move/width/height) from the property chain."""
        if (not name_tok.value[:1].isupper()
                or len(prop_parts) < 2
                or prop_parts[0] not in ("move", "width", "height")):
            return None

        table_name = name_tok.value
        prop0 = prop_parts[0]
        if prop0 == "move":
            dest_parts = self._parse_coordinate_pair()
            if dest_parts is not None:
                dest_row, dest_col = dest_parts
                src_parts = prop_parts[1].split(",")
                if len(src_parts) == 2:
                    return SdbMoveNode(
                        table_name=table_name,
                        src_row=int(src_parts[0]),
                        src_col=int(src_parts[1]),
                        dest_row=dest_row, dest_col=dest_col,
                        line=name_tok.line,
                    )
        elif prop0 == "width":
            col_str = prop_parts[1]
            try:
                col = int(col_str)
            except ValueError:
                col = col_str
            size_tok = self.env.consume(
                TokenType.INTEGER, "Expected integer width after ':'",
            )
            return SdbWidthNode(
                table_name=table_name, column=col, size=size_tok.value,
                line=name_tok.line,
            )
        elif prop0 == "height":
            row = int(prop_parts[1])
            size_tok = self.env.consume(
                TokenType.INTEGER, "Expected integer height after ':'",
            )
            return SdbHeightNode(
                table_name=table_name, row=row, size=size_tok.value,
                line=name_tok.line,
            )
        return None

    def _parse_coordinate_pair(self) -> Optional[tuple[int, int]]:
        if self.env.check(TokenType.INTEGER):
            first = self.env.advance()
            if self.env.check(TokenType.COMMA):
                self.env.advance()
                if self.env.check(TokenType.INTEGER):
                    second = self.env.advance()
                    return (int(first.value), int(second.value))
        return None

    def _check_compound_assign(self) -> Optional[str]:
        tt = self.env.current().type
        if tt in self.reg.COMPOUND_ASSIGN_OPS:
            self.env.advance()
            return self.reg.COMPOUND_ASSIGN_OPS[tt]
        nxt = self.env.pos + 1
        if nxt < len(self.env.tokens):
            nxt_tt = self.env.tokens[nxt].type
            key = (tt, nxt_tt)
            if key in self.reg.COMPOUND_3CHAR:
                self.env.advance()
                self.env.advance()
                return self.reg.COMPOUND_3CHAR[key]
        return None

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

    def _parse_dot_property(self) -> str:
        if self._expression_parser is not None:
            return self._expression_parser._parse_dot_property()
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())

    def _parse_binary_rhs(self, left: Node) -> Node:
        if self._expression_parser is not None:
            return self._expression_parser._parse_binary_rhs(left)
        from parser.parser import ParseError
        raise ParseError("Expression parser not configured", self.env.current())
