from argparse import ArgumentParser
from os.path import isfile
from sys import exit

import liftoff
from parse.errors import SyntaxError
from parse.lexer import Lexer
from parse.parser import Parser
from runtime.errors import RuntimeError

arg_parser = ArgumentParser(description="Evaluate Rocket source code")
arg_parser.add_argument("path", help="path to the code to evaluate")
arg_parser.add_argument(
    "-a", "--ast", action="store_true", help="whether or not to show the ast"
)

args = arg_parser.parse_args()
input_path: str = args.path
show_ast: bool = args.ast

if not isfile(input_path):
    print("the path specified does not exist")
    exit(1)

with open(input_path) as f:
    try:
        src = f.read()
        if show_ast:
            tokens = Lexer().lex(src)
            ast = Parser().parse(tokens)
            print(ast)
            print()

        liftoff.evaluate(src)
    except SyntaxError as e:
        print(f"syntax error: {e}")
        exit(1)
    except RuntimeError as e:
        print(f"runtime error: {e}")
        exit(1)
