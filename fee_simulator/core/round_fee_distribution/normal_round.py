from typing import List
from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from fee_simulator.types import RoundLabel
from fee_simulator.core.majority import (
    compute_majority,
    who_is_in_vote_majority,
    normalize_vote,
)
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT


def apply_normal_round(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    events = []
    round = transaction_results.rounds[round_index]
    if not round.rotations:
        return events
    votes = round.rotations[-1].votes
    majority = compute_majority(votes)
    if majority == "UNDETERMINED":
        first_addr = next(iter(votes.keys()), None)
        if first_addr:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=first_addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
                    role="LEADER",
                    vote=normalize_vote(votes[first_addr]),
                    hash="0xdefault",  # TODO:Update with actual hash if available
                    cost=0,
                    staked=0,
                    earned=budget.leaderTimeout,
                    slashed=0,
                    burned=0,
                )
            )
            for addr in votes:
                events.append(
                    FeeEvent(
                        sequence_id=event_sequence.next_id(),
                        address=addr,
                        round_index=round_index,
                        round_label="NORMAL_ROUND",
                        role="VALIDATOR",
                        vote=normalize_vote(votes[addr]),
                        hash="0xdefault",
                        cost=0,
                        staked=0,
                        earned=budget.validatorsTimeout,
                        slashed=0,
                        burned=0,
                    )
                )
    else:
        majority_addresses, minority_addresses = who_is_in_vote_majority(
            votes, majority
        )
        for addr in majority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=budget.validatorsTimeout,
                    slashed=0,
                    burned=0,
                )
            )
        for addr in minority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=0,
                    slashed=0,
                    burned=PENALTY_REWARD_COEFFICIENT * budget.validatorsTimeout,
                )
            )
        first_addr = next(iter(votes), None)
        if first_addr:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=first_addr,
                    round_index=round_index,
                    round_label="NORMAL_ROUND",
                    role="LEADER",
                    vote=normalize_vote(votes[first_addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=budget.leaderTimeout,
                    slashed=0,
                    burned=0,
                )
            )
    return events
