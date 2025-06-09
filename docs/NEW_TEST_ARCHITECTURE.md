# Fee Simulator Test Architecture Implementation Guide

## Table of Contents
1. [Overview](#overview)
2. [New Directory Structure](#new-directory-structure)
3. [Core Components](#core-components)
4. [Migration Plan](#migration-plan)
5. [Implementation Examples](#implementation-examples)
6. [Execution Strategy](#execution-strategy)

## Overview

This guide provides a complete implementation plan for refactoring the fee simulator test architecture. The new architecture prioritizes invariants as first-class citizens, eliminates redundancy, and provides clear separation of concerns.

### Key Principles
- **Invariants First**: Invariants are the specification
- **No Duplication**: Each test has one clear home
- **Composable**: Build complex tests from simple components
- **Progressive**: Fast tests run first, comprehensive tests run on demand

## New Directory Structure

```
tests/
├── __init__.py
├── conftest.py                      # Enhanced pytest configuration
├── README.md                        # Test architecture documentation
│
├── invariants/                      # PRIORITY 1: System invariants
│   ├── __init__.py
│   ├── core/                        # Core invariant implementations
│   │   ├── __init__.py
│   │   ├── conservation.py          # Value conservation invariants
│   │   ├── fairness.py             # Fairness and gaming prevention
│   │   ├── determinism.py          # Deterministic behavior
│   │   ├── state.py                # State consistency invariants
│   │   └── business_rules.py       # Business rule invariants
│   ├── registry.py                  # Invariant registration and management
│   ├── runners/                     # Different execution strategies
│   │   ├── __init__.py
│   │   ├── base_runner.py          # Abstract runner interface
│   │   ├── quick_runner.py         # Fast smoke tests
│   │   ├── property_runner.py      # Property-based testing
│   │   ├── path_runner.py          # Path exhaustive testing
│   │   └── parallel_runner.py      # Distributed execution
│   └── reports.py                   # Invariant violation reporting
│
├── scenarios/                       # PRIORITY 2: Real-world scenarios
│   ├── __init__.py
│   ├── common/                      # Common transaction patterns
│   │   ├── single_round.py
│   │   ├── simple_appeal.py
│   │   ├── chained_appeals.py
│   │   └── leader_timeouts.py
│   ├── edge_cases/                  # Known edge cases
│   │   ├── max_appeals.py          # 16 chained appeals
│   │   ├── all_validators_idle.py
│   │   ├── split_decisions.py
│   │   └── round_size_limits.py
│   ├── attack_vectors/              # Security scenarios
│   │   ├── gaming_attempts.py
│   │   ├── stake_manipulation.py
│   │   └── collision_attacks.py
│   └── regression/                  # Past bugs
│       ├── issue_001_negative_balance.py
│       └── catalog.yaml             # Regression test catalog
│
├── components/                      # PRIORITY 3: Component tests
│   ├── __init__.py
│   ├── test_round_labeling.py
│   ├── test_fee_distribution.py
│   ├── test_bond_computing.py
│   ├── test_majority_voting.py
│   ├── test_path_generation.py
│   └── test_refunds.py
│
├── integration/                     # PRIORITY 4: Integration tests
│   ├── __init__.py
│   ├── test_full_transaction_flow.py
│   ├── test_round_combinations.py
│   └── test_error_handling.py
│
├── performance/                     # PRIORITY 5: Performance tests
│   ├── __init__.py
│   ├── benchmarks/
│   │   ├── test_throughput.py
│   │   ├── test_memory_usage.py
│   │   └── baseline_metrics.json
│   └── stress/
│       ├── test_large_rounds.py
│       ├── test_many_appeals.py
│       └── test_concurrent_load.py
│
├── fixtures/                        # Shared test infrastructure
│   ├── __init__.py
│   ├── builders/                    # Test data builders
│   │   ├── __init__.py
│   │   ├── transaction_builder.py
│   │   ├── round_builder.py
│   │   ├── path_builder.py
│   │   └── scenario_builder.py
│   ├── generators/                  # Data generators
│   │   ├── __init__.py
│   │   ├── address_generator.py
│   │   ├── vote_generator.py
│   │   └── path_generator.py
│   ├── validators/                  # Custom assertions
│   │   ├── __init__.py
│   │   ├── fee_validators.py
│   │   ├── state_validators.py
│   │   └── output_validators.py
│   └── test_data/                   # Static test data
│       ├── sample_paths.json
│       └── known_good_results.json
│
└── utils/                           # Test utilities
    ├── __init__.py
    ├── oracle.py                    # Expected outcome calculator
    ├── reporter.py                  # Test result reporting
    └── path_sampler.py             # Smart path sampling
```

## Core Components

### 1. Invariant Registry System

```python
# tests/invariants/registry.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Any
from enum import Enum

class InvariantPriority(Enum):
    CRITICAL = "critical"    # Must never fail
    HIGH = "high"           # Should rarely fail
    MEDIUM = "medium"       # Nice to have
    LOW = "low"            # Informational

class InvariantGroup(Enum):
    FINANCIAL = "financial"
    STATE = "state"
    FAIRNESS = "fairness"
    PERFORMANCE = "performance"
    ALL = "all"

@dataclass
class InvariantViolation:
    invariant_id: str
    message: str
    severity: InvariantPriority
    context: Dict[str, Any]
    
class Invariant(ABC):
    """Base class for all invariants"""
    
    def __init__(self, id: str, description: str, 
                 priority: InvariantPriority,
                 groups: List[InvariantGroup]):
        self.id = id
        self.description = description
        self.priority = priority
        self.groups = groups
    
    @abstractmethod
    def check(self, state: 'SystemState') -> Optional[InvariantViolation]:
        """Check if invariant holds. Return None if OK, Violation if not."""
        pass

class InvariantRegistry:
    """Central registry for all system invariants"""
    
    def __init__(self):
        self._invariants: Dict[str, Invariant] = {}
        self._groups: Dict[InvariantGroup, Set[str]] = {
            group: set() for group in InvariantGroup
        }
    
    def register(self, invariant: Invariant) -> None:
        """Register an invariant"""
        self._invariants[invariant.id] = invariant
        for group in invariant.groups:
            self._groups[group].add(invariant.id)
            self._groups[InvariantGroup.ALL].add(invariant.id)
    
    def check_all(self, state: 'SystemState') -> List[InvariantViolation]:
        """Check all invariants"""
        return self.check_group(InvariantGroup.ALL, state)
    
    def check_group(self, group: InvariantGroup, 
                    state: 'SystemState') -> List[InvariantViolation]:
        """Check all invariants in a group"""
        violations = []
        for inv_id in self._groups[group]:
            if violation := self._invariants[inv_id].check(state):
                violations.append(violation)
        return violations
    
    def check_critical(self, state: 'SystemState') -> List[InvariantViolation]:
        """Check only critical invariants (for fast tests)"""
        violations = []
        for inv in self._invariants.values():
            if inv.priority == InvariantPriority.CRITICAL:
                if violation := inv.check(state):
                    violations.append(violation)
        return violations
```

### 2. System State for Testing

```python
# tests/invariants/core/state.py
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class SystemState:
    """Complete system state for invariant checking"""
    
    # Input
    transaction_results: 'TransactionRoundResults'
    transaction_budget: 'TransactionBudget'
    addresses: List[str]
    
    # Output  
    fee_events: List['FeeEvent']
    round_labels: List[str]
    
    # Derived
    address_balances: Optional[Dict[str, int]] = None
    total_costs: Optional[int] = None
    total_earnings: Optional[int] = None
    total_burns: Optional[int] = None
    
    def __post_init__(self):
        """Calculate derived values"""
        if self.fee_events and not self.address_balances:
            self._calculate_balances()
    
    def _calculate_balances(self):
        """Calculate final balances for all addresses"""
        self.address_balances = {}
        for event in self.fee_events:
            addr = event.address
            if addr not in self.address_balances:
                self.address_balances[addr] = 0
            
            self.address_balances[addr] += event.earned
            self.address_balances[addr] -= event.cost
            self.address_balances[addr] -= event.burned
            self.address_balances[addr] -= event.slashed
```

### 3. Example Invariant Implementations

```python
# tests/invariants/core/conservation.py
from typing import Optional
from ..registry import Invariant, InvariantViolation, InvariantPriority, InvariantGroup

class ConservationInvariant(Invariant):
    """Total money in = Total money out + burns"""
    
    def __init__(self):
        super().__init__(
            id="conservation_of_value",
            description="Total costs must equal earnings + burns + refunds",
            priority=InvariantPriority.CRITICAL,
            groups=[InvariantGroup.FINANCIAL]
        )
    
    def check(self, state: SystemState) -> Optional[InvariantViolation]:
        total_in = sum(e.cost for e in state.fee_events)
        total_out = sum(e.earned for e in state.fee_events)
        total_burned = sum(e.burned for e in state.fee_events)
        
        refund = self._calculate_sender_refund(state)
        
        if abs(total_in - (total_out + total_burned + refund)) > 1:
            return InvariantViolation(
                invariant_id=self.id,
                message=f"Conservation violated: {total_in} != {total_out} + {total_burned} + {refund}",
                severity=self.priority,
                context={
                    "total_in": total_in,
                    "total_out": total_out,
                    "total_burned": total_burned,
                    "refund": refund,
                    "difference": total_in - (total_out + total_burned + refund)
                }
            )
        return None

class NonNegativeBalanceInvariant(Invariant):
    """No address should have negative balance"""
    
    def __init__(self):
        super().__init__(
            id="non_negative_balances",
            description="All addresses must have non-negative final balance",
            priority=InvariantPriority.CRITICAL,
            groups=[InvariantGroup.FINANCIAL, InvariantGroup.FAIRNESS]
        )
    
    def check(self, state: SystemState) -> Optional[InvariantViolation]:
        for addr, balance in state.address_balances.items():
            if balance < 0:
                return InvariantViolation(
                    invariant_id=self.id,
                    message=f"Address {addr} has negative balance: {balance}",
                    severity=self.priority,
                    context={"address": addr, "balance": balance}
                )
        return None
```

### 4. Test Builders

```python
# tests/fixtures/builders/transaction_builder.py
from typing import List, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class TransactionBuilder:
    """Fluent interface for building test transactions"""
    
    _rounds: List['Round'] = field(default_factory=list)
    _budget: Optional['TransactionBudget'] = None
    _addresses: List[str] = field(default_factory=list)
    
    def with_normal_round(self, 
                         majority: str = "AGREE",
                         num_validators: int = 5) -> 'TransactionBuilder':
        """Add a normal round with specified majority"""
        round_builder = RoundBuilder()
        round_obj = round_builder.normal_round(
            majority=majority,
            num_validators=num_validators,
            addresses=self._get_next_addresses(num_validators)
        ).build()
        self._rounds.append(round_obj)
        return self
    
    def with_appeal_round(self, 
                         appeal_type: str,
                         successful: bool) -> 'TransactionBuilder':
        """Add an appeal round"""
        round_builder = RoundBuilder()
        round_obj = round_builder.appeal_round(
            appeal_type=appeal_type,
            successful=successful,
            addresses=self._get_next_addresses(7)  # Default appeal size
        ).build()
        self._rounds.append(round_obj)
        return self
    
    def with_leader_timeout(self) -> 'TransactionBuilder':
        """Add a leader timeout round"""
        round_builder = RoundBuilder()
        round_obj = round_builder.leader_timeout_round(
            addresses=self._get_next_addresses(5)
        ).build()
        self._rounds.append(round_obj)
        return self
    
    def with_budget(self, leader_timeout: int = 100,
                   validators_timeout: int = 200) -> 'TransactionBuilder':
        """Set the transaction budget"""
        appeal_count = sum(1 for r in self._rounds if self._is_appeal_round(r))
        self._budget = TransactionBudget(
            leaderTimeout=leader_timeout,
            validatorsTimeout=validators_timeout,
            appealRounds=appeal_count,
            rotations=[0] * (len(self._rounds) + 1) // 2,
            senderAddress=self._addresses[-1],
            appeals=[Appeal(appealantAddress=self._addresses[-2-i]) 
                    for i in range(appeal_count)],
            staking_distribution="constant"
        )
        return self
    
    def build(self) -> 'SystemState':
        """Build the complete system state"""
        transaction = TransactionRoundResults(rounds=self._rounds)
        if not self._budget:
            self.with_budget()
        
        # Process transaction
        fee_events, labels = process_transaction(
            self._addresses, transaction, self._budget
        )
        
        return SystemState(
            transaction_results=transaction,
            transaction_budget=self._budget,
            addresses=self._addresses,
            fee_events=fee_events,
            round_labels=labels
        )
```

### 5. Test Oracle

```python
# tests/utils/oracle.py
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class ExpectedOutcome:
    """Expected outcome for a transaction"""
    
    earnings: Dict[str, int]
    costs: Dict[str, int]
    burns: Dict[str, int]
    labels: List[str]
    
class FeeDistributionOracle:
    """Calculates expected outcomes for test verification"""
    
    def __init__(self, business_rules: 'BusinessRules'):
        self.rules = business_rules
    
    def calculate_expected(self, 
                          transaction: 'TransactionRoundResults',
                          budget: 'TransactionBudget') -> ExpectedOutcome:
        """Calculate what the outcome SHOULD be"""
        expected = ExpectedOutcome(
            earnings={}, costs={}, burns={}, labels=[]
        )
        
        # Apply business rules to calculate expected outcome
        for round_idx, round_obj in enumerate(transaction.rounds):
            round_outcome = self._calculate_round_outcome(
                round_obj, round_idx, budget
            )
            self._merge_outcomes(expected, round_outcome)
        
        return expected
    
    def verify_actual(self, 
                     expected: ExpectedOutcome,
                     actual_events: List['FeeEvent'],
                     actual_labels: List[str]) -> List[str]:
        """Verify actual matches expected, return discrepancies"""
        discrepancies = []
        
        # Check labels
        if expected.labels != actual_labels:
            discrepancies.append(
                f"Label mismatch: expected {expected.labels}, "
                f"got {actual_labels}"
            )
        
        # Check earnings, costs, burns
        for addr in expected.earnings:
            actual_earning = sum(e.earned for e in actual_events 
                               if e.address == addr)
            if expected.earnings[addr] != actual_earning:
                discrepancies.append(
                    f"Earnings mismatch for {addr}: "
                    f"expected {expected.earnings[addr]}, "
                    f"got {actual_earning}"
                )
        
        return discrepancies
```

## Migration Plan

### Phase 1: Setup Infrastructure (Week 1)

#### Day 1-2: Create Directory Structure
```bash
#!/bin/bash
# create_test_structure.sh

# Create new directory structure
mkdir -p tests/{invariants/{core,runners},scenarios/{common,edge_cases,attack_vectors,regression}}
mkdir -p tests/{components,integration,performance/{benchmarks,stress}}
mkdir -p tests/{fixtures/{builders,generators,validators,test_data},utils}

# Create __init__.py files
find tests -type d -exec touch {}/__init__.py \;

# Create README
cat > tests/README.md << EOF
# Fee Simulator Test Suite

## Quick Start
- Run quick tests: pytest -m quick
- Run all tests: pytest
- Run specific group: pytest tests/invariants -k "conservation"

## Architecture
See docs/NEW_TEST_ARCHITECTURE.md for details.
EOF
```

#### Day 3-4: Implement Core Infrastructure

1. Copy and enhance `conftest.py`:
```python
# tests/conftest.py
import pytest
from pathlib import Path
from tests.invariants.registry import InvariantRegistry, InvariantGroup
from tests.fixtures.builders import TransactionBuilder
from tests.utils.oracle import FeeDistributionOracle

@pytest.fixture(scope="session")
def invariant_registry():
    """Global invariant registry"""
    registry = InvariantRegistry()
    # Auto-discover and register all invariants
    from tests.invariants.core import (
        ConservationInvariant,
        NonNegativeBalanceInvariant,
        # ... more invariants
    )
    registry.register(ConservationInvariant())
    registry.register(NonNegativeBalanceInvariant())
    return registry

@pytest.fixture
def transaction_builder():
    """Transaction builder for tests"""
    return TransactionBuilder()

@pytest.fixture
def oracle():
    """Test oracle for expected outcomes"""
    return FeeDistributionOracle()

# Markers for test categorization
def pytest_configure(config):
    config.addinivalue_line("markers", "quick: marks tests as quick (<1s)")
    config.addinivalue_line("markers", "slow: marks tests as slow (>10s)")
    config.addinivalue_line("markers", "invariants: marks invariant tests")
    config.addinivalue_line("markers", "scenarios: marks scenario tests")
    config.addinivalue_line("markers", "performance: marks performance tests")
```

#### Day 5: Create Migration Script

```python
# scripts/migrate_tests.py
import os
import shutil
from pathlib import Path

def migrate_tests():
    """Migrate existing tests to new structure"""
    
    migrations = {
        # Old path -> New path
        'tests/fee_distributions/check_invariants/': 'tests/invariants/core/',
        'tests/round_labeling/': 'tests/components/',
        'tests/round_combinations/': 'tests/integration/',
        'tests/fee_distributions/simple_round_types_tests/': 'tests/scenarios/common/',
        'tests/budget_and_refunds/': 'tests/components/',
        'tests/slashing/': 'tests/scenarios/edge_cases/',
    }
    
    for old, new in migrations.items():
        if os.path.exists(old):
            print(f"Migrating {old} -> {new}")
            # Copy files, not move, so we can verify
            shutil.copytree(old, new, dirs_exist_ok=True)
    
    print("Migration complete. Review and then delete old directories.")

if __name__ == "__main__":
    migrate_tests()
```

### Phase 2: Refactor Existing Tests (Week 2)

#### Invariant Test Refactoring

Old test:
```python
# tests/fee_distributions/check_invariants/invariant_checks.py
def check_invariants(fee_events, budget, transaction):
    check_costs_equal_earnings(fee_events)
    check_party_safety(fee_events, party)
    # ... more checks
```

New test:
```python
# tests/invariants/test_core_invariants.py
import pytest

@pytest.mark.invariants
@pytest.mark.quick
class TestCoreInvariants:
    """Test core system invariants"""
    
    def test_conservation_simple_transaction(self, 
                                           transaction_builder,
                                           invariant_registry):
        """Test value conservation on simple transaction"""
        # Build test case
        state = (transaction_builder
                .with_normal_round(majority="AGREE")
                .build())
        
        # Check invariants
        violations = invariant_registry.check_group(
            InvariantGroup.FINANCIAL, state
        )
        
        assert not violations, f"Invariant violations: {violations}"
    
    @pytest.mark.parametrize("path", load_sample_paths()[:10])
    def test_all_invariants_sample_paths(self, path, invariant_registry):
        """Test all invariants on sample paths"""
        state = create_state_from_path(path)
        violations = invariant_registry.check_critical(state)
        assert not violations
```

#### Scenario Test Refactoring

Old test:
```python
# tests/fee_distributions/simple_round_types_tests/test_normal_round.py
def test_normal_round():
    # 100 lines of setup
    # assertions mixed with logic
```

New test:
```python
# tests/scenarios/common/test_simple_rounds.py
import pytest
from tests.fixtures.builders import TransactionBuilder

@pytest.mark.scenarios
class TestSimpleRounds:
    """Test common single-round scenarios"""
    
    def test_normal_round_majority_agree(self, 
                                        transaction_builder,
                                        oracle,
                                        invariant_registry):
        """Normal round with majority agreement"""
        # Build scenario
        state = (transaction_builder
                .with_normal_round(majority="AGREE", num_validators=5)
                .build())
        
        # Calculate expected
        expected = oracle.calculate_expected(
            state.transaction_results, 
            state.transaction_budget
        )
        
        # Verify outcome
        discrepancies = oracle.verify_actual(
            expected, 
            state.fee_events,
            state.round_labels
        )
        assert not discrepancies
        
        # Check invariants always
        violations = invariant_registry.check_all(state)
        assert not violations
```

### Phase 3: Add New Test Types (Week 3)

#### Property-Based Tests

```python
# tests/invariants/runners/property_runner.py
from hypothesis import given, strategies as st, settings

class PropertyBasedInvariantRunner:
    """Run invariants with property-based testing"""
    
    @given(path=path_strategy(max_length=10))
    @settings(max_examples=1000, deadline=None)
    def test_invariants_hold_for_all_paths(self, path, invariant_registry):
        """Invariants must hold for ANY valid path"""
        state = create_state_from_path(path)
        
        # Only check critical invariants for speed
        violations = invariant_registry.check_critical(state)
        
        assert not violations, (
            f"Invariant violations on path {path}: {violations}"
        )
```

#### Performance Benchmarks

```python
# tests/performance/benchmarks/test_throughput.py
import pytest
import time

@pytest.mark.performance
class TestThroughput:
    """Throughput benchmarks"""
    
    def test_transaction_processing_speed(self, benchmark):
        """Benchmark transaction processing"""
        # Setup
        large_transaction = create_large_transaction(rounds=20)
        
        # Benchmark
        result = benchmark(process_transaction, large_transaction)
        
        # Assert performance requirements
        assert benchmark.stats['mean'] < 0.1  # 100ms average
        assert benchmark.stats['max'] < 0.5   # 500ms worst case
```

### Phase 4: Continuous Integration (Week 4)

```yaml
# .github/workflows/tests.yml
name: Test Suite

on: [push, pull_request]

jobs:
  quick-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - name: Install dependencies
        run: pip install -r requirements-test.txt
      - name: Run quick tests
        run: pytest -m quick --junit-xml=results/quick.xml
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: quick-test-results
          path: results/

  standard-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    needs: quick-tests
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - name: Run standard tests
        run: pytest -m "not slow" --junit-xml=results/standard.xml
        
  comprehensive-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - name: Run all tests including slow
        run: pytest --junit-xml=results/comprehensive.xml
```

## Implementation Examples

### Example 1: Complete Invariant Test

```python
# tests/invariants/test_financial_invariants.py
import pytest
from decimal import Decimal

@pytest.mark.invariants
class TestFinancialInvariants:
    """Test all financial invariants"""
    
    def test_conservation_with_appeals(self, invariant_registry):
        """Test conservation through appeal chains"""
        # Create scenario with multiple appeals
        state = (TransactionBuilder()
                .with_normal_round(majority="AGREE")
                .with_appeal_round("VALIDATOR", successful=False)
                .with_normal_round(majority="UNDETERMINED") 
                .with_appeal_round("LEADER", successful=True)
                .with_normal_round(majority="AGREE")
                .build())
        
        # Check only financial invariants
        violations = invariant_registry.check_group(
            InvariantGroup.FINANCIAL, state
        )
        
        # Detailed assertion for debugging
        for v in violations:
            print(f"Violation: {v.invariant_id}")
            print(f"Message: {v.message}")
            print(f"Context: {v.context}")
        
        assert not violations
    
    @pytest.mark.parametrize("num_appeals", range(1, 17))
    def test_conservation_with_chained_appeals(self, 
                                             num_appeals,
                                             invariant_registry):
        """Test conservation with N chained appeals"""
        builder = TransactionBuilder()
        
        # Build chain of appeals
        for i in range(num_appeals):
            builder.with_normal_round()
            builder.with_appeal_round("VALIDATOR", successful=False)
        
        builder.with_normal_round(majority="UNDETERMINED")
        state = builder.build()
        
        # Should maintain conservation
        violations = invariant_registry.check_group(
            InvariantGroup.FINANCIAL, state
        )
        assert not violations
```

### Example 2: Scenario Test with Oracle

```python
# tests/scenarios/edge_cases/test_all_idle.py
import pytest

@pytest.mark.scenarios
class TestAllIdleScenarios:
    """Test edge case where all validators are idle"""
    
    def test_all_validators_idle(self, oracle, invariant_registry):
        """What happens when everyone is idle?"""
        # Build pathological case
        builder = RoundBuilder()
        round_obj = builder.with_votes({
            addr[0]: ["LEADER_RECEIPT", "IDLE"],
            addr[1]: "IDLE",
            addr[2]: "IDLE",
            addr[3]: "IDLE",
            addr[4]: "IDLE",
        }).build()
        
        state = create_state_with_round(round_obj)
        
        # Oracle tells us expected behavior
        expected = oracle.calculate_expected(
            state.transaction_results,
            state.transaction_budget
        )
        
        # Everyone should be slashed
        for addr in [addr[0], addr[1], addr[2], addr[3], addr[4]]:
            assert addr in expected.burns
            assert expected.burns[addr] > 0
        
        # But invariants should still hold!
        violations = invariant_registry.check_all(state)
        assert not violations
```

### Example 3: Performance Test

```python
# tests/performance/stress/test_path_explosion.py
import pytest
import psutil
import os

@pytest.mark.performance
@pytest.mark.slow
class TestPathExplosion:
    """Test system behavior under path explosion"""
    
    def test_memory_usage_bounded(self):
        """Memory usage should be bounded even with millions of paths"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate paths without storing them all
        path_count = 0
        for path in generate_paths_lazy(max_length=15):
            # Process path
            state = create_state_from_path(path)
            
            # Only keep violations, not all states
            violations = check_critical_invariants(state)
            if violations:
                record_violation(path, violations)
            
            path_count += 1
            if path_count % 10000 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                # Memory should grow sub-linearly
                assert memory_growth < path_count * 0.001  # < 1KB per path
```

## Execution Strategy

### Test Levels

```python
# pytest.ini
[pytest]
markers =
    quick: Quick smoke tests (< 1 minute total)
    standard: Standard test suite (< 10 minutes)
    slow: Slow exhaustive tests (> 10 minutes)
    invariants: Invariant-focused tests
    scenarios: Real-world scenario tests
    performance: Performance benchmarks
    
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Test groups for different contexts
addopts = 
    --strict-markers
    --tb=short
    -ra

[pytest:quick]
addopts = -m "quick" --maxfail=1

[pytest:ci]
addopts = -m "not slow" --maxfail=5

[pytest:full]
addopts = --maxfail=10
```

### Running Tests

```bash
# Quick smoke tests (< 1 minute)
pytest -m quick

# Standard tests for CI (< 10 minutes)  
pytest -m "not slow"

# Only invariant tests
pytest tests/invariants -v

# Specific scenario
pytest tests/scenarios/edge_cases/test_max_appeals.py

# Performance benchmarks
pytest tests/performance --benchmark-only

# Full test suite (overnight)
pytest --cov=fee_simulator --cov-report=html

# Parallel execution
pytest -n auto

# With specific verbosity
pytest --log-cli-level=INFO tests/scenarios
```

## Summary

This architecture provides:

1. **Clear Organization**: Each test has one obvious home
2. **No Duplication**: Shared logic in fixtures and builders  
3. **Progressive Testing**: Quick → Standard → Comprehensive
4. **Invariant-First**: Invariants are the specification
5. **Easy Migration**: Script to move existing tests
6. **Extensible**: Easy to add new test types

The migration can be done incrementally over 4 weeks, with immediate benefits after week 1 when the core infrastructure is in place.