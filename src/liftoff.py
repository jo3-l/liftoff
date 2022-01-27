from parse.lexer import Lexer
from parse.parser import Parser
from runtime.builtins import BUILT_IN_FNS, BuiltInFnCollection
from runtime.interpreter import Interpreter


def evaluate(src: str, built_in_fns: BuiltInFnCollection = BUILT_IN_FNS):
    tokens = Lexer().lex(src)
    ast = Parser().parse(tokens)
    interpreter = Interpreter()
    interpreter.evaluate(ast, built_in_fns)
