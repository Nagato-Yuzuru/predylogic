from typing import Protocol


class RuleDef[RunCtx, **RuleParams](Protocol):
    """
    A callable that takes a context and positional and keyword arguments and returns a boolean.
    """

    __name__: str

    def __call__(self, ctx: RunCtx, /, *args: RuleParams.args, **kwargs: RuleParams.kwargs) -> bool:
        """
        Take a context and positional and keyword arguments and returns a boolean.

        Args:
            ctx: Rule context.
            *args: Positional arguments for pass to the rule.
            **kwargs: Keyword arguments for pass to the rule.

        Examples:
            >>> class UserCtx:
            ...     age: int
            ...     ...
            >>> def is_over_age_threshold(user_ctx: UserCtx, threshold: int) -> bool:
            ...     return user_ctx.age >= threshold
            >>> is_over_age_threshold.__name__
            'is_over_age_threshold'

        """

        ...
