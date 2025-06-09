"""
Convert TRANSITIONS_GRAPH paths to TransactionRoundResults objects.

This module provides the bridge between graph paths and the transaction
data structures used by the fee distribution system.
"""

from typing import List, Dict, Tuple
from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    Round,
    Rotation,
    Appeal,
)
from fee_simulator.types import Vote
from fee_simulator.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES


def is_appeal_node(node: str) -> bool:
    """Check if a node represents an appeal round."""
    return any(appeal_type in node for appeal_type in [
        "VALIDATOR_APPEAL",
        "LEADER_APPEAL"
    ])


def create_majority_agree_votes(size: int, addresses: List[str], offset: int = 0) -> Dict[str, Vote]:
    """Create votes where majority agrees."""
    votes = {
        addresses[offset]: ["LEADER_RECEIPT", "AGREE"],  # Leader
    }
    
    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1
    
    # First majority_count-1 validators agree (we already have leader agreeing)
    for i in range(1, majority_count):
        votes[addresses[offset + i]] = "AGREE"
    
    # Rest of validators split between DISAGREE and TIMEOUT
    for i in range(majority_count, size):
        if (i - majority_count) % 2 == 0:
            votes[addresses[offset + i]] = "DISAGREE"
        else:
            votes[addresses[offset + i]] = "TIMEOUT"
    
    return votes


def create_majority_disagree_votes(size: int, addresses: List[str], offset: int = 0) -> Dict[str, Vote]:
    """Create votes where majority disagrees."""
    votes = {
        addresses[offset]: ["LEADER_RECEIPT", "DISAGREE"],  # Leader
    }
    
    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1
    
    # First majority_count-1 validators disagree (we already have leader disagreeing)
    for i in range(1, majority_count):
        votes[addresses[offset + i]] = "DISAGREE"
    
    # Rest of validators split between AGREE and TIMEOUT
    for i in range(majority_count, size):
        if (i - majority_count) % 2 == 0:
            votes[addresses[offset + i]] = "AGREE"
        else:
            votes[addresses[offset + i]] = "TIMEOUT"
    
    return votes


def create_majority_timeout_votes(size: int, addresses: List[str], offset: int = 0) -> Dict[str, Vote]:
    """Create votes where majority times out."""
    votes = {
        addresses[offset]: ["LEADER_RECEIPT", "TIMEOUT"],  # Leader
    }
    
    # Calculate majority threshold (more than half)
    majority_count = (size // 2) + 1
    
    # First majority_count-1 validators timeout (we already have leader timing out)
    for i in range(1, majority_count):
        votes[addresses[offset + i]] = "TIMEOUT"
    
    # Rest of validators split between AGREE and DISAGREE
    for i in range(majority_count, size):
        if (i - majority_count) % 2 == 0:
            votes[addresses[offset + i]] = "AGREE"
        else:
            votes[addresses[offset + i]] = "DISAGREE"
    
    return votes


def create_undetermined_votes(size: int, addresses: List[str], offset: int = 0) -> Dict[str, Vote]:
    """Create votes with no clear majority (undetermined) - 1/3 agree, 1/3 disagree, 1/3 timeout."""
    votes = {
        addresses[offset]: ["LEADER_RECEIPT", "AGREE"],  # Leader
    }
    
    # Calculate thirds for validators (size - 1 because we exclude the leader)
    num_validators = size - 1
    agree_count = num_validators // 3
    disagree_count = num_validators // 3
    # Remaining validators get TIMEOUT
    timeout_count = num_validators - agree_count - disagree_count
    
    # Assign votes
    validator_idx = 1
    
    # Agree votes
    for _ in range(agree_count):
        votes[addresses[offset + validator_idx]] = "AGREE"
        validator_idx += 1
    
    # Disagree votes
    for _ in range(disagree_count):
        votes[addresses[offset + validator_idx]] = "DISAGREE"
        validator_idx += 1
    
    # Timeout votes (remaining)
    for _ in range(timeout_count):
        votes[addresses[offset + validator_idx]] = "TIMEOUT"
        validator_idx += 1
    
    return votes


def create_leader_timeout_votes(size: int, addresses: List[str], offset: int = 0) -> Dict[str, Vote]:
    """Create votes where leader times out."""
    votes = {
        addresses[offset]: ["LEADER_TIMEOUT", "NA"],  # Leader timed out
    }
    # Validators vote on whether to accept timeout
    for i in range(1, size):
        votes[addresses[offset + i]] = "AGREE"  # Accept the timeout
    return votes


def create_appeal_votes(node: str, size: int, addresses: List[str], offset: int = 0, prev_majority: str = None) -> Dict[str, Vote]:
    """Create votes for an appeal round based on the node type and previous round context."""
    votes = {}
    
    # Determine if this is a leader appeal or validator appeal
    is_leader_appeal = "LEADER_APPEAL" in node
    
    if is_leader_appeal:
        # Leader appeals: All participants get NA votes
        for i in range(size):
            votes[addresses[offset + i]] = "NA"
            
        # Determine success/failure based on node name and create appropriate majority
        if "SUCCESSFUL" in node and "UNSUCCESSFUL" not in node:
            # Successful leader appeal - create a clear majority (not undetermined/disagree)
            majority_count = (size // 2) + 1
            # Create majority AGREE
            for i in range(majority_count):
                votes[addresses[offset + i]] = "NA"  # These will be counted as effective AGREE
        else:
            # Unsuccessful leader appeal - maintain undetermined/disagree state
            # Equal distribution ensures no clear majority
            pass  # Already set all to NA
    else:
        # Validator appeals: Validators are appealing the majority decision
        # The success/failure depends on whether appeal changes the outcome
        
        if "SUCCESSFUL" in node and "UNSUCCESSFUL" not in node:
            # Successful appeal means the outcome changes
            # If previous was AGREE, appeal needs majority DISAGREE/TIMEOUT
            # If previous was DISAGREE, appeal needs majority AGREE
            # If previous was TIMEOUT, appeal needs majority AGREE/DISAGREE
            majority_count = (size // 2) + 1
            
            if prev_majority == "AGREE":
                # Need majority to disagree or timeout
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "AGREE"
            elif prev_majority == "DISAGREE":
                # Need majority to agree
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "AGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "DISAGREE"
            else:  # TIMEOUT or UNDETERMINED
                # Default to majority disagree
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "AGREE"
        else:
            # Unsuccessful appeal means the outcome stays the same
            # Appeal majority should match previous majority
            majority_count = (size // 2) + 1
            
            if prev_majority == "AGREE":
                # Majority agrees (same as before)
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "AGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "DISAGREE"
            elif prev_majority == "DISAGREE":
                # Majority disagrees (same as before)
                for i in range(majority_count):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(majority_count, size):
                    votes[addresses[offset + i]] = "AGREE"
            else:  # TIMEOUT or UNDETERMINED
                # For unsuccessful validator appeal after undetermined, maintain undetermined
                # Create equal split to ensure no clear majority
                third = size // 3
                for i in range(third):
                    votes[addresses[offset + i]] = "AGREE"
                for i in range(third, 2 * third):
                    votes[addresses[offset + i]] = "DISAGREE"
                for i in range(2 * third, size):
                    votes[addresses[offset + i]] = "TIMEOUT"
    
    return votes


def create_normal_round(node: str, normal_index: int, addresses: List[str], offset: int) -> Round:
    """Create a normal round based on the node type."""
    size = NORMAL_ROUND_SIZES[normal_index] if normal_index < len(NORMAL_ROUND_SIZES) else NORMAL_ROUND_SIZES[-1]
    
    # Parse node type to determine votes
    if node == "LEADER_RECEIPT_MAJORITY_AGREE":
        votes = create_majority_agree_votes(size, addresses, offset)
    elif node == "LEADER_RECEIPT_MAJORITY_DISAGREE":
        votes = create_majority_disagree_votes(size, addresses, offset)
    elif node == "LEADER_RECEIPT_MAJORITY_TIMEOUT":
        votes = create_majority_timeout_votes(size, addresses, offset)
    elif node == "LEADER_RECEIPT_UNDETERMINED":
        votes = create_undetermined_votes(size, addresses, offset)
    elif node == "LEADER_TIMEOUT":
        votes = create_leader_timeout_votes(size, addresses, offset)
    else:
        # Default case
        votes = create_undetermined_votes(size, addresses, offset)
    
    return Round(rotations=[Rotation(votes=votes)])


def create_appeal_round(node: str, appeal_index: int, addresses: List[str], offset: int, prev_majority: str = None) -> Round:
    """Create an appeal round based on the node type."""
    size = APPEAL_ROUND_SIZES[appeal_index] if appeal_index < len(APPEAL_ROUND_SIZES) else APPEAL_ROUND_SIZES[-1]
    
    votes = create_appeal_votes(node, size, addresses, offset, prev_majority)
    
    return Round(rotations=[Rotation(votes=votes)])


def path_to_transaction_results(
    path: List[str], 
    addresses: List[str],
    sender_address: str = None,
    appealant_address: str = None,
    leader_timeout: int = 100,
    validators_timeout: int = 200,
) -> Tuple[TransactionRoundResults, TransactionBudget]:
    """
    Convert a TRANSITIONS_GRAPH path to TransactionRoundResults and TransactionBudget.
    
    Args:
        path: List of node names from TRANSITIONS_GRAPH
        addresses: Pool of addresses to use for participants
        sender_address: Address of the transaction sender (default: addresses[-1])
        appealant_address: Address of the appealant (default: addresses[-2])
        leader_timeout: Leader timeout value
        validators_timeout: Validators timeout value
        
    Returns:
        Tuple of (TransactionRoundResults, TransactionBudget)
    """
    if sender_address is None:
        sender_address = addresses[-1]
    if appealant_address is None:
        appealant_address = addresses[-2]
    
    rounds = []
    appeals = []
    normal_count = 0
    appeal_count = 0
    address_offset = 0
    prev_majority = None
    last_normal_majority = None  # Track the last normal round's majority for chained appeals
    
    # Import compute_majority for tracking round majorities
    from fee_simulator.core.majority import compute_majority
    
    # Skip START and END nodes
    for i, node in enumerate(path[1:-1]):
        if is_appeal_node(node):
            # For validator appeals, use the last normal round's majority as context
            # This ensures chained appeals reference the original disputed outcome
            context_majority = last_normal_majority if "VALIDATOR_APPEAL" in node else prev_majority
            
            # Appeal round - pass appropriate majority context
            round_obj = create_appeal_round(node, appeal_count, addresses, address_offset, context_majority)
            rounds.append(round_obj)
            appeals.append(Appeal(appealantAddress=appealant_address))
            
            # Update offset for next round
            appeal_size = APPEAL_ROUND_SIZES[appeal_count] if appeal_count < len(APPEAL_ROUND_SIZES) else APPEAL_ROUND_SIZES[-1]
            address_offset += appeal_size
            appeal_count += 1
        else:
            # Normal round
            round_obj = create_normal_round(node, normal_count, addresses, address_offset)
            rounds.append(round_obj)
            
            # Update the last normal round majority
            if round_obj.rotations and round_obj.rotations[0].votes:
                last_normal_majority = compute_majority(round_obj.rotations[0].votes)
            
            # Update offset for next round
            normal_size = NORMAL_ROUND_SIZES[normal_count] if normal_count < len(NORMAL_ROUND_SIZES) else NORMAL_ROUND_SIZES[-1]
            address_offset += normal_size
            normal_count += 1
        
        # Track the majority outcome of this round for the next round
        if round_obj.rotations and round_obj.rotations[0].votes:
            prev_majority = compute_majority(round_obj.rotations[0].votes)
    
    # Create budget based on path
    # Count normal rounds (non-appeal rounds)
    normal_round_count = len(rounds) - appeal_count
    
    # Rotations are indexed by normal round number, so we need one per normal round
    budget = TransactionBudget(
        leaderTimeout=leader_timeout,
        validatorsTimeout=validators_timeout,
        appealRounds=appeal_count,
        rotations=[0] * normal_round_count,
        senderAddress=sender_address,
        appeals=appeals,
        staking_distribution="constant"
    )
    
    return TransactionRoundResults(rounds=rounds), budget


def node_to_expected_label(node: str) -> str:
    """
    Map a graph node to its expected round label.
    
    This is useful for testing to verify that round_labeling produces
    the expected labels for a given path.
    """
    # Normal rounds
    if node in ["LEADER_RECEIPT_MAJORITY_AGREE", "LEADER_RECEIPT_MAJORITY_DISAGREE",
                "LEADER_RECEIPT_MAJORITY_TIMEOUT", "LEADER_RECEIPT_UNDETERMINED"]:
        return "NORMAL_ROUND"
    elif node == "LEADER_TIMEOUT":
        return "LEADER_TIMEOUT"
    
    # Appeal rounds - the node name directly maps to the label
    elif node == "VALIDATOR_APPEAL_SUCCESSFUL":
        return "APPEAL_VALIDATOR_SUCCESSFUL"
    elif node == "VALIDATOR_APPEAL_UNSUCCESSFUL":
        return "APPEAL_VALIDATOR_UNSUCCESSFUL"
    elif node == "LEADER_APPEAL_SUCCESSFUL":
        return "APPEAL_LEADER_SUCCESSFUL"
    elif node == "LEADER_APPEAL_UNSUCCESSFUL":
        return "APPEAL_LEADER_UNSUCCESSFUL"
    elif node == "LEADER_APPEAL_TIMEOUT_SUCCESSFUL":
        return "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"
    elif node == "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL":
        return "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"
    
    return "UNKNOWN"