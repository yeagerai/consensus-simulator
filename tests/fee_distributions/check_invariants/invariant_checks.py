from fee_simulator.models import FeeEvent, TransactionBudget, TransactionRoundResults
from fee_simulator.fee_aggregators.aggregated import (
    compute_agg_costs,
    compute_agg_earnings,
    compute_agg_burnt,
    compute_agg_appealant_burnt,
)
from fee_simulator.fee_aggregators.address_metrics import (
    compute_total_costs,
    compute_total_earnings,
)
from typing import List
import itertools


def check_costs_equal_earnings(fee_events: List[FeeEvent], tolerance: int = 5) -> None:
    appealant_burnt = compute_agg_appealant_burnt(fee_events)
    assert (
        abs(
            compute_agg_costs(fee_events)
            - compute_agg_earnings(fee_events)
            - appealant_burnt
        )
        < tolerance
    )


def check_party_safety(fee_events: List[FeeEvent], party: List[str]) -> None:
    party_acc_costs = 0
    party_acc_earnings = 0
    for address in party:
        addr_costs = compute_total_costs(fee_events, address)
        addr_earnings = compute_total_earnings(fee_events, address)
        party_acc_costs += addr_costs
        party_acc_earnings += addr_earnings
    assert party_acc_costs >= party_acc_earnings


def check_no_free_burn(fee_events: List[FeeEvent]) -> None:
    # Check that noone can burn more of what is costing
    total_costs = compute_agg_costs(fee_events)
    total_burnt = compute_agg_burnt(fee_events)
    assert total_burnt < total_costs


def all_parties_to_check(
    transaction_results: TransactionRoundResults, max_n_vals: int = 3
) -> List[List[str]]:
    all_validator_addresses = list(
        set(
            [
                addr
                for round in transaction_results.rounds
                for rotation in round.rotations
                for addr in rotation.votes.keys()
            ]
        )
    )
    all_validators_combinations = []
    for i in range(
        1, min(len(all_validator_addresses), max_n_vals)
    ):  # grows exponentially
        all_validators_combinations.extend(
            list(itertools.combinations(all_validator_addresses, i))
        )
    return all_validators_combinations


def check_invariants(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    transaction_results: TransactionRoundResults,
    tolerance: int = 5,
    max_n_vals: int = 3,
) -> None:
    check_costs_equal_earnings(fee_events, tolerance)
    check_no_free_burn(fee_events)
    sender_address = transaction_budget.senderAddress
    appealant_addresses = [
        appeal.appealantAddress for appeal in transaction_budget.appeals
    ]
    initial_party = [sender_address] + appealant_addresses
    all_validators_combinations = all_parties_to_check(transaction_results, max_n_vals)

    for combination in all_validators_combinations:
        party_to_check = initial_party + list(combination)
        check_party_safety(fee_events, party_to_check)
