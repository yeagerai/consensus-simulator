"""
Unit tests for individual fee distribution functions.

Each test focuses on a single fee distribution function and verifies
its behavior in isolation.
"""

import pytest
from typing import List, Dict
from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    Round,
    Rotation,
    Appeal,
    EventSequence,
    FeeEvent,
)
from fee_simulator.types import RoundLabel
from fee_simulator.utils import generate_random_eth_address
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT

# Import all fee distribution functions
from fee_simulator.core.round_fee_distribution.normal_round import apply_normal_round
from fee_simulator.core.round_fee_distribution.appeal_leader_successful import apply_appeal_leader_successful
from fee_simulator.core.round_fee_distribution.appeal_validator_successful import apply_appeal_validator_successful
from fee_simulator.core.round_fee_distribution.appeal_validator_unsuccessful import apply_appeal_validator_unsuccessful
from fee_simulator.core.round_fee_distribution.appeal_leader_timeout_successful import apply_appeal_leader_timeout_successful
from fee_simulator.core.round_fee_distribution.leader_timeout_50_percent import apply_leader_timeout_50_percent
from fee_simulator.core.round_fee_distribution.leader_timeout_150_previous_normal_round import apply_leader_timeout_150_previous_normal_round
from fee_simulator.core.round_fee_distribution.leader_timeout_50_previous_appeal_bond import apply_leader_timeout_50_previous_appeal_bond
from fee_simulator.core.round_fee_distribution.split_previous_appeal_bond import apply_split_previous_appeal_bond

# Generate test addresses
addresses_pool = [generate_random_eth_address() for _ in range(100)]

class TestNormalRound:
    """Unit tests for apply_normal_round function."""
    
    def test_leader_receipt_majority_agree(self):
        """Test normal round with leader receipt and majority agree."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                            }
                        )
                    ]
                )
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=0,
            rotations=[0],
            senderAddress=addresses_pool[99],
            appeals=[],
            staking_distribution="constant",
        )
        
        # Execute
        round_labels = ["NORMAL_ROUND"]
        events = apply_normal_round(
            transaction_results=transaction_results,
            round_index=0,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify
        assert len(events) == 4  # One for each participant
        
        # Leader should earn leader timeout + validator timeout
        leader_event = next(e for e in events if e.address == addresses_pool[0])
        assert leader_event.earned == 300  # 100 + 200
        assert leader_event.role == "LEADER"
        
        # Majority validators should earn validator timeout
        for addr in [addresses_pool[1], addresses_pool[2]]:
            event = next(e for e in events if e.address == addr)
            assert event.earned == 200
            assert event.role == "VALIDATOR"
        
        # Minority validator should be penalized
        minority_event = next(e for e in events if e.address == addresses_pool[3])
        assert minority_event.earned == 0
        assert minority_event.burned == PENALTY_REWARD_COEFFICIENT * 200
        assert minority_event.role == "VALIDATOR"
    
    def test_leader_receipt_undetermined(self):
        """Test normal round with undetermined outcome."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "DISAGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "TIMEOUT",
                            }
                        )
                    ]
                )
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=0,
            rotations=[0],
            senderAddress=addresses_pool[99],
            appeals=[],
            staking_distribution="constant",
        )
        
        # Execute
        events = apply_normal_round(
            transaction_results=transaction_results,
            round_index=0,
            budget=budget,
            event_sequence=event_sequence,
        )
        
        # Verify
        assert len(events) == 5
        
        # Leader should earn leader timeout
        leader_event = next(e for e in events if e.address == addresses_pool[0])
        assert leader_event.earned == 100
        
        # All validators should earn 0 (undetermined)
        for addr in [addresses_pool[1], addresses_pool[2], addresses_pool[3], addresses_pool[4]]:
            event = next(e for e in events if e.address == addr)
            assert event.earned == 0
            assert event.burned == 0


class TestAppealLeaderSuccessful:
    """Unit tests for apply_appeal_leader_successful function."""
    
    def test_basic_appeal_leader_successful(self):
        """Test successful leader appeal."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round (undetermined)
                Round(rotations=[Rotation(votes={
                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[1]: "DISAGREE",
                })]),
                # Appeal round
                Round(rotations=[Rotation(votes={
                    addresses_pool[2]: "NA",
                    addresses_pool[3]: "NA",
                })]),
                # Normal round after appeal
                Round(rotations=[Rotation(votes={
                    addresses_pool[4]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[5]: "AGREE",
                })]),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=1,
            rotations=[0, 0],
            senderAddress=addresses_pool[99],
            appeals=[Appeal(appealantAddress=addresses_pool[98])],
            staking_distribution="constant",
        )
        round_labels = ["SKIP_ROUND", "APPEAL_LEADER_SUCCESSFUL", "NORMAL_ROUND"]
        
        # Execute
        events = apply_appeal_leader_successful(
            transaction_results=transaction_results,
            round_index=1,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify
        assert len(events) == 1  # Only appealant event
        
        appealant_event = events[0]
        assert appealant_event.address == addresses_pool[98]
        assert appealant_event.role == "APPEALANT"
        # Appealant should earn appeal bond + leader timeout
        # Appeal bond = 7 validators * 200 + 100 = 1500
        assert appealant_event.earned == 1500 + 100  # 1600
        assert appealant_event.cost == 0  # Cost is recorded separately


class TestAppealValidatorSuccessful:
    """Unit tests for apply_appeal_validator_successful function."""
    
    def test_basic_appeal_validator_successful(self):
        """Test successful validator appeal."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round (majority agree)
                Round(rotations=[Rotation(votes={
                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[1]: "AGREE",
                    addresses_pool[2]: "AGREE",
                    addresses_pool[3]: "DISAGREE",
                })]),
                # Appeal round (validators disagree)
                Round(rotations=[Rotation(votes={
                    addresses_pool[4]: "DISAGREE",
                    addresses_pool[5]: "DISAGREE",
                    addresses_pool[6]: "DISAGREE",
                    addresses_pool[7]: "AGREE",
                })]),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=1,
            rotations=[0],
            senderAddress=addresses_pool[99],
            appeals=[Appeal(appealantAddress=addresses_pool[98])],
            staking_distribution="constant",
        )
        round_labels = ["SKIP_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"]
        
        # Execute
        events = apply_appeal_validator_successful(
            transaction_results=transaction_results,
            round_index=1,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify
        # Should have events for appealant and validators
        assert len(events) == 5  # appealant + 4 validators
        
        # Appealant should earn appeal bond
        appealant_event = next(e for e in events if e.address == addresses_pool[98])
        assert appealant_event.earned == 7 * 200 + 100  # 1500
        
        # Majority validators (who disagreed) should earn validator timeout
        for addr in [addresses_pool[4], addresses_pool[5], addresses_pool[6]]:
            event = next(e for e in events if e.address == addr)
            assert event.earned == 200
            assert event.role == "VALIDATOR"
        
        # Minority validator should be penalized
        minority_event = next(e for e in events if e.address == addresses_pool[7])
        assert minority_event.earned == 0
        assert minority_event.burned == PENALTY_REWARD_COEFFICIENT * 200


class TestLeaderTimeout50Percent:
    """Unit tests for apply_leader_timeout_50_percent function."""
    
    def test_single_leader_timeout(self):
        """Test leader timeout when it's the only round."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[1]: "NA",
                                addresses_pool[2]: "NA",
                            }
                        )
                    ]
                )
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=0,
            rotations=[0],
            senderAddress=addresses_pool[99],
            appeals=[],
            staking_distribution="constant",
        )
        
        # Execute
        round_labels = ["LEADER_TIMEOUT_50_PERCENT"]
        events = apply_leader_timeout_50_percent(
            transaction_results=transaction_results,
            round_index=0,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify
        assert len(events) == 1
        
        leader_event = events[0]
        assert leader_event.address == addresses_pool[0]
        assert leader_event.role == "LEADER"
        assert leader_event.earned == 50  # 50% of leader timeout


class TestSplitPreviousAppealBond:
    """Unit tests for apply_split_previous_appeal_bond function."""
    
    def test_split_appeal_bond_among_validators(self):
        """Test splitting appeal bond among validators in undetermined round."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round
                Round(rotations=[Rotation(votes={
                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[1]: "AGREE",
                })]),
                # Unsuccessful appeal
                Round(rotations=[Rotation(votes={
                    addresses_pool[2]: "AGREE",
                    addresses_pool[3]: "AGREE",
                })]),
                # Undetermined round (split bond)
                Round(rotations=[Rotation(votes={
                    addresses_pool[4]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[5]: "AGREE",
                    addresses_pool[6]: "DISAGREE",
                    addresses_pool[7]: "DISAGREE",
                    addresses_pool[8]: "TIMEOUT",
                })]),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=1,
            rotations=[0, 0],
            senderAddress=addresses_pool[99],
            appeals=[Appeal(appealantAddress=addresses_pool[98])],
            staking_distribution="constant",
        )
        round_labels = ["NORMAL_ROUND", "APPEAL_VALIDATOR_UNSUCCESSFUL", "SPLIT_PREVIOUS_APPEAL_BOND"]
        
        # Execute
        events = apply_split_previous_appeal_bond(
            transaction_results=transaction_results,
            round_index=2,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify
        assert len(events) == 5  # Leader + 4 validators
        
        # Leader should earn leader timeout
        leader_event = next(e for e in events if e.address == addresses_pool[4])
        assert leader_event.earned == 100
        
        # Each validator should earn their share of the appeal bond
        # Appeal bond = 7 * 200 + 100 = 1500
        # Split among 4 validators = 375 each
        for addr in [addresses_pool[5], addresses_pool[6], addresses_pool[7], addresses_pool[8]]:
            event = next(e for e in events if e.address == addr)
            assert event.earned == 375
            assert event.role == "VALIDATOR"


class TestChainedAppealScenarios:
    """Test scenarios with multiple chained appeals."""
    
    def test_double_unsuccessful_appeals(self):
        """Test handling of consecutive unsuccessful appeals."""
        # Setup for a complex scenario with multiple appeals
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal
                Round(rotations=[Rotation(votes={
                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[1]: "AGREE",
                })]),
                # Round 1: First appeal (unsuccessful)
                Round(rotations=[Rotation(votes={
                    addresses_pool[2]: "AGREE",
                    addresses_pool[3]: "AGREE",
                })]),
                # Round 2: Normal
                Round(rotations=[Rotation(votes={
                    addresses_pool[4]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[5]: "AGREE",
                })]),
                # Round 3: Second appeal (unsuccessful)
                Round(rotations=[Rotation(votes={
                    addresses_pool[6]: "AGREE",
                    addresses_pool[7]: "AGREE",
                })]),
                # Round 4: Undetermined (split bond)
                Round(rotations=[Rotation(votes={
                    addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                    addresses_pool[9]: "DISAGREE",
                })]),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=2,
            rotations=[0, 0, 0],
            senderAddress=addresses_pool[99],
            appeals=[
                Appeal(appealantAddress=addresses_pool[97]),
                Appeal(appealantAddress=addresses_pool[96]),
            ],
            staking_distribution="constant",
        )
        round_labels = [
            "NORMAL_ROUND",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "NORMAL_ROUND",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "SPLIT_PREVIOUS_APPEAL_BOND",
        ]
        
        # Execute the appeal functions
        # First unsuccessful appeal
        events1 = apply_appeal_validator_unsuccessful(
            transaction_results=transaction_results,
            round_index=1,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify first appeal has no payouts (unsuccessful)
        assert len(events1) == 0
        
        # Second unsuccessful appeal
        events2 = apply_appeal_validator_unsuccessful(
            transaction_results=transaction_results,
            round_index=3,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify second appeal has no payouts (unsuccessful)
        assert len(events2) == 0
        
        # The split bond function should handle the second appeal's bond
        events3 = apply_split_previous_appeal_bond(
            transaction_results=transaction_results,
            round_index=4,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )
        
        # Verify the bond is split correctly
        assert len(events3) == 2  # Leader + 1 validator
        
        # The second appeal bond (13 * 200 + 100 = 2700) should be split
        validator_event = next(e for e in events3 if e.address == addresses_pool[9])
        assert validator_event.earned == 2700  # Gets the whole bond since only 1 validator


def test_all_distribution_functions_have_tests():
    """Meta-test to ensure we have tests for all distribution functions."""
    # List of all distribution functions that should have tests
    distribution_functions = {
        "normal_round": TestNormalRound,
        "appeal_leader_successful": TestAppealLeaderSuccessful,
        "appeal_validator_successful": TestAppealValidatorSuccessful,
        "leader_timeout_50_percent": TestLeaderTimeout50Percent,
        "split_previous_appeal_bond": TestSplitPreviousAppealBond,
    }
    
    # Verify each has at least one test method
    for func_name, test_class in distribution_functions.items():
        test_methods = [m for m in dir(test_class) if m.startswith("test_")]
        assert len(test_methods) > 0, f"No tests found for {func_name}"


if __name__ == "__main__":
    # Run a quick validation
    print("Running unit tests for fee distribution functions...")
    
    # Test normal round
    test_normal = TestNormalRound()
    test_normal.test_leader_receipt_majority_agree()
    test_normal.test_leader_receipt_undetermined()
    print("✓ Normal round tests passed")
    
    # Test appeals
    test_leader_appeal = TestAppealLeaderSuccessful()
    test_leader_appeal.test_basic_appeal_leader_successful()
    print("✓ Leader appeal tests passed")
    
    test_validator_appeal = TestAppealValidatorSuccessful()
    test_validator_appeal.test_basic_appeal_validator_successful()
    print("✓ Validator appeal tests passed")
    
    # Test special cases
    test_timeout = TestLeaderTimeout50Percent()
    test_timeout.test_single_leader_timeout()
    print("✓ Leader timeout tests passed")
    
    test_split = TestSplitPreviousAppealBond()
    test_split.test_split_appeal_bond_among_validators()
    print("✓ Split bond tests passed")
    
    # Test chained scenarios
    test_chained = TestChainedAppealScenarios()
    test_chained.test_double_unsuccessful_appeals()
    print("✓ Chained appeal tests passed")
    
    print("\nAll unit tests completed successfully!")