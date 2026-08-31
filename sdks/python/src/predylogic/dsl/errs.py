"""Domain exceptions for the pdyl DSL compiler."""


class PdylError(SyntaxError):
    """
    A ``.pdyl`` compile-time error.

    Subclasses ``SyntaxError`` deliberately (not the package's usual ``Exception``
    bases): compile errors carry ``filename``/``lineno``/``offset``/``text`` and
    render with Python's own caret display, so a semantic error in a ``.pdyl``
    file reports exactly like a syntax error in a ``.py`` file — at load time,
    with a position. Both real syntax errors (re-raised from :func:`ast.parse`)
    and whitelist/semantic errors use this one type.
    """
