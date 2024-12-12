# simulation/transaction_budget.py


from dataclasses import dataclass

from simulation.errors import OutOfGasError


@dataclass
class PresetLeaf:
    """
    A leaf preset representing a simple message pattern with direct gas costs.

    Used for basic message patterns that don't reference other messages.
    Gas costs are fixed and known at initialization.
    """

    initial_leader_budget: int = 0
    initial_validator_budget: int = 0
    rotation_budget: list[int] = None
    appeal_rounds_budget: list[int] = None

    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.rotation_budget is None:
            self.rotation_budget = [0] * 7
        if self.appeal_rounds_budget is None:
            self.appeal_rounds_budget = [0] * 7

    def compute_total_gas(self) -> int:
        """
        Calculate total gas required for this leaf preset.

        Returns:
            int: Sum of all gas costs in this preset
        """
        return (
            self.initial_leader_budget
            + self.initial_validator_budget
            + sum(self.rotation_budget)
            + sum(self.appeal_rounds_budget)
        )


@dataclass
class PresetBranch:
    """
    A branch preset representing a complex message pattern that may reference other presets.

    Used for composite message patterns that can reference other branches or leaves.
    Includes both direct gas costs and references to other message patterns.
    """

    initial_leader_budget: int = 0
    initial_validator_budget: int = 0
    rotation_budget: list[int] = None
    appeal_rounds_budget: list[int] = None
    internal_messages_budget_guess: dict[str, str] = (
        None  # message_key -> reference_key
    )
    external_messages_budget_guess: list[int] = None

    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.rotation_budget is None:
            self.rotation_budget = [0] * 7
        if self.appeal_rounds_budget is None:
            self.appeal_rounds_budget = [0] * 7
        if self.internal_messages_budget_guess is None:
            self.internal_messages_budget_guess = {}
        if self.external_messages_budget_guess is None:
            self.external_messages_budget_guess = []

    def compute_own_gas(self) -> int:
        """
        Calculate gas required for this branch's own operations.

        Returns:
            int: Sum of direct gas costs (excluding referenced messages)
        """
        return (
            self.initial_leader_budget
            + self.initial_validator_budget
            + sum(self.rotation_budget)
            + sum(self.appeal_rounds_budget)
            + sum(self.external_messages_budget_guess)
        )


class TransactionBudget:
    """
    Manages the complete gas budget for a transaction.

    Handles both direct gas costs and preset-based message patterns,
    tracking gas usage and ensuring operations stay within budget limits.
    """

    def __init__(
        self,
        initial_leader_budget: int,
        initial_validator_budget: int,
        rotation_budget: list[int],
        appeal_rounds_budget: list[int],
        preset_leafs: dict[str, PresetLeaf] = None,
        preset_branches: dict[str, PresetBranch] = None,
        total_internal_messages_budget: int = 0,
        external_messages_budget_guess: list[int] = None,
    ):
        """
        Initialize a new transaction budget.

        Args:
            initial_leader_budget: Gas allocated for initial leader operations
            initial_validator_budget: Gas allocated for initial validator operations
            rotation_budget: Gas allocated for each potential rotation
            appeal_rounds_budget: Gas allocated for each potential appeal
            preset_leafs: Dictionary of leaf presets for message patterns
            preset_branches: Dictionary of branch presets for message patterns
            total_internal_messages_budget: Total gas limit for internal messages
            external_messages_budget_guess: Expected gas costs for external messages

        Raises:
            ValueError: If rotation and appeal budgets have different lengths
        """
        # Validate budget lists
        if len(rotation_budget) != len(appeal_rounds_budget):
            raise ValueError("Rotation and appeal budgets must have same length")

        # Direct budgets
        self.initial_leader_budget = initial_leader_budget
        self.initial_validator_budget = initial_validator_budget
        self.rotation_budget = rotation_budget
        self.appeal_rounds_budget = appeal_rounds_budget

        # Preset structures
        self.preset_leafs = preset_leafs or {}
        self.preset_branches = preset_branches or {}

        # Message budgets
        self.total_internal_messages_budget = total_internal_messages_budget
        self.external_messages_budget_guess = external_messages_budget_guess or []

        # Calculate total available gas
        self.total_gas = (
            initial_leader_budget
            + initial_validator_budget
            + sum(rotation_budget)
            + sum(appeal_rounds_budget)
            + total_internal_messages_budget
            + sum(self.external_messages_budget_guess)
        )

        # Runtime tracking
        self.remaining_gas = self.total_gas
        self.failed = False

    def get_gas_usage(self) -> tuple[int, int, float]:
        """
        Get current gas usage statistics.

        Returns:
            tuple[int, int, float]: (gas_used, gas_remaining, usage_percentage)
        """
        gas_used = self.total_gas - self.remaining_gas
        usage_percentage = (
            (gas_used / self.total_gas) * 100 if self.total_gas > 0 else 0
        )
        return gas_used, self.remaining_gas, usage_percentage

    def compute_internal_message_budget(self, message_key: str) -> int | None:
        """
        Compute gas cost for a specific message pattern.

        Recursively traverses the preset tree structure to compute total gas costs
        for complex message patterns.

        Args:
            message_key: Identifier for the message pattern

        Returns:
            Optional[int]: Computed gas cost, or None if invalid or insufficient gas

        Raises:
            OutOfGasError: If computation would exceed remaining gas
        """
        if self.failed:
            raise OutOfGasError("Transaction already failed")

        # Try leaf preset first
        if message_key in self.preset_leafs:
            return self._compute_leaf_budget(message_key)

        # Then try branch preset
        if message_key in self.preset_branches:
            return self._compute_branch_budget(message_key)

        return None

    def _compute_leaf_budget(self, message_key: str) -> int:
        """Compute gas cost for a leaf preset."""
        leaf = self.preset_leafs[message_key]
        gas = leaf.compute_total_gas()

        if gas > self.remaining_gas:
            self.failed = True
            raise OutOfGasError(f"Insufficient gas for leaf preset: {message_key}")

        self.remaining_gas -= gas
        return gas

    def _compute_branch_budget(self, message_key: str) -> int:
        """Compute gas cost for a branch preset."""
        branch = self.preset_branches[message_key]
        total_gas = branch.compute_own_gas()

        # Compute gas for referenced messages
        for ref_key in branch.internal_messages_budget_guess.values():
            try:
                ref_gas = self.compute_internal_message_budget(ref_key)
                if ref_gas is None:
                    self.failed = True
                    raise OutOfGasError(f"Invalid reference in branch: {ref_key}")
                total_gas += ref_gas
            except OutOfGasError:
                self.failed = True
                raise

        if total_gas > self.remaining_gas:
            self.failed = True
            raise OutOfGasError(f"Insufficient gas for branch preset: {message_key}")

        self.remaining_gas -= total_gas
        return total_gas

    def get_round_budgets(self, round_number: int) -> tuple[int, int]:
        """
        Get available rotation and appeal budgets for a specific round.

        Args:
            round_number: Round index (0-based)

        Returns:
            tuple[int, int]: (rotation_budget, appeal_budget) for the round

        Raises:
            ValueError: If round number exceeds available budgets
        """
        if round_number >= len(self.rotation_budget):
            raise ValueError(f"No budget allocated for round {round_number}")

        return (
            self.rotation_budget[round_number],
            self.appeal_rounds_budget[round_number],
        )

    def __repr__(self) -> str:
        """String representation of the budget state."""
        used, remaining, percentage = self.get_gas_usage()
        return (
            f"TransactionBudget("
            f"used={used}, "
            f"remaining={remaining}, "
            f"usage={percentage:.1f}%, "
            f"failed={self.failed})"
        )
