import random
import string
import hashlib
from typing import Union
from decimal import Decimal, ROUND_DOWN
from typing import List
from fee_simulator.models import (
    FeeEvent,
    TransactionBudget,
    EventSequence,
)
from fee_simulator.constants import (
    ROUND_SIZES,
    DEFAULT_STAKE,
)
from fee_simulator.types import RoundLabel


def generate_random_eth_address() -> str:
    seed = "".join(random.choices(string.ascii_letters + string.digits, k=32))
    hashed = hashlib.sha256(seed.encode()).hexdigest()
    return "0x" + hashed[:40]


def initialize_constant_stakes(
    event_sequence: EventSequence, addresses: List[str]
) -> List[FeeEvent]:
    events = []
    for addr in addresses:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=addr,
                staked=DEFAULT_STAKE,
            )
        )
    return events


def compute_total_cost(transaction_budget: TransactionBudget) -> int:
    max_round_price = 0
    max_appealant_reward = (
        transaction_budget.appealRounds * transaction_budget.leaderTimeout
    )
    num_rounds = transaction_budget.appealRounds * 2 + 1
    for i in range(num_rounds):
        if i % 2 == 0:
            max_round_price += (
                ROUND_SIZES[i]
                * (transaction_budget.rotations[i // 2] + 1)
                * transaction_budget.validatorsTimeout
                + transaction_budget.leaderTimeout
            )
        else:
            max_round_price += (
                ROUND_SIZES[i] * transaction_budget.validatorsTimeout
                + transaction_budget.leaderTimeout
            )
    total_cost = max_appealant_reward + max_round_price
    return total_cost


def to_wei(value: Union[int, float, str, Decimal], decimals: int = 18) -> int:
    try:
        d = Decimal(str(value))
        return int(d * (10**decimals))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot convert {value} to Wei: {e}")


def from_wei(value: int, decimals: int = 18) -> Decimal:
    return Decimal(value) / (10**decimals)


def split_amount(amount: int, num_recipients: int, decimals: int = 18) -> int:
    if num_recipients == 0:
        raise ValueError("Number of recipients cannot be zero")

    d_amount = from_wei(amount, decimals)
    per_recipient = (d_amount / num_recipients).quantize(
        Decimal("0." + "0" * (decimals - 1) + "1"), rounding=ROUND_DOWN
    )
    return to_wei(per_recipient, decimals)


def compute_round_size_indices(round_types: List[RoundLabel]) -> List[int]:
    if not round_types:
        return []

    indices = []
    next_normal_index = 0
    consecutive_appeals = 0

    for round_type in round_types:
        is_appeal = is_appeal_round(round_type)

        if is_appeal:
            consecutive_appeals += 1
            # First appeal uses the odd index after the last normal
            # Subsequent appeals skip even indices
            appeal_index = next_normal_index + (2 * consecutive_appeals - 1)
            indices.append(appeal_index)
        else:
            # Normal round resets the appeal counter
            consecutive_appeals = 0
            indices.append(next_normal_index)
            next_normal_index += 2

    return indices


def get_round_size(round_index: int, round_types: List[RoundLabel]) -> int:
    indices = compute_round_size_indices(round_types)

    if round_index >= len(indices):
        raise IndexError(
            f"Round index {round_index} out of bounds for {len(round_types)} rounds"
        )

    size_index = indices[round_index]

    if size_index >= len(ROUND_SIZES):
        # Handle case where we've exhausted predefined sizes
        return ROUND_SIZES[-1]  # Use the largest available size

    return ROUND_SIZES[size_index]


def is_appeal_round(round_label: RoundLabel) -> bool:
    return round_label.startswith("APPEAL_")
