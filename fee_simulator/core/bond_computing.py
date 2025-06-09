from fee_simulator.utils import is_appeal_round
from fee_simulator.utils_round_sizes import get_round_size_for_bond
from fee_simulator.types import RoundLabel
from typing import List


def compute_appeal_bond(
    normal_round_index: int,
    leader_timeout: int,
    validators_timeout: int,
    round_labels: List[RoundLabel],
) -> int:

    # Validate this is actually a normal round index
    if normal_round_index < 0 or normal_round_index >= len(round_labels):
        raise ValueError(f"Invalid normal round index: {normal_round_index}")

    if is_appeal_round(round_labels[normal_round_index]):
        raise ValueError(f"Round {normal_round_index} is not a normal round")

    # The appeal round is the next round
    appeal_round_index = normal_round_index + 1

    # Check that the next round exists and is an appeal
    if appeal_round_index >= len(round_labels):
        raise ValueError(f"No appeal round after normal round {normal_round_index}")

    if not is_appeal_round(round_labels[appeal_round_index]):
        raise ValueError(f"Round {appeal_round_index} is not an appeal round")

    # Get the size of the appeal round using the new utility
    appeal_round_size = get_round_size_for_bond(appeal_round_index, round_labels)

    # Bond covers the cost of the appeal round
    appeal_cost = appeal_round_size * validators_timeout
    total_cost = appeal_cost + leader_timeout

    return max(total_cost, 0)
