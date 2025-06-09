# Test Architecture Documentation

## Overview

The GenLayer Fee Distribution Simulator employs a comprehensive testing strategy designed to ensure mathematical correctness and production-ready reliability for blockchain financial operations. The test suite uses multiple testing approaches to achieve 100% coverage of all possible transaction scenarios.

## Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py                          # Pytest configuration and global fixtures
├── invariant_checks.py                  # Common invariant assertion helpers
│
├── budget_and_refunds/                  # Budget and refund mechanism tests
│   ├── test_budget_computing.py
│   └── test_refunds.py
│
├── fee_distributions/                   # Core fee distribution testing
│   ├── INVARIANTS_DESIGN.md            # 22 invariants documentation
│   ├── check_invariants/               # Invariant implementation
│   │   ├── comprehensive_invariants.py
│   │   ├── invariant_checks.py
│   │   ├── test_invariants_in_round_combinations.py
│   │   └── analyze_tests_results.py
│   ├── simple_round_types_tests/       # Individual round type tests
│   │   ├── test_normal_round.py
│   │   ├── test_appeal_leader_successful.py
│   │   ├── test_appeal_validator_successful.py
│   │   └── test_leader_timeout_*.py
│   └── unit_tests/                     # Unit tests for distribution functions
│       └── test_fee_distribution_functions.py
│
├── round_combinations/                  # Exhaustive path testing
│   ├── graph_data.py                   # TRANSITIONS_GRAPH (source of truth)
│   ├── path_generator.py               # DFS path generation
│   ├── path_counter.py                 # Matrix-based counting
│   ├── path_analyzer.py                # Statistical analysis
│   └── critical_path_analyzer.py       # Production verification
│
├── round_labeling/                     # Round type detection tests
│   ├── test_round_labeling.py          # Core labeling tests
│   ├── test_round_labeling_advanced.py # Complex scenarios
│   ├── test_round_labeling_properties.py # Property-based testing
│   └── test_all_paths_comprehensive.py # Exhaustive testing
│
├── round_types_tests/                  # Legacy round type tests
│   ├── test_normal_round.py
│   ├── test_appeal_*.py
│   └── test_leader_timeout_*.py
│
├── slashing/                           # Penalty mechanism tests
│   ├── test_deterministic_violation.py # Hash mismatch penalties
│   ├── test_idleness.py               # Idle validator penalties
│   └── test_tribunal_appeal.py        # Tribunal mechanisms
│
└── unittests/                          # Additional unit tests
    └── (various unit test files)
```

## Testing Framework

### Core Framework: Pytest
- Custom command-line options: `--verbose-output`, `--debug-output`
- Fixture-based test organization
- Parametrized test support
- Custom markers for test categorization

### Additional Frameworks
- **Hypothesis**: Property-based testing for round labeling
- **NumPy**: Matrix operations for path counting
- **Custom Display Utilities**: Rich table formatting for test output

## Testing Approaches

### 1. Unit Testing
**Purpose**: Test individual functions in isolation

**Characteristics**:
- Direct function calls with mock data
- Single responsibility testing
- Fast execution
- High granularity

**Example Pattern**:
```python
def test_compute_appeal_bond():
    # Test specific bond calculation
    bond = compute_appeal_bond(
        normal_round_index=0,
        leader_timeout=100,
        validators_timeout=200,
        round_labels=["NORMAL_ROUND", "APPEAL_LEADER"]
    )
    assert bond == 1500  # 7 * 200 + 100
```

### 2. Integration Testing
**Purpose**: Test complete transaction processing pipelines

**Characteristics**:
- End-to-end transaction flow
- Multiple component interaction
- Real-world scenario simulation
- Invariant verification

**Example Pattern**:
```python
def test_complete_transaction_flow():
    # Setup transaction
    transaction = create_transaction_with_appeals()
    
    # Process through pipeline
    fee_events, labels = process_transaction(transaction)
    
    # Verify invariants
    check_comprehensive_invariants(fee_events, transaction, labels)
```

### 3. Property-Based Testing
**Purpose**: Discover edge cases through random generation

**Characteristics**:
- Hypothesis framework integration
- Automatic shrinking to minimal failing cases
- Mathematical property verification
- Unbounded test case generation

**Example Pattern**:
```python
@given(
    num_rounds=st.integers(min_value=1, max_value=10),
    appeal_pattern=st.lists(st.booleans())
)
def test_round_labeling_properties(num_rounds, appeal_pattern):
    # Generate transaction from parameters
    # Verify properties hold for all inputs
```

### 4. Exhaustive Path Testing
**Purpose**: Test every possible transaction path

**Characteristics**:
- Complete state space exploration
- Dual verification (counting + generation)
- Production-ready guarantees
- Checkpoint support for long runs

**Key Components**:
- **Path Counter**: Matrix multiplication for counting
- **Path Generator**: DFS for actual path generation
- **Path Analyzer**: Statistical validation
- **Critical Path Analyzer**: Production verification

### 5. Invariant Testing
**Purpose**: Ensure mathematical and business rules always hold

**22 Core Invariants**:
1. Conservation of value
2. Non-negative balances
3. Appeal bond coverage
4. Majority/minority consistency
5. Role exclusivity
6. Sequential processing
7. Appeal follows normal
8. Burn non-negativity
9. Refund non-negativity
10. Vote consistency
11. Idle slashing correctness
12. Deterministic violation slashing
13. Leader timeout earning limits
14. Single leader per round
15. Complete round processing
16. Unique sequence IDs
17. Sender balance consistency
18. Appeal bond payment
19. Vote count accuracy
20. Hash consistency
21. Stake conservation
22. Deterministic fee distribution

## Test Organization Patterns

### File Naming Conventions
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Helper functions: `_helper_*` or utility modules

### Test Structure Template
```python
class TestFeatureArea:
    """Docstring explaining test area"""
    
    def setup_method(self):
        """Per-test setup"""
        self.addresses = [generate_random_eth_address() for _ in range(20)]
        self.event_sequence = EventSequence()
    
    def test_specific_scenario(self, verbose, debug):
        """Test docstring explaining scenario"""
        # Arrange
        transaction = self._create_test_transaction()
        
        # Act
        result = function_under_test(transaction)
        
        # Assert invariants
        check_invariants(result)
        
        # Assert specific outcomes
        assert result.specific_field == expected_value
        
        # Display results if verbose
        if verbose:
            display_test_results(result)
```

### Common Test Utilities

#### Address Generation
```python
addresses = [generate_random_eth_address() for _ in range(n)]
```

#### Transaction Creation
```python
# From path
transaction = path_to_transaction_results(path, addresses)

# Manual creation
transaction = TransactionRoundResults(
    rounds=[Round(rotations=[Rotation(votes={...})])]
)
```

#### Invariant Checking
```python
# Single invariant
check_conservation_of_value(fee_events, budget, labels)

# All invariants
check_comprehensive_invariants(fee_events, budget, transaction, labels)
```

## Configuration and Fixtures

### Global Fixtures (conftest.py)
```python
@pytest.fixture
def verbose(request):
    """Enable verbose output when --verbose-output is passed"""
    return request.config.getoption("--verbose-output")

@pytest.fixture
def debug(request):
    """Enable debug output when --debug-output is passed"""
    return request.config.getoption("--debug-output")
```

### Custom Command Options
- `--verbose-output`: Display summary tables and results
- `--debug-output`: Display detailed transaction data

### Test Markers
- `@pytest.mark.slow`: Long-running tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.unit`: Unit tests

## Test Execution Patterns

### Running Tests
```bash
# All tests
pytest

# Specific directory
pytest tests/fee_distributions/

# Specific file
pytest tests/round_labeling/test_round_labeling.py

# With verbose output
pytest -s --verbose-output --debug-output

# Specific test
pytest tests/round_types_tests/test_normal_round.py::test_specific_case
```

### Test Output
- Standard: Pass/fail indicators
- Verbose: Formatted tables showing fee distributions
- Debug: Complete transaction details and intermediate states

## Coverage Strategy

### Code Coverage
- Target: 100% line coverage
- Tool: pytest-cov
- Critical paths must have multiple test approaches

### Scenario Coverage
- All round types
- All vote combinations
- All appeal patterns
- Edge cases (empty rounds, timeouts, etc.)
- Chained scenarios (up to 16 appeals)

### Path Coverage
- Exhaustive testing up to length 7 (mandatory)
- Statistical sampling for lengths 8-19
- Critical path identification and testing

## Performance Considerations

### Test Execution Time
- Unit tests: < 1 second each
- Integration tests: < 5 seconds each
- Exhaustive tests: May take hours (use checkpoints)

### Resource Usage
- Memory: Path testing can use significant memory
- CPU: Matrix operations are compute-intensive
- Disk: Checkpoint files for long-running tests

## Best Practices

### Test Independence
- Each test must be completely independent
- No shared state between tests
- Deterministic random seeds when needed

### Clear Test Names
- Test names should describe the scenario
- Include expected outcome in name when relevant
- Group related tests in classes

### Assertion Messages
- Include context in assertion messages
- Show actual vs expected values
- Reference invariant numbers when applicable

### Documentation
- Each test file should have a module docstring
- Complex tests need inline comments
- Reference the business rules being tested

## Continuous Integration

### Test Stages
1. **Fast Tests**: Unit tests and basic integration
2. **Full Tests**: All tests except exhaustive
3. **Exhaustive Tests**: Complete path verification (nightly)

### Failure Handling
- Tests must fail fast with clear messages
- Invariant violations must identify which invariant failed
- Include transaction state in failure output

## Future Considerations

### Scalability
- Parallel test execution for path testing
- Distributed testing for exhaustive verification
- Test result caching for regression testing

### Maintenance
- Regular review of test coverage
- Update tests when business rules change
- Refactor tests to reduce duplication

### Monitoring
- Track test execution times
- Monitor flaky tests
- Analyze failure patterns