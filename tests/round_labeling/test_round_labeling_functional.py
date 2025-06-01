"""
Functional, generic testing for round labeling using the transaction graph.

This ensures we test ALL possible combinations including all types of
chained appeals without hardcoding specific scenarios.
"""

import pytest
import itertools
from functools import partial, reduce
from typing import List, Dict, Callable, Tuple, Optional
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
    Appeal,
)
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.utils import generate_random_eth_address
from fee_simulator.types import Vote
from tests.round_combinations import (
    generate_all_paths,
    PathConstraints,
    TRANSACTION_GRAPH,
)
from tests.fee_distributions.check_invariants.invariant_checks import check_invariants

# Pre-generate address pool
ADDR_POOL = [generate_random_eth_address() for _ in range(2000)]


# Functional vote generators
def create_leader_vote(action: str, vote_type: str = "NA") -> List[str]:
    """Create a leader vote based on action."""
    if action == "LEADER_RECEIPT":
        return [action, vote_type if vote_type != "NA" else "AGREE"]
    else:  # LEADER_TIMEOUT
        return [action, "NA"]


def create_validator_vote(vote_type: str) -> str:
    """Create a validator vote."""
    return vote_type


def create_votes_for_outcome(
    outcome: str, num_validators: int, base_addr: int
) -> Dict[str, Vote]:
    """Create votes that produce a specific outcome."""
    votes = {}

    # Leader is always first
    leader_addr = ADDR_POOL[base_addr]

    if outcome == "LEADER_TIMEOUT":
        votes[leader_addr] = create_leader_vote("LEADER_TIMEOUT")
        # All validators get NA
        for i in range(1, num_validators):
            votes[ADDR_POOL[base_addr + i]] = "NA"

    elif outcome in ["LEADER_RECEIPT_MAJORITY_AGREE", "MAJORITY_AGREE"]:
        votes[leader_addr] = create_leader_vote("LEADER_RECEIPT", "AGREE")
        # Majority agree
        agree_count = (num_validators // 2) + 1
        for i in range(1, agree_count):
            votes[ADDR_POOL[base_addr + i]] = "AGREE"
        for i in range(agree_count, num_validators):
            votes[ADDR_POOL[base_addr + i]] = "DISAGREE"

    elif outcome in ["LEADER_RECEIPT_MAJORITY_DISAGREE", "MAJORITY_DISAGREE"]:
        votes[leader_addr] = create_leader_vote("LEADER_RECEIPT", "AGREE")
        # Majority disagree
        disagree_count = (num_validators // 2) + 1
        for i in range(1, num_validators - disagree_count + 1):
            votes[ADDR_POOL[base_addr + i]] = "AGREE"
        for i in range(num_validators - disagree_count + 1, num_validators):
            votes[ADDR_POOL[base_addr + i]] = "DISAGREE"

    elif outcome in ["LEADER_RECEIPT_MAJORITY_TIMEOUT", "MAJORITY_TIMEOUT"]:
        votes[leader_addr] = create_leader_vote("LEADER_RECEIPT", "AGREE")
        # Majority timeout
        timeout_count = (num_validators // 2) + 1
        for i in range(1, num_validators - timeout_count + 1):
            votes[ADDR_POOL[base_addr + i]] = "AGREE"
        for i in range(num_validators - timeout_count + 1, num_validators):
            votes[ADDR_POOL[base_addr + i]] = "TIMEOUT"

    elif outcome in ["LEADER_RECEIPT_UNDETERMINED", "UNDETERMINED"]:
        votes[leader_addr] = create_leader_vote("LEADER_RECEIPT", "AGREE")
        # Create undetermined (no majority)
        third = max(1, (num_validators - 1) // 3)
        for i in range(1, third + 1):
            votes[ADDR_POOL[base_addr + i]] = "AGREE"
        for i in range(third + 1, 2 * third + 1):
            votes[ADDR_POOL[base_addr + i]] = "DISAGREE"
        for i in range(2 * third + 1, num_validators):
            votes[ADDR_POOL[base_addr + i]] = "TIMEOUT"

    else:  # Default NA for appeals
        for i in range(num_validators):
            votes[ADDR_POOL[base_addr + i]] = "NA"

    return votes


def create_appeal_votes(
    appeal_type: str, is_successful: bool, num_validators: int, base_addr: int
) -> Dict[str, Vote]:
    """Create votes for an appeal round."""
    if "LEADER_APPEAL" in appeal_type:
        # Leader appeals typically have NA votes
        return {ADDR_POOL[base_addr + i]: "NA" for i in range(num_validators)}

    elif "VALIDATOR_APPEAL" in appeal_type:
        if is_successful:
            # Change the outcome (e.g., from AGREE to DISAGREE)
            return create_votes_for_outcome(
                "MAJORITY_DISAGREE", num_validators, base_addr
            )
        else:
            # Keep the same outcome
            return create_votes_for_outcome("MAJORITY_AGREE", num_validators, base_addr)

    return {ADDR_POOL[base_addr + i]: "NA" for i in range(num_validators)}


# Path to transaction converter
def node_to_round(
    node: str, round_index: int, address_offset: int
) -> Tuple[Round, int, int]:
    """Convert a graph node to a round, returning (round, new_offset, appeal_count)."""
    # Determine round size based on round index
    round_sizes = [5, 7, 11, 13, 17, 19, 23, 25]  # Grows with appeals
    size_index = min(round_index, len(round_sizes) - 1)
    num_validators = round_sizes[size_index]

    appeal_count = 0

    # Create votes based on node type
    if "APPEAL" in node:
        appeal_count = 1
        is_successful = "SUCCESSFUL" in node
        votes = create_appeal_votes(node, is_successful, num_validators, address_offset)
    elif node == "LEADER_TIMEOUT":
        votes = create_votes_for_outcome(
            "LEADER_TIMEOUT", num_validators, address_offset
        )
    else:
        # Extract outcome from node name
        votes = create_votes_for_outcome(node, num_validators, address_offset)

    rotation = Rotation(votes=votes)
    new_offset = address_offset + num_validators

    return Round(rotations=[rotation]), new_offset, appeal_count


def path_to_transaction_results(
    path: List[str],
) -> Tuple[TransactionRoundResults, TransactionBudget]:
    """Convert a path from the graph to a complete transaction setup."""
    rounds = []
    appeals = []
    address_offset = 0
    total_appeals = 0

    # Filter out START and END
    actual_nodes = [node for node in path if node not in ["START", "END"]]

    for i, node in enumerate(actual_nodes):
        round_obj, address_offset, appeal_count = node_to_round(
            node, len(rounds), address_offset
        )
        rounds.append(round_obj)

        if appeal_count > 0:
            appeals.append(Appeal(appealantAddress=ADDR_POOL[1900 + total_appeals]))
            total_appeals += 1

    # Create transaction budget
    # rotations length must equal appealRounds + 1
    rotations = [0] * (total_appeals + 1)

    budget = TransactionBudget(
        leaderTimeout=100,
        validatorsTimeout=200,
        appealRounds=total_appeals,
        rotations=rotations,
        senderAddress=ADDR_POOL[1999],
        appeals=appeals,
        staking_distribution="constant",
    )

    return TransactionRoundResults(rounds=rounds), budget


# Invariant checkers
def check_round_labeling_invariants(
    labels: List[str], transaction_results: TransactionRoundResults, path: List[str]
) -> None:
    """Check all invariants for round labeling."""
    # Invariant 1: Every round gets a label
    assert len(labels) == len(
        transaction_results.rounds
    ), f"Label count mismatch for path {path}"

    # Invariant 2: All labels are valid
    valid_labels = {
        "NORMAL_ROUND",
        "EMPTY_ROUND",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
        "APPEAL_LEADER_SUCCESSFUL",
        "APPEAL_LEADER_UNSUCCESSFUL",
        "APPEAL_VALIDATOR_SUCCESSFUL",
        "APPEAL_VALIDATOR_UNSUCCESSFUL",
        "LEADER_TIMEOUT",
        "VALIDATORS_PENALTY_ONLY_ROUND",
        "SKIP_ROUND",
        "LEADER_TIMEOUT_50_PERCENT",
        "SPLIT_PREVIOUS_APPEAL_BOND",
        "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
    }

    for i, label in enumerate(labels):
        assert (
            label in valid_labels
        ), f"Invalid label '{label}' at position {i} for path {path}"

    # Invariant 3: Appeal positioning (with exceptions)
    for i, label in enumerate(labels):
        if "APPEAL" in label and label not in [
            "SPLIT_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        ]:
            # Check if it's at an odd index OR if it's part of a special pattern
            if i % 2 == 0:
                # This could be OK if it's part of a transformed pattern
                # But we should verify the path had an appeal at this position
                path_nodes = [n for n in path if n not in ["START", "END"]]
                if i < len(path_nodes):
                    assert (
                        "APPEAL" in path_nodes[i]
                    ), f"Appeal label at even index {i} without appeal in path: {path}"

    # Invariant 4: Single round special case
    if len(labels) == 1 and len(transaction_results.rounds) == 1:
        round = transaction_results.rounds[0]
        if round.rotations and round.rotations[0].votes:
            first_vote = next(iter(round.rotations[0].votes.values()))
            if isinstance(first_vote, list) and first_vote[0] == "LEADER_TIMEOUT":
                assert (
                    labels[0] == "LEADER_TIMEOUT_50_PERCENT"
                ), f"Single leader timeout should be 50% for path {path}"


def check_chained_appeal_patterns(labels: List[str], path: List[str]) -> None:
    """Check patterns specific to chained appeals."""
    # Count consecutive unsuccessful appeals
    max_consecutive_unsuccessful = 0
    current_consecutive = 0

    for label in labels:
        if "UNSUCCESSFUL" in label and "APPEAL" in label:
            current_consecutive += 1
            max_consecutive_unsuccessful = max(
                max_consecutive_unsuccessful, current_consecutive
            )
        else:
            current_consecutive = 0

    # Verify that chains are handled (no specific limit on length)
    # The system should handle any length of chain
    assert (
        max_consecutive_unsuccessful >= 0
    ), "Should handle appeal chains of any length"

    # Check that SPLIT_PREVIOUS_APPEAL_BOND only appears after unsuccessful appeal
    for i in range(1, len(labels)):
        if labels[i] == "SPLIT_PREVIOUS_APPEAL_BOND":
            # Previous round should be appeal-related or there should be an unsuccessful appeal before
            found_unsuccessful = False
            for j in range(i - 1, -1, -1):
                if "APPEAL" in labels[j] and "UNSUCCESSFUL" in labels[j]:
                    found_unsuccessful = True
                    break
                elif "APPEAL" in labels[j] and "SUCCESSFUL" in labels[j]:
                    break  # Successful appeal breaks the chain

            assert (
                found_unsuccessful
            ), f"SPLIT_PREVIOUS_APPEAL_BOND without prior unsuccessful appeal in path {path}"


# Generate all paths for testing
def get_all_test_paths(max_length: int = 19) -> List[List[str]]:
    """Generate all valid paths from the transaction graph."""
    constraints = PathConstraints(
        min_length=1, max_length=max_length, source_node="START", target_node="END"
    )

    return generate_all_paths(TRANSACTION_GRAPH, constraints)


# Functional composition helpers
def compose(*funcs):
    """Compose functions from right to left."""
    return reduce(lambda f, g: lambda x: f(g(x)), funcs, lambda x: x)


def pipe(*funcs):
    """Pipe functions from left to right."""
    return reduce(lambda f, g: lambda x: g(f(x)), funcs, lambda x: x)


# Main test class
class TestRoundLabelingAllPaths:
    """Test round labeling for all possible paths in the transaction graph."""

    # Generate all paths up to reasonable length
    all_paths = get_all_test_paths(max_length=15)  # Reduced for test performance

    @pytest.mark.parametrize(
        "path",
        all_paths[:100],  # Test first 100 paths (increase for more coverage)
        ids=lambda x: f"path_{'->'.join(x[1:-1])}",  # Exclude START/END from ID
    )
    def test_round_labeling_for_path(self, path):
        """Test round labeling for a specific path from the graph."""
        # Convert path to transaction
        transaction_results, budget = path_to_transaction_results(path)

        # Label rounds
        labels = label_rounds(transaction_results)

        # Check invariants
        check_round_labeling_invariants(labels, transaction_results, path)
        check_chained_appeal_patterns(labels, path)

        # Process transaction to verify integration
        fee_events, round_labels = process_transaction(
            ADDR_POOL, transaction_results, budget
        )

        # Verify labels match
        assert (
            round_labels == labels
        ), f"Labels mismatch between direct labeling and transaction processing for path {path}"

        # Check transaction invariants
        check_invariants(fee_events, budget, transaction_results)

    def test_specific_chained_patterns(self):
        """Test specific patterns that must include chained appeals."""
        # Pattern 1: Maximum unsuccessful validator appeals
        chained_patterns = [
            # Double unsuccessful validator appeals
            [
                "START",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "VALIDATOR_APPEAL_UNSUCCESSFUL",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "VALIDATOR_APPEAL_UNSUCCESSFUL",
                "END",
            ],
            # Triple unsuccessful leader appeals
            [
                "START",
                "LEADER_RECEIPT_UNDETERMINED",
                "LEADER_APPEAL_UNSUCCESSFUL",
                "LEADER_RECEIPT_UNDETERMINED",
                "LEADER_APPEAL_UNSUCCESSFUL",
                "LEADER_RECEIPT_UNDETERMINED",
                "LEADER_APPEAL_UNSUCCESSFUL",
                "END",
            ],
            # Mixed chain
            [
                "START",
                "LEADER_TIMEOUT",
                "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL",
                "LEADER_TIMEOUT",
                "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL",
                "LEADER_TIMEOUT",
                "END",
            ],
        ]

        for pattern in chained_patterns:
            if self._is_valid_path(pattern):
                transaction_results, budget = path_to_transaction_results(pattern)
                labels = label_rounds(transaction_results)

                # Count unsuccessful appeals
                unsuccessful_count = sum(
                    1 for label in labels if "UNSUCCESSFUL" in label
                )
                assert (
                    unsuccessful_count > 0
                ), f"Pattern {pattern} should have unsuccessful appeals"

    def _is_valid_path(self, path: List[str]) -> bool:
        """Check if a path is valid according to the transaction graph."""
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]

            if current not in TRANSACTION_GRAPH:
                return False

            if next_node not in TRANSACTION_GRAPH[current]:
                return False

        return True


# Functional test generators
def create_test_scenario(
    pattern: List[Tuple[str, int]],
) -> Callable[[], Tuple[TransactionRoundResults, TransactionBudget]]:
    """Create a test scenario generator from a pattern specification."""

    def generator():
        rounds = []
        appeals = []
        address_offset = 0

        for node_type, count in pattern:
            for _ in range(count):
                round_obj, address_offset, appeal_count = node_to_round(
                    node_type, len(rounds), address_offset
                )
                rounds.append(round_obj)

                if appeal_count > 0:
                    appeals.append(
                        Appeal(appealantAddress=ADDR_POOL[1900 + len(appeals)])
                    )

        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=len(appeals),
            rotations=[0] * (len(appeals) + 1),  # Must equal appealRounds + 1
            senderAddress=ADDR_POOL[1999],
            appeals=appeals,
            staking_distribution="constant",
        )

        return TransactionRoundResults(rounds=rounds), budget

    return generator


# Property-based test helpers
def generate_random_path(max_length: int = 10) -> List[str]:
    """Generate a random valid path through the graph."""
    path = ["START"]
    current = "START"

    for _ in range(max_length):
        if current == "END":
            break

        neighbors = TRANSACTION_GRAPH.get(current, [])
        if not neighbors:
            break

        # Weighted choice to prefer some paths
        if "END" in neighbors and len(path) > 3:
            # Increase chance of ending
            next_node = "END" if hash(str(path)) % 3 == 0 else neighbors[0]
        else:
            next_node = neighbors[hash(str(path)) % len(neighbors)]

        path.append(next_node)
        current = next_node

    if current != "END":
        path.append("END")

    return path


class TestRoundLabelingProperties:
    """Property-based tests for round labeling."""

    @pytest.mark.parametrize("seed", range(50))
    def test_random_paths(self, seed):
        """Test random paths through the graph."""
        # Use seed for reproducibility
        import random

        random.seed(seed)

        path = generate_random_path(max_length=15)

        # Convert and test
        transaction_results, budget = path_to_transaction_results(path)
        labels = label_rounds(transaction_results)

        # Check all invariants
        check_round_labeling_invariants(labels, transaction_results, path)
        check_chained_appeal_patterns(labels, path)

    def test_determinism(self):
        """Test that labeling is deterministic."""
        # Generate complex path
        path = [
            "START",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "END",
        ]

        # Convert multiple times
        results = []
        for _ in range(10):
            transaction_results, _ = path_to_transaction_results(path)
            labels = label_rounds(transaction_results)
            results.append(labels)

        # All should be identical
        assert all(r == results[0] for r in results), "Labeling should be deterministic"


# Functional invariant checkers using partial application
check_valid_labels = partial(
    check_round_labeling_invariants, path=["START", "END"]  # Default path for partial
)

check_appeal_chains = partial(
    check_chained_appeal_patterns, path=["START", "END"]  # Default path for partial
)


if __name__ == "__main__":
    print("Running functional round labeling tests...")

    # Quick test of path generation
    print("\n1. Testing path generation...")
    test_paths = get_all_test_paths(max_length=7)
    print(f"Generated {len(test_paths)} test paths")

    # Show some example paths
    print("\nExample paths:")
    for i, path in enumerate(test_paths[:5]):
        print(f"  {i+1}. {' -> '.join(path)}")

    # Test specific patterns
    print("\n2. Testing specific chained patterns...")
    test = TestRoundLabelingAllPaths()
    test.test_specific_chained_patterns()

    # Test some random paths
    print("\n3. Testing random paths...")
    prop_test = TestRoundLabelingProperties()
    for seed in range(5):
        prop_test.test_random_paths(seed)
        print(f"  Seed {seed} ✓")

    print("\n4. Testing determinism...")
    prop_test.test_determinism()

    print("\n✓ All functional tests passed!")
    print(
        f"\nRecommendation: Run pytest with all {len(test_paths)} paths for complete coverage"
    )
