from typing import Any, Optional


class RuntimeError(Exception):
    def __init__(self, msg: str, line: Optional[int] = -1, col: Optional[int] = -1):
        super().__init__(msg if line == -1 or col == -1 else f"{line}:{col}: {msg}")


class Sentinel(Exception):
    def __init__(self):
        super().__init__("sentinel")


class Break(Sentinel):
    pass


class Continue(Sentinel):
    pass


class Return(Sentinel):
    def __init__(self, val: Any):
        super().__init__()
        self.val = val
