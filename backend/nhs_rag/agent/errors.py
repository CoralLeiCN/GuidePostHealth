class AnswerUnavailableError(RuntimeError):
    """The answer runtime could not complete a request."""


class InvalidAnswerError(ValueError):
    """Generated output failed the answer or evidence-reference contract."""
