# GenLayer Fee Distribution Simulator

## Overview

The GenLayer Fee Distribution Simulator is a comprehensive Python-based system for modeling and testing fee distribution mechanisms in the GenLayer blockchain validator network. It uses a path-based approach to exhaustively test all possible transaction scenarios, ensuring correctness through rigorous invariant checking.

The simulator follows a deterministic flow: **TRANSITIONS_GRAPH → Path → TransactionRoundResults → Round Labels → Fee Distribution**, where each step is purely functional and content-based rather than index-based.

## Key Features

- **Path-Based Testing**: Generates all valid transaction paths from TRANSITIONS_GRAPH for exhaustive testing
- **Content-Based Round Detection**: Identifies round types by analyzing vote patterns, not indices
- **22 Invariants**: Comprehensive invariant checking ensures correctness (conservation of value, non-negative balances, etc.)
- **Role-Based Fee Distribution**: Allocates fees based on participant roles (Leader, Validator, Sender, Appealant)
- **Appeal Mechanisms**: Handles leader and validator appeals with proper bond calculations
- **Special Pattern Recognition**: Automatically transforms round labels based on transaction patterns
- **Visualization Tools**: Rich formatted tables for transaction results and fee distributions
- **Modular Architecture**: Clean separation between path generation, transaction processing, and fee distribution

## Project Structure

```
fee_simulator/
├── core/                     # Core logic
│   ├── round_fee_distribution/  # Fee distribution strategies
│   │   ├── normal_round.py
│   │   ├── appeal_*_successful.py
│   │   ├── appeal_*_unsuccessful.py
│   │   ├── leader_timeout_*.py
│   │   └── split_previous_appeal_bond.py
│   ├── path_to_transaction.py   # Path → Transaction converter
│   ├── round_labeling.py        # Content-based round type detection
│   ├── transaction_processing.py # Main processing pipeline
│   ├── bond_computing.py        # Appeal bond calculations
│   ├── majority.py              # Vote outcome determination
│   └── refunds.py               # Sender refund logic
├── models.py                 # Data structures (immutable)
├── constants.py              # NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES
├── types.py                  # Type definitions
└── display/                  # Visualization utilities

tests/
├── round_combinations/       # Path generation from TRANSITIONS_GRAPH
│   ├── graph_data.py        # The source of truth graph
│   └── generate_paths.py    # Path generation logic
├── round_labeling/          # Round detection tests
├── fee_distributions/       # Fee distribution tests
│   ├── simple_round_types_tests/
│   └── check_invariants/    # 22 invariant implementations
└── invariant_checks.py      # Invariant verification
```
- `requirements.txt`: Lists project dependencies.

## How It Works

### Processing Pipeline

```
1. TRANSITIONS_GRAPH defines valid state transitions
   ↓
2. Path Generator creates sequences like:
   ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "APPEAL_VALIDATOR_SUCCESSFUL", "END"]
   ↓
3. Path-to-Transaction converter creates TransactionRoundResults with appropriate votes
   ↓
4. Round Labeling analyzes vote patterns (content-based, not index-based):
   - All NA votes → Leader Appeal
   - LEADER_TIMEOUT → Leader Timeout
   - AGREE/DISAGREE without leader → Validator Appeal
   ↓
5. Fee Distribution based on labels:
   - NORMAL_ROUND → Leader and majority validators earn
   - APPEAL_*_SUCCESSFUL → Appealant earns bond
   - Special patterns trigger transformations
   ↓
6. Invariant Checking ensures correctness
```

### Round Type Detection

Rounds are identified by their vote patterns, not their position:

- **Leader Appeals**: All participants vote "NA"
- **Validator Appeals**: No LEADER_RECEIPT, validators vote AGREE/DISAGREE
- **Normal Rounds**: Have LEADER_RECEIPT or LEADER_TIMEOUT
- **Special Patterns**: e.g., successful appeal makes previous round SKIP_ROUND

### Key Concepts

1. **Vote Types**:
   - `LEADER_RECEIPT`: Leader submitted result
   - `LEADER_TIMEOUT`: Leader failed to respond
   - `AGREE`/`DISAGREE`/`TIMEOUT`: Validator votes
   - `NA`: Not applicable (appeals)

2. **Round Sizes**:
   - Normal rounds: [5, 11, 23, 47, 95, 191, 383, 767, 1000]
   - Appeal rounds: [7, 13, 25, 49, 97, 193, 385, 769, 1000]

3. **Fee Distribution**:
   - Leader earns: leader_timeout + validator_timeout (if majority)
   - Validators earn: validator_timeout (if in majority)
   - Penalties: PENALTY_REWARD_COEFFICIENT * validator_timeout

## Installation

1. Clone the repository:
    
    ```bash
    git clone <repository_url>
    cd genlayer-fee-simulator
    ```
    
2. Create a virtual environment and activate it:
    
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
    
3. Install dependencies:
    
    ```bash
    pip install -r requirements.txt
    ```
    

## Usage

### Running Tests

To run the entire test suite:

```bash
pytest
```

To run the entire test suite and log all the results in a file for future analysis:

```
pytest -s --verbose-output --debug-output > tests.txt 
```

And then `cat tests.txt` to visualize it.

To run a specific test with verbose and debug output (displays formatted tables):

```bash
pytest tests/round_types_tests/test_normal_round.py -s --verbose-output --debug-output
```

### Creating Custom Scenarios

You can create and simulate custom transaction scenarios programmatically:

```python
from fee_simulator.models import TransactionBudget, TransactionRoundResults, Round, Rotation, FeeEvent
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.utils import generate_random_eth_address
from fee_simulator.display import display_summary_table, display_transaction_results, display_fee_distribution

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(6)]

# Define budget
budget = TransactionBudget(
    leaderTimeout=100,
    validatorsTimeout=200,
    appealRounds=0,
    rotations=[0],
    senderAddress=addresses[5],
    appeals=[],
    staking_distribution="constant"
)

# Define transaction results
rotation = Rotation(
    votes={
        addresses[0]: ["LEADER_RECEIPT", "AGREE"],
        addresses[1]: "AGREE",
        addresses[2]: "AGREE",
        addresses[3]: "AGREE",
        addresses[4]: "DISAGREE"
    }
)
results = TransactionRoundResults(rounds=[Round(rotations=[rotation])])

# Process transaction
fee_events, round_labels = process_transaction(addresses, results, budget)

# Display results
display_summary_table(fee_events, results, budget, round_labels)
display_transaction_results(results, round_labels)
display_fee_distribution(fee_events)
```

## Testing Framework

The test suite covers:

- **Unit Tests**: Validate individual components (e.g., budget calculations, refunds).
- **Scenario-Based Tests**: Test specific round types (e.g., `test_normal_round.py`, `test_appeal_leader_successful.py`).
- **Slashing Tests**: Verify slashing for idleness and deterministic violations.
- **Edge Cases**: Handle scenarios like empty rounds, undetermined majorities, and unsuccessful appeals.

Run tests with verbose output to inspect detailed fee distributions and transaction outcomes.

## Use Cases

- **Economic Analysis**: Evaluate the incentive structure of the GenLayer protocol.
- **Protocol Validation**: Simulate fee distribution before deploying protocol changes.
- **Education**: Understand blockchain consensus and fee mechanics.
- **Development**: Test and refine fee distribution algorithms.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
