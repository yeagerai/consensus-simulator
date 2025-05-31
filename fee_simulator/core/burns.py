from fee_simulator.models import FeeEvent
from typing import List
from fee_simulator.core.bond_computing import compute_appeal_bond
from fee_simulator.types import RoundLabel


def compute_unsuccessful_leader_appeal_burn(
    current_round_index: int, appealant_address: str, fee_events: List[FeeEvent]
) -> float:

    burn = 0
    cost = 0
    earned = 0

    for event in fee_events:
        if (
            event.address == appealant_address
            and event.round_label is not None
            and "UNSUCCESSFUL" in event.round_label
            and event.round_index == current_round_index
        ):
            cost += event.cost

        if (
            event.round_index == current_round_index
            or event.round_index == current_round_index + 1
        ):
            earned += event.earned

    burn = cost - earned
    return burn


def compute_unsuccessful_validator_appeal_burn(
    current_round_index: int,
    leader_timeout: int,
    validator_timeout: int,
    fee_events: List[FeeEvent],
    round_labels: List[RoundLabel],  # New parameter
) -> float:

    burn = 0
    cost = compute_appeal_bond(
        normal_round_index=current_round_index - 1,
        leader_timeout=leader_timeout,
        validators_timeout=validator_timeout,
        round_labels=round_labels,  # Pass round labels
    )
    earned = 0

    for event in fee_events:
        if (
            event.round_index == current_round_index
            and event.round_label is not None
            and "UNSUCCESSFUL" in event.round_label
        ):
            earned += event.earned

    burn = cost - earned
    return burn
