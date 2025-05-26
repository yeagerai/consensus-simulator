import pytest
import itertools
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
from tests.invariant_checks import check_invariants
from tests.unittests.round_combinations import generate_all_paths

# Constants
LEADER_TIMEOUT = 100
VALIDATORS_TIMEOUT = 200
VOTE_TYPES = ["AGREE", "DISAGREE", "TIMEOUT"]
LEADER_ACTIONS = ["LEADER_RECEIPT", "LEADER_TIMEOUT"]

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

# Combined Dependency Graph
combined_graph = {
    "LEADER_RECEIPT": [
        "MAJORITY_AGREE",
        "UNDETERMINED",
        "MAJORITY_DISAGREE",
        "MAJORITY_TIMEOUT",
    ],
    "LEADER_TIMEOUT": ["LEADER_APPEAL"],
    "MAJORITY_AGREE": ["VALIDATOR_APPEAL"],
    "UNDETERMINED": ["LEADER_APPEAL"],
    "MAJORITY_DISAGREE": ["LEADER_APPEAL"],
    "MAJORITY_TIMEOUT": ["VALIDATOR_APPEAL"],
    "VALIDATOR_APPEAL": ["LEADER_RECEIPT", "LEADER_TIMEOUT"],
    "LEADER_APPEAL": ["LEADER_RECEIPT", "LEADER_TIMEOUT"],
}

# Generate all paths
depth = 17
source_nodes = ["LEADER_RECEIPT", "LEADER_TIMEOUT"]
all_paths = generate_all_paths(combined_graph, depth, source_nodes)


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


# Test with all paths (limited to 32 paths for efficiency)
@pytest.mark.parametrize("path", all_paths, ids=lambda x: f"path_{'-'.join(x)}")
def test_paths_with_invariants(verbose, debug, path):
    """
    Test each path from all_paths with check_invariants.
    """
    test_description = f"Testing transaction path: {' -> '.join(path)}. Verifies round labeling, fee distribution, and invariants."

    if verbose:
        display_test_description(
            test_name=f"test_path_{'-'.join(path)}",
            test_description=test_description,
        )

    transaction_results, transaction_budget = path_to_transaction_results(
        path, addresses_pool, VOTE_CONFIGS
    )

    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    if verbose:
        display_summary_table(
            fee_events, transaction_results, transaction_budget, round_labels
        )
        display_transaction_results(transaction_results, round_labels)
    if debug:
        display_fee_distribution(fee_events)

    check_invariants(fee_events, transaction_budget, transaction_results)
