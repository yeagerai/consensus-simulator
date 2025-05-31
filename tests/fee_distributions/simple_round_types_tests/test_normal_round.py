from fee_simulator.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
)
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.utils import compute_total_cost, generate_random_eth_address
from fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
    display_test_description,
)
from fee_simulator.fee_aggregators.address_metrics import (
    compute_all_zeros,
    compute_total_costs,
    compute_total_earnings,
    compute_total_burnt,
    compute_total_balance,
)
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT
from tests.invariant_checks import check_invariants

leaderTimeout = 100
validatorsTimeout = 200

addresses_pool = [generate_random_eth_address() for _ in range(2000)]

default_budget = TransactionBudget(
    leaderTimeout=leaderTimeout,
    validatorsTimeout=validatorsTimeout,
    appealRounds=0,
    rotations=[0],
    senderAddress=addresses_pool[1999],
    appeals=[],
    staking_distribution="constant",
)


def test_normal_round(verbose, debug):
    """Test fee distribution for a normal round with all validators agreeing."""
    # Setup
    rotation = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "AGREE",
            addresses_pool[4]: "AGREE",
        }
    )
    round = Round(rotations=[rotation])
    transaction_results = TransactionRoundResults(rounds=[round])
    transaction_budget = default_budget
    # Note: initialize_constant_stakes is called within process_transaction, no need to call it separately

    # Execute
    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round",
            test_description="This test verifies the fee distribution for a normal round with all validators agreeing. It sets up a round with a majority agreement, and verifies that the leader earns the leader timeout plus validator timeout, validators earn the validator timeout, and the sender's costs match the total transaction cost.",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "NORMAL_ROUND"
    ], f"Expected ['NORMAL_ROUND'], got {round_labels}"

    # Invariant Check
    check_invariants(fee_events, transaction_budget, transaction_results)

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), "Leader should have 100 (leader) + 200 (validator)"

    # Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [1, 2, 3, 4]
    ), "Validator should have 200"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, default_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 1999]
    ), "Everyone else should have no fees in normal round"


def test_normal_round_with_minority_penalties(verbose, debug):
    """Test normal round with penalties for validators in the minority (3 Agree, 1 Disagree, 1 Timeout)."""
    # Setup
    rotation = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],  # Majority
            addresses_pool[1]: "AGREE",  # Majority
            addresses_pool[2]: "AGREE",  # Majority
            addresses_pool[3]: "DISAGREE",  # Minority
            addresses_pool[4]: "TIMEOUT",  # Minority
        }
    )
    round = Round(rotations=[rotation])
    transaction_results = TransactionRoundResults(rounds=[round])
    transaction_budget = default_budget

    # Execute
    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round_with_minority_penalties",
            test_description="This test verifies the fee distribution for a normal round with penalties for validators in the minority (3 Agree, 1 Disagree, 1 Timeout).",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "NORMAL_ROUND"
    ], f"Expected ['NORMAL_ROUND'], got {round_labels}"

    # Invariant Check
    check_invariants(fee_events, transaction_budget, transaction_results)

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), "Leader should have 100 (leader) + 200 (validator)"

    # Majority Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [1, 2]
    ), "Validators in majority should have 200"

    # Minority Validator Fees Assert
    assert all(
        compute_total_burnt(fee_events, addresses_pool[i])
        == PENALTY_REWARD_COEFFICIENT * validatorsTimeout
        for i in [3, 4]
    ), "Validators in minority should have burned 200"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, default_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"

    # Sender Total Balance Assert
    total_balance = compute_total_balance(fee_events, default_budget.senderAddress)
    assert (
        -leaderTimeout - 3 * validatorsTimeout == total_balance
    ), f"Sender should have been refunded and thus have a balance of: {-leaderTimeout - 3*validatorsTimeout}"

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 1999]
    ), "Everyone else should have no fees in normal round"


def test_normal_round_no_majority(verbose, debug):
    """Test normal round with no majority (2 Agree, 2 Disagree, 1 Timeout)."""
    # Setup
    rotation = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],  # No majority
            addresses_pool[1]: "AGREE",  # No majority
            addresses_pool[2]: "DISAGREE",  # No majority
            addresses_pool[3]: "DISAGREE",  # No majority
            addresses_pool[4]: "TIMEOUT",  # No majority
        }
    )
    round = Round(rotations=[rotation])
    transaction_results = TransactionRoundResults(rounds=[round])
    transaction_budget = default_budget

    # Execute
    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round_no_majority",
            test_description="This test verifies the fee distribution for a normal round with no majority (2 Agree, 2 Disagree, 1 Timeout).",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "NORMAL_ROUND"
    ], f"Expected ['NORMAL_ROUND'], got {round_labels}"

    # Invariant Check
    check_invariants(fee_events, transaction_budget, transaction_results)

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0])
        == leaderTimeout + validatorsTimeout
    ), "Leader should have 100 (leader) + 200 (validator)"

    # Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [1, 2, 3, 4]
    ), "Validators should have 200 due to no majority"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, default_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 1999]
    ), "Everyone else should have no fees in normal round"


def test_normal_round_majority_disagree(verbose, debug):
    """Test normal round with majority DISAGREE (2 Agree, 3 Disagree)."""
    # Setup
    rotation = Rotation(
        votes={
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],  # No majority
            addresses_pool[1]: "AGREE",  # No majority
            addresses_pool[2]: "DISAGREE",  # No majority
            addresses_pool[3]: "DISAGREE",  # No majority
            addresses_pool[4]: "DISAGREE",  # No majority
        }
    )
    round = Round(rotations=[rotation])
    transaction_results = TransactionRoundResults(rounds=[round])
    transaction_budget = default_budget

    # Execute
    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Print if verbose
    if verbose:
        display_test_description(
            test_name="test_normal_round_majority_disagree",
            test_description="This test verifies the fee distribution for a normal round with majority DISAGREE (2 Agree, 3 Disagree).",
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Round Label Assert
    assert round_labels == [
        "NORMAL_ROUND"
    ], f"Expected ['NORMAL_ROUND'], got {round_labels}"

    # Invariant Check
    check_invariants(fee_events, transaction_budget, transaction_results)

    # Leader Fees Assert
    assert (
        compute_total_earnings(fee_events, addresses_pool[0]) == leaderTimeout
    ), "Leader should have 100 (leader)"

    # Validator Fees Assert
    assert all(
        compute_total_earnings(fee_events, addresses_pool[i]) == validatorsTimeout
        for i in [2, 3, 4]
    ), "Validators should have 200 due to majority disagree"

    assert all(
        compute_total_burnt(fee_events, addresses_pool[i])
        == PENALTY_REWARD_COEFFICIENT * validatorsTimeout
        for i in [0, 1]
    ), "Validators should have 200 due to majority disagree"

    # Sender Fees Assert
    total_cost = compute_total_cost(transaction_budget)
    assert (
        compute_total_costs(fee_events, default_budget.senderAddress) == total_cost
    ), f"Sender should have costs equal to total transaction cost: {total_cost}"

    # Everyone Else 0 Fees Assert
    assert all(
        compute_all_zeros(fee_events, addresses_pool[i])
        for i in range(len(addresses_pool))
        if i not in [0, 1, 2, 3, 4, 1999]
    ), "Everyone else should have no fees in normal round"
