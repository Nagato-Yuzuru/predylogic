from collections.abc import Collection


class RegisterError(Exception):
    """Base class for exceptions in this module."""

    ...


class RuleDefNotNamedError(RegisterError):
    """Raised when a rule is not decorated with @rule_def."""

    def __init__(self):
        super().__init__("RuleDef must have a name.")


class RegistryNameConflictError(RegisterError):
    """
    Raised when attempting to registry a rule with a name that is already in use.
    """

    def __init__(self, conflict_register_name: str, added_register: Collection[str]):
        """
        Args:
            conflict_register_name: conflict registry name.
            added_register: were added register.
        """
        self.conflict_register_name = conflict_register_name
        self.added_register = added_register

        super().__init__(f"{self.conflict_register_name} was added in: {', '.join(self.added_register)}")


class RuleDefConflictError(RegisterError):
    """
    Raised when attempting to register a rule with a name that is already in use.
    """

    def __init__(self, registry_name: str, rule_name: str, registered: Collection[str]):
        """
        Args:
            registry_name: registry name.
            rule_name: conflict rule name.
            registered: has registered rule.

        """

        self.registry_name = registry_name
        self.rule_name = rule_name
        self.registered = registered

        super().__init__(
            f"{self.rule_name} is already registered in {self.registry_name}: {', '.join(self.registered)}",
        )


class RegistryNotFoundError(RegisterError):
    """Raised when attempting to get a registry that does not exist."""

    def __init__(self, registry_name: str):
        self.registry_name = registry_name
        super().__init__(f"Registry '{self.registry_name}' not found")


class RuleNotFoundError(RegisterError):
    """Raised when attempting to get a rule that does not exist."""

    def __init__(self, rule_name: str):
        self.rule_name = rule_name
        super().__init__(f"Rule '{self.rule_name}' not found")


class RuleDefNotFoundError(RegisterError):
    """Raised when attempting to get a rule definition that does not exist."""

    def __init__(self, rule_def_name: str):
        self.rule_def_name = rule_def_name
        super().__init__(f"Rule definition '{rule_def_name}' not found")
