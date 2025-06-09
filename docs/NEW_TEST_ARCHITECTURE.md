# New Test Architecture Proposal

## Overview

After analyzing the current test architecture, this document proposes a comprehensive refactoring to create a more maintainable, scalable, and coherent testing suite. The new architecture will eliminate redundancy, improve organization, and ensure complete coverage with clear separation of concerns.

## Current Issues

### 1. Redundant Test Directories
- `round_types_tests/` and `fee_distributions/simple_round_types_tests/` contain similar tests
- Duplication of test logic across multiple files
- Unclear which tests are authoritative

### 2. Inconsistent Test Organization
- Some tests are organized by feature (slashing, budget)
- Others by round type (normal, appeal)
- Mixed levels of abstraction in the same directories

### 3. Missing Test Categories
- No dedicated performance tests
- Limited stress testing for edge cases
- No regression test suite

### 4. Path-Based Testing Integration
- Path testing is isolated in `round_combinations/`
- Other tests don't leverage the TRANSITIONS_GRAPH
- Inconsistent test data generation

### 5. Invariant Testing Scattered
- Invariants defined in markdown but implemented separately
- Not all tests check invariants
- No central invariant registry

## Proposed New Architecture

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py                    # Enhanced pytest configuration
├── fixtures/                      # Shared test fixtures and utilities
│   ├── __init__.py
│   ├── addresses.py              # Address generation utilities
│   ├── transactions.py           # Transaction builders
│   ├── paths.py                  # Path-based test data generation
│   └── assertions.py             # Custom assertion helpers
│
├── unit/                         # Pure unit tests
│   ├── __init__.py
│   ├── core/                     # Core logic unit tests
│   │   ├── test_majority.py
│   │   ├── test_bond_computing.py
│   │   ├── test_round_labeling.py
│   │   └── test_refunds.py
│   ├── distributions/            # Fee distribution unit tests
│   │   ├── test_normal_round.py
│   │   ├── test_appeals.py
│   │   ├── test_timeouts.py
│   │   └── test_special_cases.py
│   └── utils/                    # Utility function tests
│       ├── test_round_sizes.py
│       └── test_helpers.py
│
├── integration/                  # Integration tests
│   ├── __init__.py
│   ├── test_transaction_flow.py  # End-to-end transaction processing
│   ├── test_round_sequences.py   # Multi-round scenarios
│   ├── test_appeal_chains.py     # Chained appeal scenarios
│   └── test_edge_cases.py        # Complex edge cases
│
├── invariants/                   # Invariant testing framework
│   ├── __init__.py
│   ├── registry.py               # Central invariant registry
│   ├── implementations/          # Invariant implementations
│   │   ├── conservation.py       # Value conservation invariants
│   │   ├── balances.py          # Balance-related invariants
│   │   ├── rounds.py            # Round-specific invariants
│   │   └── votes.py             # Vote consistency invariants
│   └── test_invariants.py        # Invariant test runner
│
├── paths/                        # Path-based testing
│   ├── __init__.py
│   ├── graph_data.py            # TRANSITIONS_GRAPH definition
│   ├── generators/              # Path generation strategies
│   │   ├── exhaustive.py        # Complete enumeration
│   │   ├── random.py            # Random sampling
│   │   └── critical.py          # Critical path selection
│   ├── test_all_paths.py        # Exhaustive path testing
│   └── test_path_properties.py  # Property-based path testing
│
├── performance/                  # Performance and stress tests
│   ├── __init__.py
│   ├── test_throughput.py       # Transaction processing speed
│   ├── test_memory.py           # Memory usage tests
│   └── test_scale.py            # Scalability tests
│
├── regression/                   # Regression test suite
│   ├── __init__.py
│   ├── snapshots/               # Expected output snapshots
│   └── test_regression.py       # Regression test runner
│
└── e2e/                         # End-to-end acceptance tests
    ├── __init__.py
    ├── scenarios/               # Business scenario definitions
    └── test_scenarios.py        # Scenario test runner
```

## Key Improvements

### 1. Clear Separation of Concerns

#### Unit Tests (`unit/`)
- Test individual functions in isolation
- No dependencies on other components
- Fast execution (< 100ms per test)
- Mock all external dependencies

#### Integration Tests (`integration/`)
- Test component interactions
- Use real implementations
- Verify data flow between components
- Check invariants at integration points

#### End-to-End Tests (`e2e/`)
- Test complete business scenarios
- Verify from user perspective
- Include setup and teardown
- Test against production-like data

### 2. Centralized Invariant System

```python
# invariants/registry.py
class InvariantRegistry:
    def __init__(self):
        self._invariants = {}
    
    def register(self, name: str, invariant: Invariant):
        self._invariants[name] = invariant
    
    def check_all(self, state: SystemState) -> List[Violation]:
        violations = []
        for name, invariant in self._invariants.items():
            if not invariant.check(state):
                violations.append(Violation(name, invariant.describe()))
        return violations

# Usage in tests
@pytest.fixture
def invariant_checker():
    registry = InvariantRegistry()
    registry.register("conservation", ConservationInvariant())
    registry.register("non_negative", NonNegativeBalanceInvariant())
    # ... register all invariants
    return registry

def test_transaction_maintains_invariants(invariant_checker):
    # Process transaction
    result = process_transaction(...)
    
    # Check all invariants
    violations = invariant_checker.check_all(result)
    assert not violations, f"Invariant violations: {violations}"
```

### 3. Path-Based Test Generation

```python
# fixtures/paths.py
class PathBasedTestGenerator:
    def __init__(self, graph=TRANSITIONS_GRAPH):
        self.graph = graph
    
    def generate_test_case(self, path: List[str]) -> TransactionTestCase:
        """Convert a path to a complete test case"""
        transaction = path_to_transaction_results(path)
        budget = self._compute_budget(path)
        expected_labels = self._compute_expected_labels(path)
        return TransactionTestCase(transaction, budget, expected_labels)
    
    def generate_all_test_cases(self, max_length: int):
        """Generate all test cases up to max_length"""
        paths = generate_all_paths(self.graph, max_length)
        return [self.generate_test_case(path) for path in paths]

# Usage in tests
@pytest.mark.parametrize("test_case", 
    PathBasedTestGenerator().generate_all_test_cases(7))
def test_all_paths_length_7(test_case, invariant_checker):
    result = process_transaction(test_case.transaction, test_case.budget)
    assert result.labels == test_case.expected_labels
    assert not invariant_checker.check_all(result)
```

### 4. Shared Fixtures and Utilities

```python
# fixtures/transactions.py
class TransactionBuilder:
    """Fluent interface for building test transactions"""
    
    def __init__(self):
        self._rounds = []
        self._budget = None
    
    def with_normal_round(self, votes: Dict[str, Vote]):
        self._rounds.append(Round(rotations=[Rotation(votes=votes)]))
        return self
    
    def with_appeal_round(self, appeal_type: str):
        votes = self._generate_appeal_votes(appeal_type)
        self._rounds.append(Round(rotations=[Rotation(votes=votes)]))
        return self
    
    def with_budget(self, **kwargs):
        self._budget = TransactionBudget(**kwargs)
        return self
    
    def build(self) -> Tuple[TransactionRoundResults, TransactionBudget]:
        return TransactionRoundResults(rounds=self._rounds), self._budget

# Usage
def test_normal_round_majority_agree():
    transaction, budget = (TransactionBuilder()
        .with_normal_round({
            addr[0]: ["LEADER_RECEIPT", "AGREE"],
            addr[1]: "AGREE",
            addr[2]: "AGREE",
            addr[3]: "DISAGREE",
            addr[4]: "DISAGREE"
        })
        .with_budget(leaderTimeout=100, validatorsTimeout=200)
        .build())
    
    # Test implementation
```

### 5. Performance Testing Framework

```python
# performance/test_throughput.py
class TestThroughput:
    @pytest.mark.performance
    def test_transaction_processing_speed(self, benchmark):
        """Ensure transaction processing meets performance targets"""
        transaction = create_large_transaction(rounds=20)
        
        # Benchmark the processing
        result = benchmark(process_transaction, transaction)
        
        # Assert performance requirements
        assert benchmark.stats['mean'] < 0.1  # 100ms average
        assert benchmark.stats['max'] < 0.5   # 500ms worst case
    
    @pytest.mark.performance
    def test_path_generation_performance(self):
        """Test path generation doesn't exceed memory limits"""
        import tracemalloc
        tracemalloc.start()
        
        # Generate paths
        paths = list(generate_all_paths(TRANSITIONS_GRAPH, 7))
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        assert peak < 1_000_000_000  # Less than 1GB
```

### 6. Regression Testing

```python
# regression/test_regression.py
class TestRegression:
    def test_fee_distribution_snapshot(self, snapshot):
        """Ensure fee distribution hasn't changed unexpectedly"""
        # Create known scenario
        transaction = create_standard_test_transaction()
        
        # Process
        fee_events, labels = process_transaction(transaction)
        
        # Compare with snapshot
        snapshot.assert_match(serialize_fee_events(fee_events))
    
    def test_round_labeling_snapshot(self, snapshot):
        """Ensure round labeling hasn't changed"""
        for path in CRITICAL_PATHS:
            transaction = path_to_transaction_results(path)
            labels = label_rounds(transaction)
            snapshot.assert_match(f"{path}: {labels}")
```

## Migration Strategy

### Phase 1: Setup New Structure (Week 1)
1. Create new directory structure
2. Set up enhanced conftest.py
3. Create shared fixtures
4. Implement invariant registry

### Phase 2: Migrate Unit Tests (Week 2)
1. Move and refactor unit tests to new structure
2. Remove redundancies
3. Improve test isolation
4. Add missing unit tests

### Phase 3: Migrate Integration Tests (Week 3)
1. Consolidate integration tests
2. Create transaction flow tests
3. Add invariant checking to all tests
4. Remove duplicate test logic

### Phase 4: Enhance Path Testing (Week 4)
1. Integrate path testing with other tests
2. Create parametrized tests from paths
3. Add property-based path testing
4. Optimize path generation

### Phase 5: Add New Test Types (Week 5)
1. Create performance test suite
2. Set up regression testing
3. Add e2e scenario tests
4. Create stress tests

### Phase 6: Documentation and CI (Week 6)
1. Update all test documentation
2. Create test writing guide
3. Set up CI pipelines
4. Create test coverage reports

## Benefits of New Architecture

### 1. Maintainability
- Clear organization reduces cognitive load
- Easy to find and update tests
- Reduced duplication means fewer places to fix bugs

### 2. Scalability
- Easy to add new test types
- Path-based generation scales to new scenarios
- Performance tests prevent regressions

### 3. Reliability
- Invariant checking catches subtle bugs
- Regression tests prevent breaking changes
- Complete coverage through path testing

### 4. Developer Experience
- Shared fixtures reduce boilerplate
- Clear patterns for writing new tests
- Fast feedback from focused unit tests

### 5. Confidence
- Every code path tested through exhaustive testing
- Business rules encoded in invariants
- Performance guarantees through benchmarks

## Success Metrics

### Coverage Metrics
- Line coverage: 100%
- Branch coverage: 100%
- Path coverage: 100% up to length 7

### Performance Metrics
- Unit test suite: < 5 seconds
- Integration tests: < 30 seconds
- Full test suite: < 5 minutes (excluding exhaustive)

### Quality Metrics
- Zero flaky tests
- All tests independent
- Clear failure messages

### Maintenance Metrics
- No duplicate test logic
- All tests follow patterns
- New tests easy to add

## Conclusion

This new test architecture addresses all current issues while providing a solid foundation for future growth. The migration can be done incrementally without disrupting current development, and the benefits will be immediate in terms of test clarity, reliability, and maintainability.

The key insight is that tests are not just about verification—they're about encoding business knowledge, preventing regressions, and giving developers confidence to make changes. This architecture treats tests as first-class citizens in the codebase.