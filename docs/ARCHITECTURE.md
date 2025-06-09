# GenLayer Fee Distribution Simulator Architecture

## Table of Contents
1. [Overview](#overview)
2. [Core Architecture](#core-architecture)
3. [Data Flow](#data-flow)
4. [Key Components](#key-components)
5. [Round Types and Labeling](#round-types-and-labeling)
6. [Fee Distribution Logic](#fee-distribution-logic)
7. [Testing Architecture](#testing-architecture)
8. [Recent Refactors](#recent-refactors)

## Overview

The GenLayer Fee Distribution Simulator is a comprehensive system for modeling and testing fee distribution mechanisms in a blockchain validator network. It simulates complex transaction scenarios involving validators, leaders, appeals, and various edge cases to ensure correct fee distribution.

### Key Design Principles
- **Path-based Flow**: The system follows a deterministic flow from graph paths to fee distributions
- **Content-based Detection**: Round types are determined by vote patterns, not indices
- **Immutable Data Structures**: All fee events are immutable for auditability
- **Comprehensive Testing**: Every path through the system is tested with invariants

## Core Architecture

```mermaid
graph TB
    subgraph "Input Layer"
        TG[TRANSITIONS_GRAPH]
        PC[Path Constraints]
    end
    
    subgraph "Path Generation"
        PG[Path Generator]
        TG --> PG
        PC --> PG
    end
    
    subgraph "Transaction Creation"
        PTT[Path to Transaction Converter]
        TB[Transaction Budget]
        TR[Transaction Round Results]
        PG --> PTT
        PTT --> TR
        PTT --> TB
    end
    
    subgraph "Processing Layer"
        RL[Round Labeling]
        TP[Transaction Processing]
        TR --> RL
        RL --> TP
        TB --> TP
    end
    
    subgraph "Distribution Layer"
        DR[Distribute Round]
        NR[Normal Round]
        AS[Appeal Successful]
        AU[Appeal Unsuccessful]
        LT[Leader Timeout]
        SB[Split Bond]
        TP --> DR
        DR --> NR
        DR --> AS
        DR --> AU
        DR --> LT
        DR --> SB
    end
    
    subgraph "Output Layer"
        FE[Fee Events]
        REF[Refunds]
        DR --> FE
        FE --> REF
    end
```

## Data Flow

The system follows a strict unidirectional data flow:

```mermaid
sequenceDiagram
    participant G as TRANSITIONS_GRAPH
    participant P as Path
    participant T as TransactionRoundResults
    participant L as Round Labels
    participant F as Fee Events
    
    G->>P: Generate valid paths
    P->>T: Convert to transaction structure
    T->>L: Label rounds by content
    L->>F: Distribute fees by label
    F->>F: Calculate refunds
```

### 1. **Graph → Path**
- The `TRANSITIONS_GRAPH` defines all valid state transitions
- Path generator creates sequences like `["START", "LEADER_RECEIPT_MAJORITY_AGREE", "APPEAL_VALIDATOR_SUCCESSFUL", "END"]`

### 2. **Path → Transaction**
- `path_to_transaction.py` converts paths to `TransactionRoundResults`
- Creates appropriate vote patterns for each node type
- Generates `TransactionBudget` with appeal information

### 3. **Transaction → Labels**
- `round_labeling.py` analyzes vote patterns to determine round types
- No dependency on round indices - purely content-based
- Applies special pattern transformations (e.g., SKIP_ROUND)

### 4. **Labels → Fees**
- `distribute_round.py` routes to specific distribution functions
- Each label has a corresponding fee distribution strategy
- Events are immutable and include all transaction details

## Key Components

### Models (`models.py`)
```python
# Core data structures
TransactionRoundResults  # Contains all rounds in a transaction
Round                   # Contains rotations (re-elections)
Rotation               # Contains votes from participants
TransactionBudget      # Defines costs and appeals
FeeEvent              # Immutable record of fee changes
Appeal                # Appeal information with appealant address
```

### Constants
```python
# Round sizes (after ROUND_SIZES split)
NORMAL_ROUND_SIZES = [5, 11, 23, 47, 95, 191, 383, 767, 1000]
APPEAL_ROUND_SIZES = [7, 13, 25, 49, 97, 193, 385, 769, 1000]

# Penalty coefficients
PENALTY_REWARD_COEFFICIENT = 1
IDLE_PENALTY_COEFFICIENT = 10
DETERMINISTIC_VIOLATION_PENALTY_COEFFICIENT = 100
```

### Vote Types
- `LEADER_RECEIPT`: Leader successfully submitted a result
- `LEADER_TIMEOUT`: Leader failed to submit in time
- `AGREE`/`DISAGREE`: Validator votes on leader's submission
- `TIMEOUT`: Validator didn't vote in time
- `IDLE`: Validator was idle (replaced)
- `NA`: Not applicable (used in appeals)

## Round Types and Labeling

### Detection Logic
Round types are detected based on vote patterns, not indices:

```mermaid
graph TD
    V[Votes in Round]
    V --> A{All NA votes?}
    A -->|Yes| LA[Leader Appeal]
    A -->|No| B{Has LEADER_TIMEOUT?}
    B -->|Yes| LT[Leader Timeout Round]
    B -->|No| C{Has LEADER_RECEIPT?}
    C -->|Yes| NR[Normal Round]
    C -->|No| D{Has AGREE/DISAGREE?}
    D -->|Yes| VA[Validator Appeal]
    D -->|No| ER[Empty Round]
```

### Round Labels
1. **Normal Rounds**
   - `NORMAL_ROUND`: Standard round with clear outcome
   - `LEADER_TIMEOUT`: Leader failed to respond
   - `SKIP_ROUND`: Retroactively skipped due to successful appeal

2. **Appeal Rounds**
   - `APPEAL_LEADER_SUCCESSFUL/UNSUCCESSFUL`: Leader being appealed
   - `APPEAL_VALIDATOR_SUCCESSFUL/UNSUCCESSFUL`: Validators appealing majority
   - `APPEAL_LEADER_TIMEOUT_SUCCESSFUL/UNSUCCESSFUL`: Timeout being appealed

3. **Special Cases**
   - `LEADER_TIMEOUT_50_PERCENT`: Single timeout round
   - `LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND`: After successful timeout appeal
   - `LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND`: After unsuccessful appeal
   - `SPLIT_PREVIOUS_APPEAL_BOND`: Undetermined after unsuccessful appeal

### Pattern Transformations
Special patterns trigger label transformations:

```python
# Example: Skip round before successful appeal
["NORMAL_ROUND", "APPEAL_LEADER_SUCCESSFUL", "NORMAL_ROUND"]
# Transforms to:
["SKIP_ROUND", "APPEAL_LEADER_SUCCESSFUL", "NORMAL_ROUND"]
```

## Fee Distribution Logic

### Distribution Router
```mermaid
graph LR
    L[Round Label] --> D{Distribute Round}
    D --> |NORMAL_ROUND| NR[apply_normal_round]
    D --> |APPEAL_*_SUCCESSFUL| AS[apply_appeal_successful]
    D --> |APPEAL_*_UNSUCCESSFUL| AU[apply_appeal_unsuccessful]
    D --> |LEADER_TIMEOUT_*| LT[apply_leader_timeout_variant]
    D --> |SPLIT_PREVIOUS_APPEAL_BOND| SB[apply_split_bond]
```

### Fee Event Structure
```python
FeeEvent(
    sequence_id=1,          # Global sequence number
    address="0x...",        # Participant address
    round_index=0,          # Round in transaction
    round_label="NORMAL_ROUND",
    role="VALIDATOR",       # LEADER, VALIDATOR, APPEALANT, SENDER
    vote="AGREE",          
    earned=200,            # Amount earned
    cost=0,                # Amount paid
    burned=0,              # Amount burned (penalties)
    slashed=0,             # Amount slashed
    staked=0               # Stake changes
)
```

### Distribution Examples

#### Normal Round (Majority Agree)
- Leader: Earns `leader_timeout + validator_timeout`
- Majority validators: Earn `validator_timeout`
- Minority validators: Burned `PENALTY_REWARD_COEFFICIENT * validator_timeout`

#### Successful Appeal
- Appealant: Earns `appeal_bond + leader_timeout` (leader appeal) or `appeal_bond` (validator appeal)
- Validators: Distribution depends on appeal type

#### Split Bond (Undetermined after unsuccessful appeal)
- Leader: Earns `leader_timeout`
- Validators: Split the appeal bond equally

## Testing Architecture

### Test Categories

```mermaid
graph TD
    T[Tests]
    T --> U[Unit Tests]
    T --> I[Integration Tests]
    T --> P[Path-based Tests]
    T --> V[Invariant Tests]
    
    U --> UF[Fee Functions]
    U --> RL[Round Labeling]
    
    I --> TC[Transaction Complete]
    
    P --> CP[Combination Paths]
    P --> EP[Edge Cases]
    
    V --> CI[Conservation]
    V --> SI[State Invariants]
    V --> BI[Business Rules]
```

### 1. **Unit Tests** (`tests/unittests/`)
- Test individual functions in isolation
- Mock dependencies
- Fast execution

### 2. **Round Labeling Tests** (`tests/round_labeling/`)
- Test pattern detection
- Verify special case transformations
- Test with generated paths from graph

### 3. **Fee Distribution Tests** (`tests/fee_distributions/`)
- `simple_round_types_tests/`: Test each round type individually
- `check_invariants/`: Comprehensive invariant checking
- Integration tests with full transaction flow

### 4. **Path Combination Tests** (`tests/round_combinations/`)
- Generate all valid paths from `TRANSITIONS_GRAPH`
- Test exhaustively up to certain lengths
- Verify invariants hold for all paths

### Invariants
The system maintains 22 critical invariants:

1. **Conservation of Value**: Total costs = earnings + burns + refunds
2. **Non-negative Balances**: No address has negative balance
3. **Appeal Bond Payment**: Appealants pay correct bonds
4. **Round Completion**: All rounds are processed
5. **Deterministic Distribution**: Same input → same output
6. **Role Consistency**: One role per participant per round
7. ...and 16 more

### Test Execution Flow
```python
# For each path in TRANSITIONS_GRAPH
path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
↓
transaction = path_to_transaction_results(path)
↓
fee_events, labels = process_transaction(transaction)
↓
check_all_invariants(fee_events, transaction, labels)
```

## Recent Refactors

### 1. **ROUND_SIZES Split**
- Split `ROUND_SIZES` into `NORMAL_ROUND_SIZES` and `APPEAL_ROUND_SIZES`
- Allows independent sizing for normal rounds vs appeals
- Simplifies chained appeal handling

### 2. **Index-based to Content-based Detection**
- Removed all `i % 2` logic for appeal detection
- Appeals detected by vote patterns (NA votes, no leader receipt)
- More flexible and maintainable

### 3. **Path-based Testing**
- Moved from manual test case creation to path generation
- `TRANSITIONS_GRAPH` as single source of truth
- Exhaustive testing of all valid scenarios

### 4. **Appeal Index Calculation**
- Removed `floor(round_index / 2)` calculations
- Count actual appeal rounds to find indices
- Find previous normal rounds by searching backwards

## Configuration and Extension

### Adding New Round Types
1. Add to `RoundLabel` type definition
2. Create distribution function in `round_fee_distribution/`
3. Add case in `distribute_round.py`
4. Update pattern matching in `round_labeling.py`
5. Add tests

### Adding New Vote Types
1. Update `Vote` type definition
2. Modify vote pattern detection in `is_likely_appeal_round()`
3. Update majority calculation if needed
4. Add test cases

### Modifying Penalties
1. Update coefficient constants
2. Ensure distribution functions use constants
3. Run invariant tests to verify conservation

## Performance Considerations

- **Path Generation**: Exponential growth with max length
  - Length 7: ~1,000 paths
  - Length 19: ~130 million paths
- **Memory**: Fee events are kept in memory
- **Optimization**: Use batch processing for large path sets

## Future Enhancements

1. **Toppers**: Special participants with different fee structures
2. **Dynamic Round Sizes**: Adjust based on network conditions
3. **Slashing**: More complex penalty mechanisms
4. **Multi-rotation**: Handling multiple leader elections per round
5. **Parallel Processing**: For large-scale path testing

## Round Sizes and Validator Selection Logic

### Round Size Constants

The system uses two separate arrays for round sizes defined in `constants.py`:

```python
NORMAL_ROUND_SIZES = [5, 11, 23, 47, 95, 191, 383, 767, 1000]
APPEAL_ROUND_SIZES = [7, 13, 25, 49, 97, 193, 385, 769, 1000]
```

These sizes follow an exponential growth pattern (approximately doubling) to:
- Ensure sufficient validators for consensus
- Scale security with transaction importance
- Balance between decentralization and efficiency

### Validator Selection Patterns

There are two main patterns for validator selection depending on appeal outcomes:

#### Pattern 1: Successful Appeal
When an appeal is successful, validators are combined:
```
Next round size = Previous normal round + Appeal round - 1
```
Where the `-1` represents excluding the original leader who was appealed.

#### Pattern 2: Chained Unsuccessful Appeals
When appeals are unsuccessful and chained, the system progresses through the arrays independently:
```
Normal rounds: Use next index in NORMAL_ROUND_SIZES
Appeal rounds: Use next index in APPEAL_ROUND_SIZES
```

### Example Flows

#### Successful Appeal Flow
```
Round 0 (Normal, 5 validators):
- Leader: addr[0] 
- Validators: addr[1], addr[2], addr[3], addr[4]

Round 1 (Appeal, 7 validators):
- New validators: addr[5], addr[6], addr[7], addr[8], addr[9], addr[10], addr[11]

Round 2 (Normal, 11 validators = 5 + 7 - 1):
- New Leader: addr[1] (promoted from original validators)
- Validators: addr[2] through addr[11]
- Excluded: addr[0] (original leader who was appealed)
```

#### Chained Unsuccessful Appeals Flow
```
Round 0 (Normal, NORMAL_ROUND_SIZES[0] = 5):
- Validators: addr[0] through addr[4]

Round 1 (Unsuccessful Appeal, APPEAL_ROUND_SIZES[0] = 7):
- New validators: addr[5] through addr[11]

Round 2 (Normal, NORMAL_ROUND_SIZES[1] = 11):
- Validators selected from available pool

Round 3 (Unsuccessful Appeal, APPEAL_ROUND_SIZES[1] = 13):
- New validators: addr[12] through addr[24]

Round 4 (Normal, NORMAL_ROUND_SIZES[2] = 23):
- Validators selected from available pool

Round 5 (Unsuccessful Appeal, APPEAL_ROUND_SIZES[2] = 25):
- New validators added as needed

Round 6 (Normal, NORMAL_ROUND_SIZES[3] = 47):
- Validators selected from available pool
```

### Key Properties

1. **Leader Exclusion**: Only occurs after successful appeals
2. **Independent Progression**: Unsuccessful appeals don't affect round size calculation
3. **Array Index Tracking**: System maintains separate indices for normal and appeal rounds
4. **Validator Pool Growth**: New validators are added as needed to meet round sizes

### Round Size Calculation Logic

```python
def get_round_size(round_index, round_labels):
    normal_count = 0
    appeal_count = 0
    
    for i in range(round_index + 1):
        if is_appeal_round(round_labels[i]):
            appeal_count += 1
        else:
            normal_count += 1
    
    if is_appeal_round(round_labels[round_index]):
        # Use appeal count to index into APPEAL_ROUND_SIZES
        index = appeal_count - 1
        return APPEAL_ROUND_SIZES[index] if index < len(APPEAL_ROUND_SIZES) else APPEAL_ROUND_SIZES[-1]
    else:
        # Use normal count to index into NORMAL_ROUND_SIZES
        index = normal_count - 1
        return NORMAL_ROUND_SIZES[index] if index < len(NORMAL_ROUND_SIZES) else NORMAL_ROUND_SIZES[-1]
```

### Special Cases

1. **After Successful Appeal**: Next normal round combines validators (sum - 1)
2. **After Unsuccessful Appeal**: Next normal round uses next size in array
3. **Mixed Patterns**: System handles combinations of successful and unsuccessful appeals
4. **Array Bounds**: When indices exceed array length, use the last value (1000)

### Validator Pool Management

The system maintains a growing pool of validator addresses:
- New validators are added during each appeal
- Validators persist across rounds (except successfully appealed leaders)
- Pool size grows to accommodate larger round sizes
- Address assignment is deterministic based on round progression