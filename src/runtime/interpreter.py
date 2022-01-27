from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Optional

from common.errors import InternalError
from parse import nodes
from parse.parser import AstRoot

from runtime.builtins import BUILT_IN_FNS, BuiltInFnCollection
from runtime.errors import Break, Continue, Return, RuntimeError, Sentinel


@dataclass
class Var:
    name: str
    val: Any


class RuntimeEnv:
    def __init__(
        self,
        stack: Optional[list[Var]] = None,
        stack_offsets: Optional[list[int]] = None,
        decl_variables_in_scope: Optional[list[set[str]]] = None,
    ):
        self._stack: list[Var] = stack or []
        self._stack_offsets: list[int] = stack_offsets or []
        self._decl_variables_in_scope: list[set[str]] = decl_variables_in_scope or [
            set()
        ]

    @contextmanager
    def enter_scope(self):
        self._stack_offsets.append(len(self._stack))
        self._decl_variables_in_scope.append(set())
        try:
            yield
        finally:
            offset = self._stack_offsets.pop()
            self._stack = self._stack[:offset]
            self._decl_variables_in_scope.pop()

    def lookup(self, name: str, line: int, col: int):
        try:
            return next(var.val for var in reversed(self._stack) if var.name == name)
        except StopIteration:
            raise RuntimeError(f"undefined variable: {name}", line, col)

    def assign(self, name: str, val: Any, line: int, col: int):
        assigned = False
        for var in reversed(self._stack):
            if var.name == name:
                var.val = val
                assigned = True

        if not assigned:
            raise RuntimeError(
                f"cannot assign to undeclared variable: {name}", line, col
            )

    def declare(self, name: str, val: Any, line: int, col: int):
        if name in self._decl_variables_in_scope[-1]:
            raise RuntimeError(
                f"cannot redeclare variable in same scope: {name}", line, col
            )
        else:
            self._decl_variables_in_scope[-1].add(name)
            self.push(name, val)

    def push(self, name: str, val: Any):
        self._stack.append(Var(name, val))

    def has(self, name: str):
        return any(var.name == name for var in self._stack)

    def copy(self):
        return RuntimeEnv(
            self._stack.copy(),
            self._stack_offsets.copy(),
            [s.copy() for s in self._decl_variables_in_scope],
        )


fn_prototype = object()


class Interpreter:
    def evaluate(self, ast: AstRoot, built_in_fns: BuiltInFnCollection = BUILT_IN_FNS):
        env = RuntimeEnv()
        for name, built_in_fn in built_in_fns.items():
            env.push(name, built_in_fn)
        try:
            # do an initial pass to declare all functions with prototypes up front,
            # so they can refer to one another recursively
            for node in ast.top_level_nodes:
                if isinstance(node, nodes.FnDefinition) and not env.has(node.name):
                    env.declare(node.name, fn_prototype, node.line, node.col)

            # now actually evaluate everything
            for node in ast.top_level_nodes:
                if isinstance(node, nodes.StmtNode):
                    self._visit_stmt(node, env)
                else:
                    self._visit_fn_definition(node, env)
        except Sentinel:
            raise InternalError("interpreter: sentinel escaped")

    def _visit_stmt(self, stmt: nodes.StmtNode, env: RuntimeEnv):
        if isinstance(stmt, nodes.BlockStmt):
            with env.enter_scope():
                self._visit_block_stmt(stmt, env)
        elif isinstance(stmt, nodes.VarDeclStmt):
            self._visit_var_decl_stmt(stmt, env)
        elif isinstance(stmt, nodes.IfStmt):
            self._visit_if_stmt(stmt, env)
        elif isinstance(stmt, nodes.ReturnStmt):
            self._visit_return_stmt(stmt, env)
        elif isinstance(stmt, nodes.WhileLoopStmt):
            self._visit_while_loop_stmt(stmt, env)
        elif isinstance(stmt, nodes.IteratorBasedForLoopStmt):
            self._visit_iterator_based_for_loop_stmt(stmt, env)
        elif isinstance(stmt, nodes.BreakStmt):
            self._visit_break_stmt()
        elif isinstance(stmt, nodes.ContinueStmt):
            self._visit_continue_stmt()
        elif isinstance(stmt, nodes.TryStmt):
            self._visit_try_stmt(stmt, env)
        elif isinstance(stmt, nodes.ExprNode):
            self._evaluate_expr(stmt, env)
        else:
            raise InternalError(f"unhandled statement node type: {type(stmt).__name__}")

    def _visit_fn_definition(self, decl: nodes.FnDefinition, env: RuntimeEnv):
        compiled = self._compile_fn(decl, env)
        env.assign(
            decl.name, compiled, decl.line, decl.col
        )  # function declaration already done in first pass, just assign

    def _compile_fn(self, decl: nodes.FnDefinition, env: RuntimeEnv) -> Callable:
        captured_env = env.copy()

        def compiled(*args: Any):
            call_env = captured_env.copy()
            if (want := len(decl.param_names)) != (got := len(args)):
                raise RuntimeError(f"call {decl.name}: want {want}, got {got} args")
            else:
                with call_env.enter_scope():
                    for param, arg in zip(decl.param_names, args):
                        call_env.declare(param, arg, -1, -1)
                    try:
                        self._visit_block_stmt(decl.body_block, call_env)
                    except Return as r:
                        return r.val
                return None

        return compiled

    def _visit_block_stmt(self, block: nodes.BlockStmt, env: RuntimeEnv):
        for stmt in block.stmts:
            self._visit_stmt(stmt, env)

    def _visit_var_decl_stmt(self, decl: nodes.VarDeclStmt, env: RuntimeEnv):
        val = self._evaluate_expr(decl.val, env)
        env.declare(decl.var_name, val, decl.line, decl.col)

    def _visit_if_stmt(self, if_stmt: nodes.IfStmt, env: RuntimeEnv):
        cond = self._evaluate_expr(if_stmt.cond, env)
        with env.enter_scope():
            if cond:
                self._visit_block_stmt(if_stmt.if_branch, env)
            elif if_stmt.else_branch:
                self._visit_block_stmt(if_stmt.else_branch, env)

    def _visit_while_loop_stmt(self, loop: nodes.WhileLoopStmt, env: RuntimeEnv):
        while self._evaluate_expr(loop.cond, env):
            try:
                with env.enter_scope():
                    self._visit_block_stmt(loop.body_block, env)
            except Break:
                break
            except Continue:
                pass

    def _visit_iterator_based_for_loop_stmt(
        self, loop: nodes.IteratorBasedForLoopStmt, env: RuntimeEnv
    ):
        iterable = self._evaluate_expr(loop.expr, env)
        try:
            it = iter(iterable)
        except TypeError:
            raise RuntimeError(
                f"cannot iterate over value of type {type(iterable).__name__}",
                loop.line,
                loop.col,
            )

        for item in it:
            try:
                with env.enter_scope():
                    env.push(loop.iterator_var_binding_name, item)
                    self._visit_block_stmt(loop.body_block, env)
            except Break:
                break
            except Continue:
                pass

    def _visit_return_stmt(self, return_stmt: nodes.ReturnStmt, env: RuntimeEnv):
        if return_stmt.return_val:
            return_val = self._evaluate_expr(return_stmt.return_val, env)
            raise Return(return_val)
        else:
            raise Return(None)

    def _visit_break_stmt(self):
        raise Break

    def _visit_continue_stmt(self):
        raise Continue

    def _visit_try_stmt(self, try_stmt: nodes.TryStmt, env: RuntimeEnv):
        try:
            with env.enter_scope():
                self._visit_block_stmt(try_stmt.try_block, env)
        except (InternalError, Sentinel):
            raise
        except Exception as e:
            with env.enter_scope():
                if try_stmt.err_var_binding_name:
                    env.push(try_stmt.err_var_binding_name, e)
                self._visit_block_stmt(try_stmt.catch_block, env)

    def _evaluate_expr(self, expr: nodes.ExprNode, env: RuntimeEnv):
        if isinstance(expr, nodes.CallExpr):
            return self._evaluate_call_expr(expr, env)
        elif isinstance(expr, nodes.SimpleLitExpr):
            return self._evaluate_simple_lit_expr(expr)
        elif isinstance(expr, nodes.AssignmentExpr):
            return self.evaluate_assignment_expr(expr, env)
        elif isinstance(expr, nodes.AccessExpr):
            return self._evaluate_access_expr(expr, env)
        elif isinstance(expr, nodes.AttrAccessExpr):
            return self._evaluate_attr_access_expr(expr, env)
        elif isinstance(expr, nodes.AttrAssignmentExpr):
            return self._evaluate_attr_assignment_expr(expr, env)
        elif isinstance(expr, nodes.ItemAccessExpr):
            return self._evaluate_item_access_expr(expr, env)
        elif isinstance(expr, nodes.ItemAssignmentExpr):
            return self._evaluate_item_assignment_expr(expr, env)
        elif isinstance(expr, nodes.ListLitExpr):
            return self._evaluate_list_lit_expr(expr, env)
        elif isinstance(expr, nodes.DictLitExpr):
            return self._evaluate_dict_lit_expr(expr, env)
        else:
            raise InternalError(f"unhandled expr node type: {type(expr).__name__}")

    def evaluate_assignment_expr(self, assign: nodes.AssignmentExpr, env: RuntimeEnv):
        val = self._evaluate_expr(assign.val, env)
        env.assign(assign.name, val, assign.line, assign.col)
        return val

    def _evaluate_access_expr(self, access: nodes.AccessExpr, env: RuntimeEnv):
        return env.lookup(access.name, access.line, access.col)

    def _evaluate_attr_access_expr(self, access: nodes.AttrAccessExpr, env: RuntimeEnv):
        obj = self._evaluate_expr(access.obj, env)
        try:
            return getattr(obj, access.attr_name)
        except AttributeError:
            raise RuntimeError(
                f"cannot access attribute {repr(access.attr_name)} on value of type {type(obj).__name__}",
                access.line,
                access.col,
            )

    def _evaluate_attr_assignment_expr(
        self, assign: nodes.AttrAssignmentExpr, env: RuntimeEnv
    ):
        obj = self._evaluate_expr(assign.obj, env)
        val = self._evaluate_expr(assign.val, env)
        try:
            setattr(obj, assign.attr_name, val)
        except AttributeError:
            raise RuntimeError(
                f"cannot set attribute {repr(assign.attr_name)} on value of type {type(obj).__name__}",
                assign.line,
                assign.col,
            )
        return val

    def _evaluate_item_access_expr(self, access: nodes.ItemAccessExpr, env: RuntimeEnv):
        obj = self._evaluate_expr(access.obj, env)
        key = self._evaluate_expr(access.key, env)
        try:
            return obj[key]
        except:
            raise RuntimeError(
                f"cannot access item {repr(key)} on value of type {type(obj).__name__}",
                access.line,
                access.col,
            )

    def _evaluate_item_assignment_expr(
        self, assign: nodes.ItemAssignmentExpr, env: RuntimeEnv
    ):
        obj = self._evaluate_expr(assign.obj, env)
        key = self._evaluate_expr(assign.key, env)
        val = self._evaluate_expr(assign.val, env)
        try:
            obj[key] = val
            return val
        except:
            raise RuntimeError(
                f"cannot assign item {repr(key)} on value of type {type(obj).__name__}",
                assign.line,
                assign.col,
            )

    def _evaluate_simple_lit_expr(self, lit: nodes.SimpleLitExpr):
        return lit.val

    def _evaluate_list_lit_expr(self, lit: nodes.ListLitExpr, env: RuntimeEnv):
        return [self._evaluate_expr(expr, env) for expr in lit.values]

    def _evaluate_dict_lit_expr(self, lit: nodes.DictLitExpr, env: RuntimeEnv):
        return {
            self._evaluate_expr(k, env): self._evaluate_expr(v, env)
            for k, v in lit.entries
        }

    def _evaluate_call_expr(self, call: nodes.CallExpr, env: RuntimeEnv) -> Any:
        args = [self._evaluate_expr(expr, env) for expr in call.args]
        fn = self._evaluate_expr(call.callee, env)
        if fn is fn_prototype:
            raise RuntimeError(
                f"cannot call fn {call.callee} before it is defined",
                call.line,
                call.col,
            )
        elif callable(fn):
            try:
                return fn(*args)
            except Exception as e:
                raise RuntimeError(
                    f"error calling {call.callee}: {e}", call.line, call.col
                )
        else:
            raise RuntimeError(
                f"cannot call non-callable value {call.callee} of type {type(call.callee).__name__}",
                call.line,
                call.col,
            )
