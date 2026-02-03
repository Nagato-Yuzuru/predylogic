class SchemaError(Exception):
    """Base Schema exception."""

    ...


class RuleDefRingError(SchemaError):
    """
    Error raised when a rule definition forms a ring, creating an infinite loop.
    """

    def __init__(self, ring: tuple[str]):
        self.ring = ring
        if len(ring) == 1:
            msg = f"Cycle detected: {ring[0]}"
        else:
            msg = f"Cycle detected: {ring[0]} -> {ring[1]} -> ..." + " -> ".join(ring[:-1])
        super().__init__(msg)
