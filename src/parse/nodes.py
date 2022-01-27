from dataclasses import dataclass, field
from json import dumps
from textwrap import indent
from typing import Optional, Tuple, Union

TopLevelNode = Union["FnDefinition", "StmtNode"]


@dataclass
class Node:
    line: int
    col: int


@dataclass
class StmtNode(Node):
    pass


@dataclass
class ExprNode(StmtNode):
    pass


@dataclass
class BlockStmt(StmtNode):
    stmts: list[StmtNode] = field(default_factory=lambda: [])

    def __str__(self):
        lines = ["{"]
        for stmt in self.stmts:
            if isinstance(stmt, ExprNode):
                lines.append(indent(f"{stmt};", "\t"))
            else:
                lines.append(indent(str(stmt), "\t"))
        lines.append("}")
        return "\n".join(lines)

    __repr__ = __str__


@dataclass
class CallExpr(ExprNode):
    callee: ExprNode
    args: list[ExprNode]

    def __str__(self):
        args = ", ".join(map(str, self.args))
        return f"{self.callee}({args})"

    __repr__ = __str__


@dataclass
class AttrAccessExpr(ExprNode):
    obj: ExprNode
    attr_name: str

    def __str__(self):
        return f"{self.obj}.{self.attr_name}"

    __repr__ = __str__


@dataclass
class AttrAssignmentExpr(ExprNode):
    obj: ExprNode
    attr_name: str
    val: ExprNode

    def __str__(self):
        return f"{self.obj}.{self.attr_name} = {self.val}"

    __repr__ = __str__


@dataclass
class ItemAccessExpr(ExprNode):
    obj: ExprNode
    key: ExprNode

    def __str__(self):
        return f"{self.obj}[{self.key}]"

    __repr__ = __str__


@dataclass
class ItemAssignmentExpr(ExprNode):
    obj: ExprNode
    key: ExprNode
    val: ExprNode

    def __str__(self):
        return f"{self.obj}[{self.key}] = {self.val}"


@dataclass
class SimpleLitExpr(ExprNode):
    pass


@dataclass
class BoolLitExpr(SimpleLitExpr):
    val: bool

    def __str__(self):
        return "true" if self.val else "false"

    __repr__ = __str__


@dataclass
class FloatLitExpr(SimpleLitExpr):
    val: float

    def __str__(self):
        return repr(self.val)

    __repr__ = __str__


@dataclass
class IntLitExpr(SimpleLitExpr):
    val: int

    def __str__(self):
        return repr(self.val)

    __repr__ = __str__


@dataclass
class StrLitExpr(SimpleLitExpr):
    val: str

    def __str__(self):
        return dumps(self.val)

    __repr__ = __str__


@dataclass
class NullLitExpr(SimpleLitExpr):
    val: None = None

    def __str__(self):
        return "null"

    __repr__ = __str__


@dataclass
class ListLitExpr(ExprNode):
    values: list[ExprNode]

    def __str__(self):
        value_list = ", ".join(map(str, self.values))
        return f"[{value_list}]"


@dataclass
class DictLitExpr(ExprNode):
    entries: list[Tuple[ExprNode, ExprNode]]

    def __str__(self):
        entry_list = ", ".join(f"{k}: {v}" for k, v in self.entries)
        return f"{{{entry_list}}}"


@dataclass
class VarDeclStmt(StmtNode):
    var_name: str
    val: ExprNode

    def __str__(self):
        return f"let {self.var_name} = {self.val};"

    __repr__ = __str__


@dataclass
class AssignmentExpr(ExprNode):
    name: str
    val: ExprNode

    def __str__(self):
        return f"{self.name} = {self.val}"

    __repr__ = __str__


@dataclass
class AccessExpr(ExprNode):
    name: str

    def __str__(self):
        return self.name

    __repr__ = __str__


@dataclass
class IfStmt(StmtNode):
    cond: ExprNode
    if_branch: StmtNode
    else_branch: Optional[StmtNode] = None

    def __str__(self):
        parts: list[str] = []
        parts.append(f"if ({self.cond}) {self.if_branch}")
        if self.else_branch:
            parts.append(f" else {self.else_branch}")
        return "".join(parts)

    __repr__ = __str__


@dataclass
class FnDefinition(Node):
    name: str
    param_names: list[str]
    body_block: BlockStmt

    def __str__(self):
        params = ", ".join(self.param_names)
        return f"fn {self.name}({params}) {self.body_block}"

    __repr__ = __str__


@dataclass
class ReturnStmt(StmtNode):
    return_val: Optional[ExprNode] = None

    def __str__(self):
        return f"return {self.return_val};" if self.return_val else "return;"

    __repr__ = __str__


@dataclass
class WhileLoopStmt(StmtNode):
    cond: ExprNode
    body_block: BlockStmt

    def __str__(self):
        return f"while ({self.cond}) {self.body_block}"

    __repr__ = __str__


@dataclass
class IteratorBasedForLoopStmt(StmtNode):
    iterator_var_binding_name: str
    expr: ExprNode
    body_block: BlockStmt

    def __str__(self):
        return f"for (let {self.iterator_var_binding_name} in {self.expr}) {self.body_block}"

    __repr__ = __str__


@dataclass
class BreakStmt(StmtNode):
    pass


@dataclass
class ContinueStmt(StmtNode):
    pass


@dataclass
class TryStmt(StmtNode):
    try_block: BlockStmt
    catch_block: BlockStmt
    err_var_binding_name: Optional[str] = None

    def __str__(self):
        if self.err_var_binding_name:
            return f"try {self.try_block} catch ({self.err_var_binding_name}) {self.catch_block}"
        else:
            return f"try {self.try_block} catch {self.catch_block}"

    __repr__ = __str__
