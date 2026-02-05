class RuleEngineError(Exception):
    """Base RuleEngine exception."""

    ...


class RuleDefRingError(RuleEngineError):
    """
    Error raised when a rule definition forms a ring, creating an infinite loop.
    """

    def __init__(self, ring: tuple[str]):
        self.ring = ring
        if len(ring) <= 1:
            msg = f"Cycle detected: {ring[0]}"
        else:
            msg = f"Cycle detected: {ring[0]} -> {ring[1] if len(ring) > 2 else ''} -> ..." + " -> ".join(ring[:-1])  # noqa: PLR2004
        super().__init__(msg)


class RuleRevokedError(RuleEngineError):
    """
    Raised when a referenced rule handle exists but implies a revoked or unconfigured state.
    """

    def __init__(self, registry_name: str, rule_name: str):
        self.registry_name = registry_name
        self.rule_name = rule_name

        super().__init__(f"Rule '{rule_name}' in {self.registry_name} revoked or missing.")
