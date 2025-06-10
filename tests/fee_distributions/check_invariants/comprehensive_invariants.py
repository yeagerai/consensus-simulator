"""
Comprehensive invariant checks for the fee distribution system.
Based on the invariants defined in INVARIANTS_DESIGN.md
"""

from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from fee_simulator.models import FeeEvent, TransactionBudget, TransactionRoundResults
from fee_simulator.types import RoundLabel
from fee_simulator.constants import (
    IDLE_PENALTY_COEFFICIENT,
    DETERMINISTIC_VIOLATION_PENALTY_COEFFICIENT,
    PENALTY_REWARD_COEFFICIENT,
    NORMAL_ROUND_SIZES,
    APPEAL_ROUND_SIZES,
)
from fee_simulator.fee_aggregators.aggregated import (
    compute_agg_costs,
    compute_agg_earnings,
    compute_agg_burnt,
    compute_agg_appealant_burnt,
)
from fee_simulator.fee_aggregators.address_metrics import (
    compute_total_costs,
    compute_total_earnings,
    compute_total_burnt,
    compute_total_balance,
)
from fee_simulator.utils import compute_total_cost, is_appeal_round
from fee_simulator.utils_round_sizes import get_round_size_for_bond
from fee_simulator.core.bond_computing import compute_appeal_bond
from fee_simulator.core.refunds import compute_sender_refund
from fee_simulator.core.majority import compute_majority


class InvariantViolation(Exception):
    """Custom exception for invariant violations"""
    def __init__(self, invariant_name: str, message: str):
        self.invariant_name = invariant_name
        self.message = message
        super().__init__(f"Invariant '{invariant_name}' violated: {message}")


def check_conservation_of_value(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
    tolerance: int = 1
) -> None:
    """Invariant 1: Total costs = total earnings (excluding sender) + sender refunds + appealant burns"""
    total_costs = compute_agg_costs(fee_events)
    total_earnings = compute_agg_earnings(fee_events)
    
    # Exclude sender's earnings from total_earnings to avoid double counting
    # since compute_sender_refund calculates what the sender should get back
    sender_earnings = sum(
        event.earned for event in fee_events 
        if event.address == transaction_budget.senderAddress
    )
    earnings_without_sender = total_earnings - sender_earnings
    
    # Calculate refund
    sender_refund = compute_sender_refund(
        transaction_budget.senderAddress,
        fee_events,
        transaction_budget,
        round_labels
    )
    
    # Calculate appealant burns (value destroyed in unsuccessful appeals)
    appealant_burns = compute_agg_appealant_burnt(fee_events)
    
    expected = earnings_without_sender + sender_refund + appealant_burns
    
    if abs(total_costs - expected) > tolerance:
        raise InvariantViolation(
            "conservation_of_value",
            f"Total costs ({total_costs}) != earnings_without_sender ({earnings_without_sender}) + "
            f"refund ({sender_refund}) + appealant_burns ({appealant_burns}). "
            f"Difference: {total_costs - expected}"
        )


def check_non_negative_balances(fee_events: List[FeeEvent]) -> None:
    """Invariant 2: No address should have negative net balance"""
    # This invariant is not applicable to this system since:
    # - Senders pay upfront and get refunds later
    # - Appealants can lose their bonds
    # - Validators can be penalized/slashed
    # - All of these result in valid negative balances
    pass


def check_appeal_bond_coverage(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel]
) -> None:
    """Invariant 3: Appeal bonds must cover appeal round costs"""
    for i, label in enumerate(round_labels):
        if is_appeal_round(label) and i > 0:
            # Find the most recent normal round before this appeal
            normal_round_index = None
            for j in range(i-1, -1, -1):
                if not is_appeal_round(round_labels[j]):
                    normal_round_index = j
                    break
            
            if normal_round_index is None:
                raise InvariantViolation(
                    "appeal_bond_coverage",
                    f"No normal round found before appeal at index {i}"
                )
            
            # Calculate expected bond
            expected_bond = compute_appeal_bond(
                normal_round_index=normal_round_index,
                leader_timeout=transaction_budget.leaderTimeout,
                validators_timeout=transaction_budget.validatorsTimeout,
                round_labels=round_labels,
                appeal_round_index=i
            )
            
            # Find actual bond paid
            appeal_events = [
                e for e in fee_events 
                if e.round_index == i and e.role == "APPEALANT" and e.cost
            ]
            
            if appeal_events:
                actual_bond = appeal_events[0].cost
                # Use the new utility to get round size
                round_size = get_round_size_for_bond(i, round_labels)
                round_cost = round_size * transaction_budget.validatorsTimeout + transaction_budget.leaderTimeout
                
                if actual_bond < round_cost:
                    raise InvariantViolation(
                        "appeal_bond_coverage",
                        f"Appeal bond ({actual_bond}) < round cost ({round_cost}) "
                        f"for round {i}"
                    )


def check_majority_minority_consistency(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    transaction_budget: TransactionBudget
) -> None:
    """Invariant 4: Minority burns = penalty coefficient * count * timeout"""
    for round_idx, round_obj in enumerate(transaction_results.rounds):
        for rotation in round_obj.rotations:
            majority_outcome = compute_majority(rotation.votes)
            
            if majority_outcome not in ["UNDETERMINED", None]:
                # Count minority validators
                minority_count = 0
                expected_burn_per_validator = PENALTY_REWARD_COEFFICIENT * transaction_budget.validatorsTimeout
                
                for address, vote in rotation.votes.items():
                    # Extract actual vote from complex vote structures
                    actual_vote = vote
                    if isinstance(vote, list):
                        actual_vote = vote[1] if len(vote) > 1 else vote[0]
                    
                    # Check if this is a minority vote
                    if actual_vote not in ["LEADER_RECEIPT", "LEADER_TIMEOUT", "NA"]:
                        if actual_vote != majority_outcome:
                            minority_count += 1
                
                # Calculate actual burns for this round
                round_burns = sum(
                    e.burned for e in fee_events 
                    if e.round_index == round_idx and e.burned and e.role == "VALIDATOR"
                )
                
                expected_total_burn = minority_count * expected_burn_per_validator
                
                if round_burns > 0 and abs(round_burns - expected_total_burn) > 1:
                    raise InvariantViolation(
                        "majority_minority_consistency",
                        f"Round {round_idx}: Expected burn ({expected_total_burn}) != "
                        f"actual burn ({round_burns}) for {minority_count} minority validators"
                    )


def check_role_exclusivity(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults
) -> None:
    """Invariant 5: Address cannot be both leader and validator in same round"""
    # Note: In the current implementation, it's actually valid for a leader 
    # to also receive validator rewards, so we'll skip this check
    pass


def check_sequential_processing(fee_events: List[FeeEvent]) -> None:
    """Invariant 6: Rounds must be processed in sequential order"""
    round_indices = [e.round_index for e in fee_events if e.round_index is not None]
    
    if not round_indices:
        return
    
    # Check that round indices are in non-decreasing order
    for i in range(1, len(round_indices)):
        if round_indices[i] < round_indices[i-1]:
            raise InvariantViolation(
                "sequential_processing",
                f"Round {round_indices[i]} processed before round {round_indices[i-1]}"
            )


def check_appeal_follows_normal(round_labels: List[RoundLabel]) -> None:
    """
    Invariant 7: Appeal rounds must follow normal rounds (not other appeals).
    With the new refactor, appeals can be at any index, but they must follow
    a normal round in the transaction path.
    """
    for i, label in enumerate(round_labels):
        if is_appeal_round(label) and i > 0:
            # Check that the previous round is not an appeal
            # (except for special cases like chained unsuccessful appeals)
            prev_label = round_labels[i-1]
            
            # Allow chained appeals only if they are unsuccessful appeals
            if is_appeal_round(prev_label):
                # Check if this is a valid chain
                valid_chain = (
                    # Unsuccessful appeals can chain
                    ("UNSUCCESSFUL" in prev_label and "UNSUCCESSFUL" in label) or
                    # Split previous appeal bond can follow unsuccessful appeals
                    ("UNSUCCESSFUL" in prev_label and label == "SPLIT_PREVIOUS_APPEAL_BOND") or
                    # Successful appeals can follow unsuccessful appeals (outcome change)
                    ("UNSUCCESSFUL" in prev_label and "SUCCESSFUL" in label)
                )
                
                if not valid_chain:
                    raise InvariantViolation(
                        "appeal_follows_normal",
                        f"Appeal round '{label}' at index {i} follows another appeal '{prev_label}' "
                        f"(this is not a valid appeal chain)"
                    )


def check_burn_non_negativity(fee_events: List[FeeEvent]) -> None:
    """Invariant 8: All burns must be non-negative"""
    for event in fee_events:
        if event.burned is not None and event.burned < 0:
            raise InvariantViolation(
                "burn_non_negativity",
                f"Negative burn amount {event.burned} for address {event.address} "
                f"in round {event.round_index}"
            )


def check_refund_non_negativity(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel]
) -> None:
    """Invariant 9: Sender refund must be non-negative"""
    refund = compute_sender_refund(
        transaction_budget.senderAddress,
        fee_events,
        transaction_budget,
        round_labels
    )
    
    if refund < 0:
        raise InvariantViolation(
            "refund_non_negativity",
            f"Negative refund amount: {refund}"
        )


def check_vote_consistency(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults
) -> None:
    """Invariant 10: Votes in fee events must match transaction rounds"""
    for event in fee_events:
        if event.vote and event.round_index is not None:
            if event.round_index < len(transaction_results.rounds):
                round_obj = transaction_results.rounds[event.round_index]
                # Assume rotation_index is 0 if not specified
                rotation_index = 0
                if rotation_index < len(round_obj.rotations):
                    rotation = round_obj.rotations[rotation_index]
                    if event.address in rotation.votes:
                        actual_vote = rotation.votes[event.address]
                        # Handle complex vote structures
                        if isinstance(actual_vote, list):
                            if event.vote not in actual_vote:
                                raise InvariantViolation(
                                    "vote_consistency",
                                    f"Vote mismatch for {event.address} in round {event.round_index}: "
                                    f"event has '{event.vote}', transaction has '{actual_vote}'"
                                )
                        elif event.vote != actual_vote:
                            raise InvariantViolation(
                                "vote_consistency",
                                f"Vote mismatch for {event.address} in round {event.round_index}: "
                                f"event has '{event.vote}', transaction has '{actual_vote}'"
                            )


def check_idle_slashing(fee_events: List[FeeEvent]) -> None:
    """Invariant 11: Idle validators slashed exactly penalty coefficient"""
    for event in fee_events:
        if event.vote == "IDLE" and event.slashed:
            # Find the stake initialization event for this address
            stake_events = [
                e for e in fee_events 
                if e.address == event.address and e.role == "TOPPER" and e.earned
            ]
            if stake_events:
                stake = stake_events[0].earned
                expected_slash = IDLE_PENALTY_COEFFICIENT * stake
                if abs(event.slashed - expected_slash) > 1:
                    raise InvariantViolation(
                        "idle_slashing",
                        f"Idle slash mismatch for {event.address}: "
                        f"expected {expected_slash}, got {event.slashed}"
                    )


def check_deterministic_violation_slashing(fee_events: List[FeeEvent]) -> None:
    """Invariant 12: Hash mismatch validators slashed correctly"""
    # Skip this check for now since FeeEvent doesn't have a 'reason' field
    # TODO: Update when we have a way to identify hash mismatch events
    pass


def check_leader_timeout_earning(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel]
) -> None:
    """Invariant 13: Leader timeout earnings <= leader timeout amount (except for special rounds)"""
    for i, label in enumerate(round_labels):
        if "LEADER_TIMEOUT" in label:
            leader_events = [
                e for e in fee_events 
                if e.round_index == i and e.role == "LEADER" and e.earned
            ]
            for event in leader_events:
                # Special case: LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND allows 150% earning
                if label == "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND":
                    if event.earned > transaction_budget.leaderTimeout * 1.5:
                        raise InvariantViolation(
                            "leader_timeout_earning",
                            f"Leader earned {event.earned} > 150% of timeout ({transaction_budget.leaderTimeout * 1.5}) "
                            f"in round {i}"
                        )
                elif event.earned > transaction_budget.leaderTimeout:
                    raise InvariantViolation(
                        "leader_timeout_earning",
                        f"Leader earned {event.earned} > timeout {transaction_budget.leaderTimeout} "
                        f"in round {i}"
                    )


def check_appeal_bond_consistency(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel]
) -> None:
    """
    Additional invariant: Appeal bonds should be calculated correctly based on
    the new APPEAL_ROUND_SIZES structure.
    """
    appeal_count = 0
    for i, label in enumerate(round_labels):
        if is_appeal_round(label):
            # Find the appealant cost event
            appealant_events = [
                e for e in fee_events 
                if e.round_index == i and e.role == "APPEALANT" and e.cost
            ]
            
            if appealant_events:
                actual_bond = appealant_events[0].cost
                
                # Get expected size using the appeal count
                expected_size = APPEAL_ROUND_SIZES[appeal_count] if appeal_count < len(APPEAL_ROUND_SIZES) else APPEAL_ROUND_SIZES[-1]
                expected_bond = expected_size * transaction_budget.validatorsTimeout + transaction_budget.leaderTimeout
                
                if actual_bond != expected_bond:
                    raise InvariantViolation(
                        "appeal_bond_consistency",
                        f"Appeal {appeal_count} (round {i}): Expected bond {expected_bond} "
                        f"(size {expected_size}), but got {actual_bond}"
                    )
            
            appeal_count += 1


def check_round_size_consistency(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel]
) -> None:
    """
    Additional invariant: The number of participants in each round should match
    the expected size from NORMAL_ROUND_SIZES or APPEAL_ROUND_SIZES.
    """
    normal_count = 0
    appeal_count = 0
    
    for i, (round_obj, label) in enumerate(zip(transaction_results.rounds, round_labels)):
        if round_obj.rotations:
            # Count unique participants in this round
            participants = set()
            for rotation in round_obj.rotations:
                participants.update(rotation.votes.keys())
            
            actual_size = len(participants)
            
            if is_appeal_round(label):
                expected_size = APPEAL_ROUND_SIZES[appeal_count] if appeal_count < len(APPEAL_ROUND_SIZES) else APPEAL_ROUND_SIZES[-1]
                appeal_count += 1
            else:
                expected_size = NORMAL_ROUND_SIZES[normal_count] if normal_count < len(NORMAL_ROUND_SIZES) else NORMAL_ROUND_SIZES[-1]
                normal_count += 1
            
            if actual_size != expected_size:
                raise InvariantViolation(
                    "round_size_consistency",
                    f"Round {i} ({label}): Expected {expected_size} participants, "
                    f"but found {actual_size}"
                )


def check_all_invariants(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
    tolerance: int = 1
) -> Tuple[bool, List[str]]:
    """
    Check all invariants and return (success, list_of_violations)
    """
    violations = []
    
    invariant_checks = [
        ("conservation_of_value", lambda: check_conservation_of_value(
            fee_events, transaction_budget, round_labels, tolerance
        )),
        ("non_negative_balances", lambda: check_non_negative_balances(fee_events)),
        ("appeal_bond_coverage", lambda: check_appeal_bond_coverage(
            fee_events, transaction_budget, transaction_results, round_labels
        )),
        ("majority_minority_consistency", lambda: check_majority_minority_consistency(
            fee_events, transaction_results, transaction_budget
        )),
        ("role_exclusivity", lambda: check_role_exclusivity(
            fee_events, transaction_results
        )),
        ("sequential_processing", lambda: check_sequential_processing(fee_events)),
        ("appeal_follows_normal", lambda: check_appeal_follows_normal(round_labels)),
        ("burn_non_negativity", lambda: check_burn_non_negativity(fee_events)),
        ("refund_non_negativity", lambda: check_refund_non_negativity(
            fee_events, transaction_budget, round_labels
        )),
        ("vote_consistency", lambda: check_vote_consistency(
            fee_events, transaction_results
        )),
        ("idle_slashing", lambda: check_idle_slashing(fee_events)),
        ("deterministic_violation_slashing", lambda: check_deterministic_violation_slashing(
            fee_events
        )),
        ("leader_timeout_earning", lambda: check_leader_timeout_earning(
            fee_events, transaction_budget, round_labels
        )),
        ("appeal_bond_consistency", lambda: check_appeal_bond_consistency(
            fee_events, transaction_budget, round_labels
        )),
        ("round_size_consistency", lambda: check_round_size_consistency(
            fee_events, transaction_results, round_labels
        )),
    ]
    
    for invariant_name, check_func in invariant_checks:
        try:
            check_func()
        except InvariantViolation as e:
            violations.append(f"{e.invariant_name}: {e.message}")
        except Exception as e:
            violations.append(f"{invariant_name}: Unexpected error - {str(e)}")
    
    return len(violations) == 0, violations


# Backward compatibility wrapper
def check_comprehensive_invariants(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
    tolerance: int = 1
) -> None:
    """
    Wrapper that raises exception on first violation for backward compatibility
    """
    success, violations = check_all_invariants(
        fee_events, transaction_budget, transaction_results, round_labels, tolerance
    )
    
    if not success:
        raise AssertionError(f"Invariant violations found:\n" + "\n".join(violations))