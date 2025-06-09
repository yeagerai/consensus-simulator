# Fee Distribution Invariants Design

## Overview

This document defines comprehensive invariants that must hold across all fee distribution scenarios in the GenLayer protocol. These invariants ensure the economic integrity and correctness of the fee distribution system.

## Core Invariants

### 1. **Conservation of Value Invariant**
**Statement**: The total value entering the system must equal the total value exiting the system.
```
total_costs = total_earnings + total_burns + sender_refund
```
**Rationale**: No value should be created or destroyed within the system.

### 2. **Non-Negative Balance Invariant**
**Statement**: No address should have a negative net balance.
```
for each address: total_earnings - total_costs - total_burns ≥ 0
```
**Rationale**: Prevents economic attacks and ensures system solvency.

### 3. **Appeal Bond Coverage Invariant**
**Statement**: Appeal bonds must cover the cost of the appeal round.
```
appeal_bond ≥ appeal_round_size * validators_timeout + leader_timeout
```
**Rationale**: Ensures appeals are economically viable and properly incentivized.

### 4. **Majority/Minority Consistency Invariant**
**Statement**: In rounds with a clear majority, the sum of minority burns equals the penalty coefficient times their timeouts.
```
sum(minority_burns) = PENALTY_REWARD_COEFFICIENT * count(minority) * validators_timeout
```
**Rationale**: Ensures consistent penalty application.

### 5. **Role Exclusivity Invariant**
**Statement**: An address cannot be both leader and validator in the same round.
```
for each round: leader_address ∉ validator_addresses
```
**Rationale**: Prevents conflicting incentives and maintains protocol integrity.

### 6. **Sequential Processing Invariant**
**Statement**: Rounds must be processed in increasing order of their indices.
```
for i in range(len(rounds)-1): round[i].index < round[i+1].index
```
**Rationale**: Ensures deterministic and predictable fee distribution.

### 7. **Appeal Pairing Invariant**
**Statement**: Appeal rounds must follow normal rounds and occur at odd indices.
```
if round[i] is appeal: i is odd and round[i-1] is normal
```
**Rationale**: Maintains the appeal structure of the protocol.

### 8. **Burn Non-Negativity Invariant**
**Statement**: All burn amounts must be non-negative.
```
for each fee_event: if fee_event.burn exists: fee_event.burn ≥ 0
```
**Rationale**: Negative burns would be equivalent to unauthorized earnings.

### 9. **Refund Non-Negativity Invariant**
**Statement**: Sender refunds must be non-negative.
```
sender_refund ≥ 0
```
**Rationale**: Prevents the sender from owing more than initially paid.

### 10. **Vote Consistency Invariant**
**Statement**: Votes in fee events must match the actual votes in transaction rounds.
```
for each fee_event with vote: fee_event.vote == transaction_rounds[round_index].rotations[rotation_index].votes[address]
```
**Rationale**: Ensures fee distribution matches actual voting behavior.

### 11. **Idle Slashing Invariant**
**Statement**: Idle validators must be slashed exactly IDLE_PENALTY_COEFFICIENT of their stake.
```
if validator is idle: slash_amount = IDLE_PENALTY_COEFFICIENT * stake
```
**Rationale**: Ensures consistent penalties for non-participation.

### 12. **Deterministic Violation Invariant**
**Statement**: Validators with hash mismatches must be slashed DETERMINISTIC_VIOLATION_PENALTY_COEFFICIENT of their stake.
```
if hash_mismatch: slash_amount = DETERMINISTIC_VIOLATION_PENALTY_COEFFICIENT * stake
```
**Rationale**: Ensures consistent penalties for protocol violations.

### 13. **Leader Timeout Earning Invariant**
**Statement**: In leader timeout scenarios, the leader earns at most the leader timeout amount.
```
if leader_timeout: leader_earnings ≤ leader_timeout
```
**Rationale**: Prevents leaders from earning more than their allocated timeout.

### 14. **Appeal Success Distribution Invariant**
**Statement**: Successful appeals must distribute the appeal bond plus the appropriate round fees.
```
if appeal_successful: total_distributed ≥ appeal_bond
```
**Rationale**: Ensures successful appealants are properly rewarded.

### 15. **Unsuccessful Appeal Burn Invariant**
**Statement**: Unsuccessful appeals must burn an amount equal to the appeal bond minus any distributions.
```
if appeal_unsuccessful: burn_amount = appeal_bond - distributions_in_round
```
**Rationale**: Ensures economic cost for unsuccessful appeals.

## Party Safety Invariants

### 16. **Sender Safety Invariant**
**Statement**: The sender cannot lose more than the total transaction cost.
```
sender_net_loss ≤ compute_total_cost(transaction_budget)
```
**Rationale**: Protects senders from unexpected losses.

### 17. **Validator Coalition Safety Invariant**
**Statement**: Any coalition of validators cannot collectively earn more than they collectively pay.
```
for any validator_subset: sum(earnings) ≤ sum(costs)
```
**Rationale**: Prevents validator collusion attacks.

### 18. **Appealant Safety Invariant**
**Statement**: Appealants can only lose their appeal bonds in unsuccessful appeals.
```
if appeal_successful: appealant_net ≥ 0
if appeal_unsuccessful: appealant_loss ≤ appeal_bond
```
**Rationale**: Bounds appealant risk to their bond amount.

## Edge Case Invariants

### 19. **Empty Round Invariant**
**Statement**: Empty rounds should not generate any fee events.
```
if round.is_empty(): no fee_events for this round
```
**Rationale**: Prevents fees from non-existent activities.

### 20. **Single Transaction Invariant**
**Statement**: Single leader timeout transactions get special 50% distribution.
```
if single_round and leader_timeout: leader_earns = leader_timeout / 2
```
**Rationale**: Handles edge case as specified in protocol.

### 21. **Chained Appeal Invariant**
**Statement**: Multiple consecutive unsuccessful appeals must each burn their respective bonds.
```
for each unsuccessful_appeal[i]: burn[i] = appeal_bond[i] - distributions[i]
```
**Rationale**: Ensures each appeal is independently accounted for.

### 22. **Undetermined Majority Invariant**
**Statement**: In undetermined rounds, all participants earn their timeout values.
```
if majority == UNDETERMINED: all_earn_timeout_values
```
**Rationale**: Fair distribution when no consensus is reached.

## Implementation Strategy

1. **Unit Test Coverage**: Each invariant should have dedicated unit tests
2. **Property-Based Testing**: Use Hypothesis to generate random scenarios
3. **Path-Based Testing**: Test all paths through TRANSITIONS_GRAPH
4. **Regression Testing**: Maintain a suite of known edge cases
5. **Performance Monitoring**: Track invariant checking overhead

## Testing Priorities

1. **Critical Invariants** (1-9): Must never fail
2. **Safety Invariants** (16-18): Protect participant funds
3. **Protocol Invariants** (10-15): Ensure correct behavior
4. **Edge Case Invariants** (19-22): Handle special scenarios

## Monitoring and Alerting

In production, these invariants should be:
1. Checked after every transaction
2. Logged for audit trails
3. Alert on any violation
4. Include in health checks