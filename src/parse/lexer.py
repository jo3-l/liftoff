from dataclasses import dataclass
from typing import Callable, Optional

from common.errors import InternalError

from parse.errors import SyntaxError
from parse.tokens import KEYWORDS, SYNTAX, Token, TokenKind


@dataclass
class LexerState:
    line: int
    col: int
    pos: int


class Lexer:
    def __init__(self):
        self._src = ""
        self._line = 1
        self._col = 1
        self._pos = 0

    def lex(self, src: str):
        self._src = src
        self._reset()
        tokens: list[Token] = []
        while tok := self._lex_any():
            tokens.append(tok)
        tokens.append(Token(TokenKind.EOF, "", self._line, self._col))
        return tokens

    def _reset(self):
        self._line = 1
        self._col = 1
        self._pos = 0

    def _lex_any(self) -> Optional[Token]:
        self._accept_run(str.isspace)
        if self._is_done():
            return None

        line, col = self._line, self._col
        backup = self._save()
        c = self._next()

        if c.isalpha() or c == "_":
            self._restore(backup)
            return self._lex_identifier()
        elif c in SYNTAX:
            return Token(SYNTAX[c], c, line, col)
        elif c == "/":
            if self._is_done():
                raise SyntaxError(f"unexpected character '/'", line, col)

            # could be either a multiline or a line comment; lookahead to see which it is
            nxt = self._peek()
            if nxt == "*":
                self._lex_multiline_comment()
            elif nxt == "/":
                self._lex_line_comment()
            else:
                raise SyntaxError(f"unexpected character '/'", line, col)
            return None if self._is_done() else self._lex_any()
        elif c == ".":
            if self._is_done():
                raise SyntaxError(f"unexpected character '.'", line, col)
            elif self._peek().isalpha() or self._peek() == "_":
                attr = self._accept_run(is_word_char)
                return Token(TokenKind.ATTR_ACCESS, f".{attr}", line, col)
            else:
                self._restore(backup)
                return self._lex_num_lit()
        elif c == '"':
            self._restore(backup)
            return self._lex_str_lit()
        elif c.isdigit():
            self._restore(backup)
            return self._lex_num_lit()
        else:
            raise SyntaxError(f"unexpected character '{c}'", line, col)

    def _lex_identifier(self):
        line, col = self._line, self._col
        word = self._accept_run(is_word_char)
        if word in KEYWORDS:
            kind = KEYWORDS[word]
            return Token(kind, word, line, col)
        elif word == "true" or word == "false":
            return Token(TokenKind.BOOL_LIT, word, line, col)
        elif word == "null":
            return Token(TokenKind.NULL_LIT, word, line, col)
        else:
            return Token(TokenKind.IDENTIFIER, word, line, col)

    def _lex_multiline_comment(self):
        line, col = self._line, self._col
        c1, c2 = self._next(), self._next()
        while not self._is_done() and c1 != "*" or c2 != "/":
            c1, c2 = c2, self._next()
        if c1 != "*" or c2 != "/":
            raise SyntaxError("unclosed multiline comment", line, col)

    def _lex_line_comment(self):
        while not self._is_done() and self._next() != "\n":
            pass

    def _lex_num_lit(self):
        line, col = self._line, self._col
        whole = self._accept_run(str.isdigit)
        if self._peek() == ".":
            self._ignore()
            frac = self._accept_run(str.isdigit)
            return Token(TokenKind.FLOAT_LIT, f"{whole}.{frac}", line, col)
        else:
            return Token(TokenKind.INT_LIT, whole, line, col)

    def _lex_str_lit(self):
        line, col, init_pos = self._line, self._col, self._pos
        self._ignore()  # ignore opening quote
        in_escape = found_close = False

        while not self._is_done():
            c = self._next()
            if in_escape:
                in_escape = False
            elif c == "\\":
                in_escape = True
            elif c == '"':
                found_close = True
                break

        if not found_close:
            raise SyntaxError("unclosed string literal", line, col)
        elif in_escape:
            raise SyntaxError(
                "unexpected escape character at end of string literal", line, col
            )
        return Token(TokenKind.STR_LIT, self._src[init_pos : self._pos], line, col)

    def _accept_run(self, pred: Callable[[str], bool]):
        chars: list[str] = []
        while not self._is_done():
            c = self._peek()
            if pred(c):
                self._next()
                chars.append(c)
            else:
                break
        return "".join(chars)

    def _peek(self):
        init_state = self._save()
        c = self._next()
        self._restore(init_state)
        return c

    def _next(self):
        if self._is_done():
            raise InternalError("lexer: next called on finished lexer")
        c = self._src[self._pos]
        self._pos += 1
        if c == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return c

    _ignore = _next  # alias for clarity

    def _save(self):
        return LexerState(self._line, self._col, self._pos)

    def _restore(self, state: LexerState):
        self._line = state.line
        self._col = state.col
        self._pos = state.pos

    def _is_done(self):
        return self._pos >= len(self._src)


def is_word_char(c: str):
    return c.isalnum() or c == "_"
