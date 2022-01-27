class SyntaxError(Exception):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(f"{line}:{col}: {msg}")
        self.line = line
        self.col = col
