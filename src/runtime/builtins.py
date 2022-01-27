import operator
from typing import Callable

BuiltInFnCollection = dict[str, Callable]


def _logical_or(arg0, *args):
    if arg0:
        return arg0
    else:
        return next(filter(bool, args), args[-1])


def _logical_and(arg0, *args):
    if not arg0:
        return arg0
    else:
        return next((arg for arg in args if not arg), args[-1])


def _logical_not(arg):
    return not arg


def _format(tmpl, *args):
    return tmpl.format(*args)


BUILT_IN_FNS: BuiltInFnCollection = {
    # i/o utilities
    "print": print,
    "input": input,

    # comparison operators
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
    "ge": operator.ge,
    "gt": operator.gt,

    # math operators
    "abs": operator.abs,
    "add": operator.add,
    "sub": operator.sub,
    "mul": operator.mul,
    "div": operator.truediv,
    "pow": operator.pos,
    "neg": operator.neg,
    "mod": operator.mod,
    "floor_div": operator.floordiv,

    # logical operators
    "not": _logical_not,
    "or": _logical_or,
    "and": _logical_and,

    # parsing
    "parse_int": int,
    "parse_float": float,

    # misc
    "format": _format,
    "range": range,
    "len": len,
}  # fmt: skip
