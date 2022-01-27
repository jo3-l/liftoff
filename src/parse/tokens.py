from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    BOOL_LIT = auto()  # true/false
    FLOAT_LIT = auto()  # float literal
    STR_LIT = auto()  # quoted string literal
    INT_LIT = auto()  # integer literal
    NULL_LIT = auto()  # null literal

    COMMA = auto()  # ,
    COLON = auto()  # ;
    EQ = auto()  # =
    LEFT_BRACE = auto()  # {
    LEFT_PAREN = auto()  # (
    LEFT_SQUARE_BRACKET = auto()  # [
    RIGHT_BRACE = auto()  # }
    RIGHT_PAREN = auto()  # )
    RIGHT_SQUARE_BRACKET = auto()  # ]
    SEMICOLON = auto()  # ;
    LINE_COMMENT_START = auto()  # //
    MULTILINE_COMMENT_START = auto()  # /*
    MULTILINE_COMMENT_END = auto()  # */

    ATTR_ACCESS = auto()  # attribute access
    IDENTIFIER = auto()  # alphanumeric identifier

    BREAK = auto()  # break
    CATCH = auto()  # catch
    CONTINUE = auto()  # continue
    ELSE = auto()  # else
    FN = auto()  # fn
    FOR = auto()  # for
    IF = auto()  # if
    IN = auto()  # in
    LET = auto()  # let
    RETURN = auto()  # return
    TRY = auto()  # try
    WHILE = auto()  # while

    EOF = auto()

    def __str__(self):
        return self.name

    __repr__ = __str__


@dataclass
class Token:
    kind: TokenKind
    val: str
    line: int
    col: int

    def __str__(self):
        return f"<{self.kind}: {repr(self.val)} at {self.line}:{self.col}>"

    __repr__ = __str__


KEYWORDS = {
    "break": TokenKind.BREAK,
    "catch": TokenKind.CATCH,
    "continue": TokenKind.CONTINUE,
    "else": TokenKind.ELSE,
    "fn": TokenKind.FN,
    "for": TokenKind.FOR,
    "if": TokenKind.IF,
    "in": TokenKind.IN,
    "let": TokenKind.LET,
    "return": TokenKind.RETURN,
    "try": TokenKind.TRY,
    "while": TokenKind.WHILE,
}

SYNTAX = {
    ",": TokenKind.COMMA,
    ":": TokenKind.COLON,
    "=": TokenKind.EQ,
    "{": TokenKind.LEFT_BRACE,
    "}": TokenKind.RIGHT_BRACE,
    "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN,
    "[": TokenKind.LEFT_SQUARE_BRACKET,
    "]": TokenKind.RIGHT_SQUARE_BRACKET,
    ";": TokenKind.SEMICOLON,
}
