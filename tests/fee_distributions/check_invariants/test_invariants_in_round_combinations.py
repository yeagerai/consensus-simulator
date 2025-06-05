import pytest
import itertools
import os
from datetime import datetime
from fee_simulator.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
    Appeal,
)
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.utils import generate_random_eth_address

from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT, ROUND_SIZES
from fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
    display_test_description,
)
from tests.fee_distributions.check_invariants.invariant_checks import check_invariants
from tests.round_combinations import generate_all_paths
from tests.round_combinations.path_types import PathConstraints
from tests.round_combinations.graph_data import TRANSACTION_GRAPH

# Constants
LEADER_TIMEOUT = 100
VALIDATORS_TIMEOUT = 200
VOTE_TYPES = ["AGREE", "DISAGREE", "TIMEOUT"]
LEADER_ACTIONS = ["LEADER_RECEIPT", "LEADER_TIMEOUT"]

# Create output directory
OUTPUT_DIR = "test_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Generate addresses
addresses_pool = [generate_random_eth_address() for _ in range(2000)]
sender_address = addresses_pool[1999]
appealant_address = addresses_pool[1998]


# Vote configs (placeholder; adjust as needed)
def get_vote_configs(num_validators):
    return list(
        itertools.islice(itertools.product(VOTE_TYPES, repeat=num_validators), 5)
    )


VOTE_CONFIGS = {
    0: get_vote_configs(4),  # Round 0: 5 participants (4 validators + 1 leader)
    1: get_vote_configs(6),  # Round 1: 7 participants (6 validators + 1 leader)
    2: get_vote_configs(10),  # Round 2: 11 participants (10 validators + 1 leader)
}

# Generate all paths
all_paths = generate_all_paths(
    TRANSACTION_GRAPH,
    PathConstraints(
        min_length=3, max_length=5, source_node="START", target_node="END"
    ),  # not real max length which would be 19
)


def create_rotation(leader_action, votes, round_index, address_offset):
    num_validators = ROUND_SIZES[round_index] - 1
    rotation_votes = {
        addresses_pool[address_offset]: [
            leader_action,
            "AGREE" if leader_action == "LEADER_RECEIPT" else "NA",
        ],
    }
    for i in range(num_validators):
        vote = votes[i] if i < len(votes) else "NA"
        rotation_votes[addresses_pool[address_offset + i + 1]] = vote
    return Rotation(votes=rotation_votes, reserve_votes={})


def path_to_transaction_results(path, addresses_pool, vote_configs):
    rounds = []
    appeal_count = 0
    address_offset = 0

    i = 0
    while i < len(path):
        if path[i] == "LEADER_RECEIPT":
            leader_action = "LEADER_RECEIPT"
            i += 1
            if i >= len(path):
                break
            next_state = path[i]
            if next_state == "MAJORITY_AGREE":
                votes = ["AGREE"] * (ROUND_SIZES[0] - 1)
            elif next_state == "UNDETERMINED":
                votes = ["AGREE"] * ((ROUND_SIZES[0] - 1) // 2) + ["DISAGREE"] * (
                    (ROUND_SIZES[0] - 1) // 2
                )
            elif next_state == "MAJORITY_DISAGREE":
                votes = ["DISAGREE"] * (ROUND_SIZES[0] - 1)
            elif next_state == "MAJORITY_TIMEOUT":
                votes = ["TIMEOUT"] * (ROUND_SIZES[0] - 1)
            else:
                votes = ["NA"] * (ROUND_SIZES[0] - 1)
            rotation = create_rotation(
                leader_action, votes, round_index=0, address_offset=address_offset
            )
            rounds.append(Round(rotations=[rotation]))
            address_offset += ROUND_SIZES[0]

        elif path[i] in ["VALIDATOR_APPEAL", "LEADER_APPEAL"]:
            appeal_count += 1
            round_index = appeal_count
            leader_action = path[i + 1] if i + 1 < len(path) else "LEADER_RECEIPT"
            votes = ["NA"] * (ROUND_SIZES[round_index] - 1)
            rotation = create_rotation(
                leader_action,
                votes,
                round_index=round_index,
                address_offset=address_offset,
            )
            rounds.append(Round(rotations=[rotation]))
            address_offset += ROUND_SIZES[round_index]
            i += 2
            continue

        elif path[i] == "LEADER_TIMEOUT":
            i += 1
            if i >= len(path) or path[i] != "LEADER_APPEAL":
                continue
            appeal_count += 1
            round_index = appeal_count
            leader_action = path[i + 1] if i + 1 < len(path) else "LEADER_RECEIPT"
            votes = ["NA"] * (ROUND_SIZES[round_index] - 1)
            rotation = create_rotation(
                leader_action,
                votes,
                round_index=round_index,
                address_offset=address_offset,
            )
            rounds.append(Round(rotations=[rotation]))
            address_offset += ROUND_SIZES[round_index]
            i += 2
            continue

        i += 1

    appeals = [Appeal(appealantAddress=appealant_address) for _ in range(appeal_count)]
    transaction_budget = TransactionBudget(
        leaderTimeout=LEADER_TIMEOUT,
        validatorsTimeout=VALIDATORS_TIMEOUT,
        appealRounds=appeal_count,
        rotations=[0] * len(rounds),
        senderAddress=sender_address,
        appeals=appeals,
        staking_distribution="constant",
    )

    return TransactionRoundResults(rounds=rounds), transaction_budget


def write_test_output(filename, content):
    """Write test output to a file in the OUTPUT_DIR"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def capture_display_output(func, *args, **kwargs):
    """Capture the output of display functions"""
    import io
    import sys
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        func(*args, **kwargs)
    return f.getvalue()


slice_size = 50


@pytest.mark.parametrize(
    "path",
    list(itertools.islice(all_paths, slice_size)) if all_paths else [],
    ids=lambda x: f"path_{'-'.join(x) if isinstance(x, list) else str(x)}",
)
def test_paths_with_invariants(verbose, debug, path):
    """
    Test each path from all_paths with check_invariants.
    """
    test_description = f"Testing transaction path: {' -> '.join(path)}. Verifies round labeling, fee distribution, and invariants."

    # Initialize output content
    output_content = []
    output_content.append(f"TEST PATH: {' -> '.join(path)}")
    output_content.append(f"Timestamp: {datetime.now().isoformat()}")
    output_content.append("=" * 80)
    output_content.append("")

    success = False
    error_message = ""

    try:
        # Generate transaction results
        transaction_results, transaction_budget = path_to_transaction_results(
            path, addresses_pool, VOTE_CONFIGS
        )

        # Process transaction
        fee_events, round_labels = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=transaction_budget,
        )

        # Capture outputs
        output_content.append("ROUND LABELS:")
        output_content.append(str(round_labels))
        output_content.append("")

        output_content.append("SUMMARY TABLE:")
        summary_output = capture_display_output(
            display_summary_table,
            fee_events,
            transaction_results,
            transaction_budget,
            round_labels,
        )
        output_content.append(summary_output)
        output_content.append("")

        output_content.append("TRANSACTION RESULTS:")
        results_output = capture_display_output(
            display_transaction_results, transaction_results, round_labels
        )
        output_content.append(results_output)
        output_content.append("")

        if debug:
            output_content.append("FEE DISTRIBUTION:")
            fee_output = capture_display_output(display_fee_distribution, fee_events)
            output_content.append(fee_output)
            output_content.append("")

        # Check invariants
        output_content.append("INVARIANT CHECK:")
        try:
            check_invariants(fee_events, transaction_budget, transaction_results)
            output_content.append("✓ All invariants passed")
            success = True
        except AssertionError as e:
            error_message = str(e)
            output_content.append(f"✗ Invariant failed: {error_message}")
            success = False
        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"
            output_content.append(
                f"✗ Unexpected error in invariant check: {error_message}"
            )
            success = False

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}"
        output_content.append(f"✗ Test failed with error: {error_message}")
        import traceback

        output_content.append("")
        output_content.append("TRACEBACK:")
        output_content.append(traceback.format_exc())
        success = False

    # Generate filename
    status_prefix = "S" if success else "F"
    safe_path_name = "_".join(
        path[:3]
    )  # Use first 3 elements to keep filename reasonable
    if len(path) > 3:
        safe_path_name += f"_plus{len(path)-3}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
    filename = f"{status_prefix}_{safe_path_name}_{timestamp}.txt"

    # Write output
    full_content = "\n".join(output_content)
    filepath = write_test_output(filename, full_content)

    # Print summary to console
    status_symbol = "✓" if success else "✗"
    print(f"{status_symbol} {' -> '.join(path)} -> {filepath}")

    # If verbose, also display in console
    if verbose:
        display_test_description(
            test_name=f"test_path_{'-'.join(path)}",
            test_description=test_description,
        )
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)

    if debug:
        display_fee_distribution(fee_events)

    # Re-raise the error to mark test as failed
    if not success:
        pytest.fail(f"Test failed: {error_message}")
