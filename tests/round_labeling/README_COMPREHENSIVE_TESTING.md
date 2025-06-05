# Comprehensive Path Testing Framework

This framework enables testing of all possible paths (133M+) through the transaction state graph for round labeling validation.

## Quick Start

### Run specific test sets:
```bash
# Quick smoke tests (seconds)
pytest test_all_paths_comprehensive.py -m quick

# First 500 paths
pytest test_all_paths_comprehensive.py -m first_500

# Last 500 paths  
pytest test_all_paths_comprehensive.py -m last_500

# Paths with 13-16 rounds
pytest test_all_paths_comprehensive.py -m rounds_13_to_16

# Specific range (e.g., paths 1M to 1.001M)
pytest test_all_paths_comprehensive.py -k "test_path_range[1000000:1001000]"

# ALL paths (WARNING: extremely slow!)
pytest test_all_paths_comprehensive.py -m all_paths
```

### Using the helper script:
```bash
# Make it executable (first time only)
chmod +x run_path_tests.py

# Run quick tests
./run_path_tests.py --quick

# Test first 1000 paths
./run_path_tests.py --first 1000

# Test paths with 13-16 rounds
./run_path_tests.py --rounds 13 16

# Estimate total path counts
./run_path_tests.py --estimate

# Run with parallel workers
./run_path_tests.py --first 1000 -n 8
```

## Architecture

### Key Components:

1. **PathGenerator**: Efficiently generates paths with filtering
   - Supports batch generation for memory efficiency
   - Can filter by round count
   - Caches total count estimates

2. **PathToTransaction**: Converts graph paths to transaction data
   - Creates appropriate vote distributions
   - Handles appeal rounds correctly
   - Generates valid transaction budgets

3. **RoundLabelingInvariants**: Validates all labeling rules
   - Every round gets a label
   - All labels are valid
   - Appeals at odd indices

### Test Categories:

- **@pytest.mark.quick**: Basic smoke tests (~10 paths)
- **@pytest.mark.first_500**: First 500 paths
- **@pytest.mark.last_500**: Last 500 paths
- **@pytest.mark.rounds_13_to_16**: Specific round counts
- **@pytest.mark.all_paths**: ALL paths (use with caution!)

## Performance Considerations

- Pre-generated address pool for efficiency
- Batch processing to manage memory
- Progress indicators for long runs
- Parallel execution support with pytest-xdist

## Custom Testing

To test a specific subset:
```python
@pytest.mark.custom_range
class TestCustomRange:
    def test_my_range(self):
        generator = PathGenerator()
        paths = generator.generate_paths_batch(50000, 100)
        # Test your specific paths
```

## Important Notes

1. Testing all 133M paths will take several days/weeks even with parallelization
2. Use targeted subsets for regular CI/CD
3. The framework validates both labeling logic and fee distribution
4. Each path is deterministically generated - same input always produces same path