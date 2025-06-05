from typing import List, Dict, Optional, Tuple
from fee_simulator.models import TransactionRoundResults
from fee_simulator.types import RoundLabel, Vote
from fee_simulator.core.majority import compute_majority


# Data extraction functions
def extract_rounds_data(
    transaction_results: TransactionRoundResults,
) -> Tuple[List[Dict[str, Vote]], List[Optional[str]]]:
    """Extract vote dictionaries and leader addresses from transaction results."""
    rounds = []
    leader_addresses = []

    for round_obj in transaction_results.rounds:
        if round_obj.rotations:
            votes = round_obj.rotations[-1].votes
            rounds.append(votes)
            leader_addresses.append(next(iter(votes.keys())) if votes else None)
        else:
            rounds.append({})
            leader_addresses.append(None)

    return rounds, leader_addresses


def get_leader_action(
    votes: Dict[str, Vote], leader_address: Optional[str]
) -> Optional[str]:
    """Extract the leader's action from their vote."""
    if not leader_address or leader_address not in votes:
        return None

    vote = votes[leader_address]
    if isinstance(vote, list) and len(vote) >= 2:
        return vote[0]
    return None


# Round classification functions
def is_single_leader_timeout(
    round_index: int, total_rounds: int, leader_action: Optional[str]
) -> bool:
    """Check if this is the only round and the leader timed out."""
    return round_index == 0 and total_rounds == 1 and leader_action == "LEADER_TIMEOUT"


def is_appeal_round(round_index: int) -> bool:
    """Appeal rounds are at odd indices (1, 3, 5, ...)."""
    return round_index % 2 == 1


def classify_normal_round(
    leader_action: Optional[str], is_only_round: bool
) -> RoundLabel:
    """Classify a non-appeal round based on leader action."""
    if leader_action == "LEADER_TIMEOUT":
        if is_only_round:
            return "LEADER_TIMEOUT_50_PERCENT"
        return "LEADER_TIMEOUT"
    return "NORMAL_ROUND"


# Appeal classification functions
def classify_leader_timeout_appeal(
    round_index: int,
    rounds: List[Dict[str, Vote]],
    leader_addresses: List[Optional[str]],
) -> RoundLabel:
    """Classify an appeal that follows a leader timeout."""
    # Check if there's a next round
    if round_index + 1 >= len(rounds):
        return "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"

    # Check next round's leader action
    next_leader_action = get_leader_action(
        rounds[round_index + 1], leader_addresses[round_index + 1]
    )

    if next_leader_action == "LEADER_TIMEOUT":
        return "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"
    else:
        return "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"


def classify_vote_appeal(
    round_index: int, rounds: List[Dict[str, Vote]], prev_majority: str
) -> RoundLabel:
    """Classify an appeal based on vote majorities."""
    # If this is the last round, assume unsuccessful
    if round_index + 1 >= len(rounds):
        if prev_majority in ["UNDETERMINED", "DISAGREE"]:
            return "APPEAL_LEADER_UNSUCCESSFUL"
        else:
            return "APPEAL_VALIDATOR_UNSUCCESSFUL"

    # Get appeal round majority
    appeal_votes = rounds[round_index]
    appeal_majority = compute_majority(appeal_votes) if appeal_votes else "UNDETERMINED"

    # Leader appeal: previous round had no clear majority
    if prev_majority in ["UNDETERMINED", "DISAGREE"]:
        next_majority = compute_majority(rounds[round_index + 1])

        if next_majority not in ["UNDETERMINED", "DISAGREE"]:
            return "APPEAL_LEADER_SUCCESSFUL"
        else:
            return "APPEAL_LEADER_UNSUCCESSFUL"

    # Validator appeal: previous round had a clear majority
    else:
        # Successful if validators changed the outcome
        if appeal_majority != prev_majority and appeal_majority != "UNDETERMINED":
            return "APPEAL_VALIDATOR_SUCCESSFUL"
        else:
            return "APPEAL_VALIDATOR_UNSUCCESSFUL"


def classify_appeal_round(
    round_index: int,
    rounds: List[Dict[str, Vote]],
    leader_addresses: List[Optional[str]],
) -> RoundLabel:
    """Classify an appeal round based on the previous round's outcome."""
    if round_index == 0:  # Safety check
        return "EMPTY_ROUND"

    prev_round = rounds[round_index - 1]
    prev_leader_action = get_leader_action(
        prev_round, leader_addresses[round_index - 1]
    )

    if prev_leader_action == "LEADER_TIMEOUT":
        return classify_leader_timeout_appeal(round_index, rounds, leader_addresses)
    else:
        prev_majority = compute_majority(prev_round)
        return classify_vote_appeal(round_index, rounds, prev_majority)


# Special case patterns
SPECIAL_CASE_PATTERNS = [
    {
        "name": "Skip round before successful appeal",
        "pattern": [
            "NORMAL_ROUND",
            ["APPEAL_LEADER_SUCCESSFUL", "APPEAL_VALIDATOR_SUCCESSFUL"],
            "NORMAL_ROUND",
        ],
        "changes": {0: "SKIP_ROUND"},
    },
    {
        "name": "Leader timeout 150% after successful appeal",
        "pattern": [
            "LEADER_TIMEOUT",
            "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
            "NORMAL_ROUND",
        ],
        "changes": {0: "SKIP_ROUND", 2: "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND"},
    },
    {
        "name": "Split appeal bond after unsuccessful appeal",
        "pattern": [
            "NORMAL_ROUND",
            ["APPEAL_LEADER_UNSUCCESSFUL", "APPEAL_VALIDATOR_UNSUCCESSFUL"],
            "NORMAL_ROUND",
        ],
        "condition": lambda rounds, i: i + 2 < len(rounds)
        and rounds[i + 2]
        and compute_majority(rounds[i + 2]) in ["UNDETERMINED", "DISAGREE"],
        "changes": {2: "SPLIT_PREVIOUS_APPEAL_BOND"},
    },
    {
        "name": "Leader timeout 50% after unsuccessful appeal",
        "pattern": [
            "LEADER_TIMEOUT_50_PERCENT",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "LEADER_TIMEOUT",
        ],
        "changes": {
            2: "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        },
    },
    {
        "name": "Chained leader timeout 50% after unsuccessful appeal",
        "pattern": [
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "LEADER_TIMEOUT",
        ],
        "changes": {
            2: "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        },
    },
]


def matches_pattern(labels: List[RoundLabel], start_idx: int, pattern: List) -> bool:
    """Check if labels match a pattern starting at the given index."""
    if start_idx + len(pattern) > len(labels):
        return False

    for i, expected in enumerate(pattern):
        actual = labels[start_idx + i]

        # Handle list of possible values
        if isinstance(expected, list):
            if actual not in expected:
                return False
        # Handle single value
        elif actual != expected:
            return False

    return True


def apply_special_cases(
    labels: List[RoundLabel], rounds: List[Dict[str, Vote]]
) -> List[RoundLabel]:
    """Apply special case transformations based on patterns."""
    new_labels = labels.copy()
    processed_indices = set()

    # Try to match each pattern
    for pattern_config in SPECIAL_CASE_PATTERNS:
        pattern = pattern_config["pattern"]

        # Look for this pattern in the labels
        for i in range(len(new_labels) - len(pattern) + 1):
            # Skip if the indices we want to change are already processed
            changes_to_make = pattern_config["changes"]
            if any((i + offset) in processed_indices for offset in changes_to_make):
                continue

            # Check if pattern matches
            if not matches_pattern(new_labels, i, pattern):
                continue

            # Check additional condition if present
            if "condition" in pattern_config:
                if not pattern_config["condition"](rounds, i):
                    continue

            # Apply changes
            for offset, new_label in pattern_config["changes"].items():
                new_labels[i + offset] = new_label
                # Mark only the changed indices as processed
                processed_indices.add(i + offset)

    return new_labels


# Main function
def label_rounds(transaction_results: TransactionRoundResults) -> List[RoundLabel]:
    """
    Label each round based on its characteristics and relationships with other rounds.

    The labeling process:
    1. Extract round data from transaction results
    2. Classify each round individually
    3. Apply special case patterns that depend on round sequences
    """
    # Extract data
    rounds, leader_addresses = extract_rounds_data(transaction_results)

    # Initial classification
    labels = []
    total_rounds = len(rounds)

    for i, round_votes in enumerate(rounds):
        # Handle empty rounds
        if not round_votes:
            labels.append("EMPTY_ROUND")
            continue

        # Get leader action
        leader_action = get_leader_action(round_votes, leader_addresses[i])

        # Special case: single leader timeout
        if is_single_leader_timeout(i, total_rounds, leader_action):
            labels.append("LEADER_TIMEOUT_50_PERCENT")
            continue

        # Check for the specific pattern: LEADER_TIMEOUT -> APPEAL -> LEADER_TIMEOUT
        # where the appeal will be unsuccessful
        if (i == 0 and leader_action == "LEADER_TIMEOUT" and 
            i + 2 < total_rounds):
            # Check if next round is an appeal and round after that is leader timeout
            next_leader_action = get_leader_action(rounds[i + 2], leader_addresses[i + 2])
            if is_appeal_round(i + 1) and next_leader_action == "LEADER_TIMEOUT":
                # This matches the pattern, so first timeout gets 50%
                labels.append("LEADER_TIMEOUT_50_PERCENT")
                continue

        # Classify based on round type
        if is_appeal_round(i):
            label = classify_appeal_round(i, rounds, leader_addresses)
        else:
            is_only_round = total_rounds == 1
            label = classify_normal_round(leader_action, is_only_round)

        labels.append(label)

    # Apply special case transformations
    labels = apply_special_cases(labels, rounds)

    return labels
