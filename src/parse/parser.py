from ast import literal_eval
from re import S
from typing import Optional, Tuple

from common.errors import InternalError

from parse import nodes
from parse.errors import SyntaxError
from parse.tokens import Token, TokenKind


class AstRoot:
    def __init__(self):
        self.top_level_nodes: list[nodes.TopLevelNode] = []

    def __str__(self):
        lines: list[str] = []
        for node in self.top_level_nodes:
            if isinstance(node, nodes.StmtNode):
                if isinstance(node, nodes.ExprNode):
                    lines.append(f"{node};")
                else:
                    lines.append(str(node))
            else:
                lines.append(str(node))
        return "\n".join(lines)

    __repr__ = __str__


class Parser:
    def __init__(self):
        self._tokens: list[Token] = []
        self._pos = 0
        self._loop_depth = 0
        self._in_fn_decl = False

    # Program = { Stmt | FnDefinition }
    def parse(self, tokens: list[Token]):
        self._tokens = tokens
        self._reset()

        ast = AstRoot()
        while not self._is_done():
            if self._lookahead(TokenKind.FN):
                ast.top_level_nodes.append(self._parse_fn_definition())
            else:
                ast.top_level_nodes.append(self._parse_stmt())
        return ast

    def _reset(self):
        self._pos = 0
        self._loop_depth = 0
        self._in_fn_decl = False

    # FnDefinition = "fn" identifier "(" [ ParamList ] ")" Block
    # ParamList    = { identifier "," } identifier
    def _parse_fn_definition(self):
        tok = self._expect(TokenKind.FN)
        name = self._expect(TokenKind.IDENTIFIER).val
        self._expect(TokenKind.LEFT_PAREN)

        param_names: list[str] = []
        while not self._accept(TokenKind.RIGHT_PAREN):
            if param_names:
                self._expect(TokenKind.COMMA)
            param_names.append(self._expect(TokenKind.IDENTIFIER).val)

        self._in_fn_decl = True
        body_block = self._parse_block()
        self._in_fn_decl = False

        return nodes.FnDefinition(tok.line, tok.col, name, param_names, body_block)

    # Block = "{" { Stmt } "}"
    def _parse_block(self):
        tok = self._expect(TokenKind.LEFT_BRACE)
        stmts: list[nodes.StmtNode] = []
        while not self._accept(TokenKind.RIGHT_BRACE):
            stmts.append(self._parse_stmt())
        return nodes.BlockStmt(tok.line, tok.col, stmts)

    # Stmt = { ";" } (ForStmt |
    #   IfStmt |
    #   VarDeclStmt |
    #   TryStmt |
    #   WhileLoopStmt |
    #   BreakStmt |
    #   ContinueStmt |
    #   ExprInStmtContext);
    def _parse_stmt(
        self,
    ) -> nodes.StmtNode:
        while self._accept(TokenKind.SEMICOLON):
            pass

        tok = self._peek()
        if tok.kind == TokenKind.FOR:
            return self._parse_for_loop()
        elif tok.kind == TokenKind.IF:
            return self._parse_if_stmt()
        elif tok.kind == TokenKind.LET:
            return self._parse_var_decl_stmt()
        elif tok.kind == TokenKind.TRY:
            return self._parse_try_stmt()
        elif tok.kind == TokenKind.WHILE:
            return self._parse_while_loop_stmt()
        elif tok.kind == TokenKind.BREAK:
            return self._parse_break_stmt()
        elif tok.kind == TokenKind.CONTINUE:
            return self._parse_continue_stmt()
        elif tok.kind == TokenKind.RETURN:
            return self._parse_return_stmt()
        else:
            return self._parse_expr_in_stmt_context()

    # ForLoop = ForLoopStmt | IteratorBasedForLoopStmt
    def _parse_for_loop(self):
        self._expect(TokenKind.FOR)
        tok = self._expect(TokenKind.LEFT_PAREN)
        mark = self._pos
        if (
            self._accept(TokenKind.LET)
            and self._accept(TokenKind.IDENTIFIER)
            and self._accept(TokenKind.IN)
        ):
            self._pos = mark
            return self._parse_iterator_based_for_loop_stmt(tok)
        else:
            self._pos = mark
            return self._parse_for_loop_stmt(tok)

    # ForLoopStmt = "for" "(" InitStmt CondExpr PostExpr ")" Block
    def _parse_for_loop_stmt(self, tok: Token):
        # for keyword and the left paren are already scanned
        init_stmt = self._parse_for_loop_initializer()
        cond_expr = self._parse_for_loop_cond_expr()
        post_expr = self._parse_for_loop_post_expr()
        self._expect(TokenKind.RIGHT_PAREN)

        self._loop_depth += 1
        loop_body = self._parse_block()
        self._loop_depth -= 1

        # Lower for loop statements into while loops, roughly like below:
        # {
        #   init_stmt;
        #   while (cond_expr) {
        #     loop_body;
        #     post_expr;
        #   }
        # }
        #
        # This transformation does not suffice if there is a continue statement in the loop body --
        # for loops always execute the post expr after an iteration regardless of whether it was
        # short circuited with a continue statement, but the rewritten version does not do this. Consider
        #
        # for (let i = 1; le(i, 5); i = add(i, 1)) { continue; }
        #
        # This would be naively rewritten to:
        # {
        #   let i = 1;
        #   while (le(i, 5)) {
        #     continue;
        #     i = add(i, 1);
        #   }
        # }
        #
        # which clearly has different semantics.
        #
        # We remediate this by additionally rewriting all continue statements within the loop body into
        # {
        #   post_expr;
        #   continue;
        # }
        #
        # Also note that this  causes the scope of variables defined in init_stmt and loop_body to
        # be different, but that"s a reasonable compromise here -- it"s a toy language, after all!
        rewritten_loop_body = loop_body
        if post_expr:
            # add trailing continue statement so post expr is added at the end
            if rewritten_loop_body.stmts and not isinstance(
                rewritten_loop_body.stmts[-1], nodes.ContinueStmt
            ):
                rewritten_loop_body.stmts.append(nodes.ContinueStmt(-1, -1))
            rewritten_loop_body = self._rewrite_continue_stmts(
                rewritten_loop_body, post_expr
            )
        stmts: list[nodes.StmtNode] = []
        if init_stmt:
            stmts.append(init_stmt)

        stmts.append(
            nodes.WhileLoopStmt(tok.line, tok.col, cond_expr, rewritten_loop_body)
        )
        return nodes.BlockStmt(tok.line, tok.col, stmts)

    # InitStmt = VarDeclStmt | [ Expr ] ";"
    def _parse_for_loop_initializer(self):
        if self._accept(TokenKind.SEMICOLON):
            return None
        elif self._lookahead(TokenKind.LET):
            return self._parse_var_decl_stmt()
        else:
            return self._parse_expr_in_stmt_context()

    # CondExpr = [ Expr ] ";"
    def _parse_for_loop_cond_expr(self):
        if self._lookahead(TokenKind.SEMICOLON):
            tok = self._next()
            return nodes.BoolLitExpr(tok.line, tok.col, True)
        else:
            return self._parse_expr_in_stmt_context()

    # PostExpr = [ Expr ]
    def _parse_for_loop_post_expr(self):
        if self._lookahead(TokenKind.RIGHT_PAREN):
            return None
        else:
            return self._parse_expr()

    # IteratorBasedForLoopStmt = "for" "(" "let" identifier "in" Expr ")" Block
    def _parse_iterator_based_for_loop_stmt(self, tok: Token):
        # for keyword and the left paren are already scanned
        self._expect(TokenKind.LET)
        iterator_var_binding_name = self._expect(TokenKind.IDENTIFIER).val
        self._expect(TokenKind.IN)
        expr = self._parse_expr()
        self._expect(TokenKind.RIGHT_PAREN)

        self._loop_depth += 1
        body_block = self._parse_block()
        self._loop_depth -= 1

        return nodes.IteratorBasedForLoopStmt(
            tok.line, tok.col, iterator_var_binding_name, expr, body_block
        )

    def _rewrite_continue_stmts(
        self, stmt: nodes.StmtNode, post_expr: nodes.ExprNode
    ) -> nodes.StmtNode:
        if isinstance(stmt, nodes.BlockStmt):
            transformed = [
                self._rewrite_continue_stmts(stmt, post_expr) for stmt in stmt.stmts
            ]
            return nodes.BlockStmt(stmt.line, stmt.col, transformed)
        elif isinstance(stmt, nodes.IfStmt):
            if_branch = self._rewrite_continue_stmts(stmt.if_branch, post_expr)
            else_branch: Optional[nodes.StmtNode] = None
            if stmt.else_branch:
                else_branch = self._rewrite_continue_stmts(stmt.else_branch, post_expr)
            return nodes.IfStmt(stmt.line, stmt.col, stmt.cond, if_branch, else_branch)
        elif isinstance(stmt, nodes.TryStmt):
            return nodes.TryStmt(
                stmt.line,
                stmt.col,
                self._rewrite_continue_stmts(stmt.try_block, post_expr),
                stmt.err_var_binding_name,
                self._rewrite_continue_stmts(stmt.catch_block, post_expr),
            )
        elif isinstance(stmt, nodes.ContinueStmt):
            # continue => { post_expr; continue; }
            return nodes.BlockStmt(
                stmt.line,
                stmt.col,
                [
                    post_expr,
                    stmt,
                ],
            )
        else:
            return stmt

    # IfStmt = "if" "(" Expr ")" Block [ ElseBranch ]
    def _parse_if_stmt(self):
        tok = self._expect(TokenKind.IF)
        self._expect(TokenKind.LEFT_PAREN)
        cond_expr = self._parse_expr()
        self._expect(TokenKind.RIGHT_PAREN)
        if_branch, else_branch = self._parse_block(), self._parse_if_stmt_else_branch()
        return nodes.IfStmt(tok.line, tok.col, cond_expr, if_branch, else_branch)

    # ElseBranch = "else" (IfStmt | Block)
    def _parse_if_stmt_else_branch(self):
        if self._accept(TokenKind.ELSE):
            # special case for "else if"; lower into
            # if (x) {
            #   ...
            # } else {
            #   if (y) {
            #     ...
            #   }
            # }
            if self._lookahead(TokenKind.IF):
                return self._parse_if_stmt()
            else:
                return self._parse_block()
        else:
            return None

    # VarDeclStmt = "let" identifier "=" Expr ";"
    def _parse_var_decl_stmt(self):
        tok = self._expect(TokenKind.LET)
        var_name = self._expect(TokenKind.IDENTIFIER).val
        self._expect(TokenKind.EQ)
        val = self._parse_expr()
        self._expect(TokenKind.SEMICOLON)
        return nodes.VarDeclStmt(tok.line, tok.col, var_name, val)

    # TryStmt       = "try" Block "catch" [ ErrVarBinding ] Block
    # ErrVarBinding = "(" identifier ")"
    def _parse_try_stmt(self):
        tok = self._expect(TokenKind.TRY)
        try_block = self._parse_block()
        self._expect(TokenKind.CATCH)

        err_var_binding_name = None
        if self._accept(TokenKind.LEFT_PAREN):
            err_var_binding_name = self._expect(TokenKind.IDENTIFIER).val
            self._expect(TokenKind.RIGHT_PAREN)

        catch_block = self._parse_block()
        return nodes.TryStmt(
            tok.line, tok.col, try_block, catch_block, err_var_binding_name
        )

    # WhileLoopStmt = "while" "(" Expr ")" Block
    def _parse_while_loop_stmt(self):
        tok = self._expect(TokenKind.WHILE)
        self._expect(TokenKind.LEFT_PAREN)
        cond_expr = self._parse_expr()
        self._expect(TokenKind.RIGHT_PAREN)
        self._loop_depth += 1
        body_block = self._parse_block()
        self._loop_depth -= 1
        return nodes.WhileLoopStmt(tok.line, tok.col, cond_expr, body_block)

    # BreakStmt = "break" ";"
    def _parse_break_stmt(self):
        tok = self._expect(TokenKind.BREAK)
        if self._loop_depth == 0:
            raise SyntaxError(
                "unexpected break outside of loop body", tok.line, tok.col
            )
        stmt = nodes.BreakStmt(tok.line, tok.col)
        self._expect(TokenKind.SEMICOLON)
        return stmt

    # ContinueStmt = "continue" ";"
    def _parse_continue_stmt(self):
        tok = self._expect(TokenKind.CONTINUE)
        if self._loop_depth == 0:
            raise SyntaxError(
                "unexpected continue outside of loop body", tok.line, tok.col
            )
        stmt = nodes.ContinueStmt(tok.line, tok.col)
        self._expect(TokenKind.SEMICOLON)
        return stmt

    # ReturnStmt = "return" [ Expr ] ";"
    def _parse_return_stmt(self):
        tok = self._expect(TokenKind.RETURN)
        if not self._in_fn_decl:
            raise SyntaxError(
                "unexpected return outside of function declaration",
                tok.line,
                tok.col,
            )
        if self._accept(TokenKind.SEMICOLON):
            return nodes.ReturnStmt(tok.line, tok.col, None)
        return_val = self._parse_expr()
        self._expect(TokenKind.SEMICOLON)
        return nodes.ReturnStmt(tok.line, tok.col, return_val)

    # ExprInStmtContext ::= Expr ";"
    def _parse_expr_in_stmt_context(self):
        expr = self._parse_expr()
        self._expect(TokenKind.SEMICOLON)
        return expr

    # Expr = LitExpr |
    #   "(" Expr ")" |
    #   FnCallExpr |
    #   AssignmentExpr |
    #   AccessExpr |
    #   CallExpr |
    #   AttrAccessExpr |
    #   AttrAssignmentExpr;
    #
    # LitExpr = BoolLitExpr |
    #   FloatLitExpr |
    #   IntLitExpr |
    #   StrLitExpr |
    #   NullLitExpr |
    #   ListLitExpr |
    #   DictLitExpr;
    #
    # BoolLitExpr  = "true" | "false"
    # FloatLitExpr = integer* "." integer { integer }
    # IntLitExpr   = integer*
    # NullLitExpr  = "null"
    #
    # {* https://docs.python.org/3/reference/lexical_analysis.html#string-and-bytes-literals *}
    # StrLitExpr   = ? Python string literal ?
    #
    # AccessExpr = identifier
    def _parse_expr(self) -> nodes.ExprNode:
        tok = self._next()
        if tok.kind == TokenKind.BOOL_LIT:
            return self._finish_expr(
                nodes.BoolLitExpr(tok.line, tok.col, tok.val == "true")
            )
        elif tok.kind == TokenKind.FLOAT_LIT:
            return self._finish_expr(
                nodes.FloatLitExpr(tok.line, tok.col, float(tok.val))
            )
        elif tok.kind == TokenKind.INT_LIT:
            return self._finish_expr(nodes.IntLitExpr(tok.line, tok.col, int(tok.val)))
        elif tok.kind == TokenKind.STR_LIT:
            try:
                return self._finish_expr(
                    nodes.StrLitExpr(tok.line, tok.col, literal_eval(tok.val))
                )
            except:
                raise SyntaxError("invalid string literal", tok.line, tok.col)
        elif tok.kind == TokenKind.NULL_LIT:
            return self._finish_expr(nodes.NullLitExpr(tok.line, tok.col))
        elif tok.kind == TokenKind.LEFT_PAREN:
            expr = self._parse_expr()
            self._expect(TokenKind.RIGHT_PAREN)
            return self._finish_expr(expr)
        elif tok.kind == TokenKind.LEFT_SQUARE_BRACKET:
            self._backup()
            return self._finish_expr(self._parse_list_lit_expr())
        elif tok.kind == TokenKind.LEFT_BRACE:
            self._backup()
            return self._finish_expr(self._parse_dict_lit_expr())
        elif tok.kind == TokenKind.IDENTIFIER:
            if self._is_done():
                return self._finish_expr(nodes.AccessExpr(tok.line, tok.col, tok.val))
            elif self._lookahead(TokenKind.EQ):
                self._backup()
                return self._finish_expr(self._parse_assignment_expr())
            else:
                return self._finish_expr(nodes.AccessExpr(tok.line, tok.col, tok.val))
        else:
            raise SyntaxError(
                f"unexpected token {tok.kind} at start of expression", tok.line, tok.col
            )

    def _finish_expr(self, expr: nodes.ExprNode) -> nodes.ExprNode:
        cur_expr = expr
        while self._lookahead(
            TokenKind.ATTR_ACCESS, TokenKind.LEFT_SQUARE_BRACKET, TokenKind.LEFT_PAREN
        ):
            if self._lookahead(TokenKind.ATTR_ACCESS):
                cur_expr = self._parse_attr_access_or_assignment(cur_expr)
            elif self._lookahead(TokenKind.LEFT_SQUARE_BRACKET):
                cur_expr = self._parse_item_access_or_assignment(cur_expr)
            else:
                cur_expr = self._parse_call_expr(cur_expr)
        return cur_expr

    # CallExpr = Expr "(" [ ArgList ] ")"
    # ArgList  = { Expr "," } Expr
    def _parse_call_expr(self, callee: nodes.ExprNode):
        args: list[nodes.ExprNode] = []
        self._expect(TokenKind.LEFT_PAREN)
        while not self._accept(TokenKind.RIGHT_PAREN):
            if args:
                self._expect(TokenKind.COMMA)
            args.append(self._parse_expr())
        return nodes.CallExpr(callee.line, callee.col, callee, args)

    # AttrAccessExpr     = Expr "." identifier
    # AttrAssignmentExpr = Expr "." identifier = Expr
    def _parse_attr_access_or_assignment(self, obj: nodes.ExprNode):
        tok = self._expect(TokenKind.ATTR_ACCESS)
        attr_name = tok.val[1:]
        if self._accept(TokenKind.EQ):
            val = self._parse_expr()
            return nodes.AttrAssignmentExpr(tok.line, tok.col, obj, attr_name, val)
        else:
            return nodes.AttrAccessExpr(tok.line, tok.col, obj, attr_name)

    # ItemAccessExpr = Expr "[" Expr "]"
    # ItemAssignmentExpr = Expr "[" Expr "]" "=" Expr
    def _parse_item_access_or_assignment(self, obj: nodes.ExprNode):
        tok = self._expect(TokenKind.LEFT_SQUARE_BRACKET)
        key = self._parse_expr()
        self._expect(TokenKind.RIGHT_SQUARE_BRACKET)
        if self._accept(TokenKind.EQ):
            val = self._parse_expr()
            return nodes.ItemAssignmentExpr(tok.line, tok.col, obj, key, val)
        else:
            return nodes.ItemAccessExpr(tok.line, tok.col, obj, key)

    # AssignmentExpr = identifier "=" Expr
    def _parse_assignment_expr(self):
        tok = self._expect(TokenKind.IDENTIFIER)
        self._expect(TokenKind.EQ)
        val = self._parse_expr()
        return nodes.AssignmentExpr(tok.line, tok.col, tok.val, val)

    # ListLitExpr = "[" [ { Expr ","} Expr ] "]"
    def _parse_list_lit_expr(self):
        tok = self._expect(TokenKind.LEFT_SQUARE_BRACKET)
        values: list[nodes.ExprNode] = []
        while not self._accept(TokenKind.RIGHT_SQUARE_BRACKET):
            if values:
                self._expect(TokenKind.COMMA)
            values.append(self._parse_expr())
        return nodes.ListLitExpr(tok.line, tok.col, values)

    # DictLitExpr  = "{" [ { KeyValuePair "," } KeyValuePair ] "}"
    # KeyValuePair = Expr ":" Expr
    def _parse_dict_lit_expr(self):
        tok = self._expect(TokenKind.LEFT_BRACE)
        entries: list[Tuple[nodes.ExprNode, nodes.ExprNode]] = []
        while not self._accept(TokenKind.RIGHT_BRACE):
            if entries:
                self._expect(TokenKind.COMMA)
            key = self._parse_expr()
            self._expect(TokenKind.COLON)
            val = self._parse_expr()
            entries.append((key, val))
        return nodes.DictLitExpr(tok.line, tok.col, entries)

    def _accept(self, *args: TokenKind):
        tok = self._peek()
        if tok.kind in args:
            self._ignore()
            return True
        return False

    def _lookahead(self, *args: TokenKind):
        return self._peek().kind in args

    def _expect(self, *args: TokenKind):
        expected = ", ".join(map(str, args))
        tok = self._next()
        if tok.kind not in args:
            raise SyntaxError(
                f"unexpected token {tok.kind}; expected one of {expected}",
                tok.line,
                tok.col,
            )
        return tok

    def _peek(self):
        tok = self._next()
        self._backup()
        return tok

    def _next(self):
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    _ignore = _next  # alias for clarity

    def _backup(self, n: Optional[int] = 1):
        if self._pos < n:
            raise InternalError("parser: backup out of range")
        self._pos -= n

    def _is_done(self):
        return self._tokens[self._pos].kind == TokenKind.EOF
