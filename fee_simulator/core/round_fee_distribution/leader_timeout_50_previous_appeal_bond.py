from typing import List
from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
    RoundLabel,
)
from fee_simulator.core.majority import normalize_vote
from fee_simulator.core.bond_computing import compute_appeal_bond
from fee_simulator.utils import is_appeal_round


def apply_leader_timeout_50_previous_appeal_bond(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    events = []
    round = transaction_results.rounds[round_index]
    if (
        not round.rotations
        or not budget.appeals
        or round_index < 1
        or round_index - 1 > len(budget.appeals)
    ):
        return events

    votes = round.rotations[-1].votes
    sender_address = budget.senderAddress
    
    # Find the most recent normal round before the previous round
    # This is used to compute the appeal bond from the previous appeal
    normal_round_index = round_index - 2  # Default
    for i in range(round_index - 1, -1, -1):
        if not is_appeal_round(round_labels[i]):
            normal_round_index = i
            break
    
    appeal_bond = compute_appeal_bond(
        normal_round_index,
        budget.leaderTimeout,
        budget.validatorsTimeout,
        round_labels=round_labels,
    )

    # Award half the appeal bond to the leader
    first_addr = next(iter(votes.keys()), None)
    if first_addr:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=first_addr,
                round_index=round_index,
                round_label="LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
                role="LEADER",
                vote=normalize_vote(votes[first_addr]),
                hash="0xdefault",
                cost=0,
                staked=0,
                earned=appeal_bond / 2,
                slashed=0,
                burned=0,
            )
        )

    # Award half the appeal bond to the sender
    events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=sender_address,
            round_index=round_index,
            round_label="LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            role="SENDER",
            vote="NA",
            hash="0xdefault",
            cost=0,
            staked=0,
            earned=appeal_bond / 2,
            slashed=0,
            burned=0,
        )
    )

    return events
