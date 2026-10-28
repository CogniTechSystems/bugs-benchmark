"""Error type and display helpers for calculator failures."""


class CalculatorError(ValueError):
    """Error raised for malformed expressions and invalid arithmetic, carrying an optional zero-
    based source offset where the problem was detected.
    """

    def __init__(self, message: str, position: int | None = None) -> None:
        """Create an error from a readable message and an optional zero-based source position."""
        super().__init__(message)
        self.message = message
        self.position = position

    def __str__(self) -> str:
        """Return the message, followed by its position when a position is known."""
        if self.position is None:
            return self.message
        return f"{self.message} at position {self.position}"


def render_error(source: str, error: CalculatorError) -> str:
    """Return the error text, followed by the source and a caret under the clamped position when the
    error carries a position.
    """
    if error.position is None:
        return str(error)
    column = min(max(error.position, 0), len(source))
    return f"{error}\n{source}\n{' ' * column}^"
