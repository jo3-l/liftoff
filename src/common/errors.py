class InternalError(Exception):
    def __init__(self, msg: str):
        super().__init__(f"internal error: {msg}")
