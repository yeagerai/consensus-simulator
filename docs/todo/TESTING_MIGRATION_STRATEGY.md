# Testing Migration Strategy

## Overview

This document provides a detailed, step-by-step migration plan from the current test architecture to the new invariant-first testing suite. The migration is designed to be incremental, risk-free, and to provide immediate value at each step.

## Current State Analysis

### Existing Test Structure
```
tests/
├── conftest.py                          # Basic pytest config
├── invariant_checks.py                  # Helper functions
├── budget_and_refunds/                  # 2 test files
├── fee_distributions/                   
│   ├── check_invariants/               # 4 files (invariant implementations)
│   ├── simple_round_types_tests/       # 8 files (round type tests)
│   └── unit_tests/                     # 1 file (new unit tests)
├── round_combinations/                  # 6 files (path analysis)
├── round_labeling/                     # 9 files (labeling tests)
├── round_types_tests/                  # 8 files (DUPLICATE of simple_round_types)
├── slashing/                           # 3 files (penalty tests)
└── unittests/                          # Additional unit tests
```

### Key Issues to Address
1. **Duplication**: `round_types_tests/` and `fee_distributions/simple_round_types_tests/` contain similar tests
2. **Scattered Invariants**: Invariant logic spread across multiple files
3. **No Clear Organization**: Tests organized by different principles
4. **Limited Test Types**: Missing performance, stress, and property-based tests
5. **Manual Test Creation**: No builders or fixtures for common patterns

## Migration Phases

### Phase 0: Preparation (2 days)

#### Day 1: Assessment and Planning
1. **Inventory Current Tests**
   ```bash
   # Create test inventory
   find tests -name "test_*.py" -type f | sort > docs/current_tests_inventory.txt
   
   # Count test functions
   grep -r "def test_" tests/ | wc -l  # Document current test count
   
   # Identify duplicate tests
   diff -r tests/round_types_tests/ tests/fee_distributions/simple_round_types_tests/
   ```

2. **Document Current Coverage**
   ```bash
   # Run coverage report
   pytest --cov=fee_simulator --cov-report=html --cov-report=term
   # Save baseline coverage metrics
   ```

3. **Create Migration Checklist**
   ```markdown
   # docs/test_migration_checklist.md
   - [ ] Baseline metrics captured
   - [ ] Duplicate tests identified
   - [ ] Critical paths documented
   - [ ] Team communication sent
   ```

#### Day 2: Setup Development Environment
1. **Create Feature Branch**
   ```bash
   git checkout -b feature/test-architecture-migration
   ```

2. **Install Additional Dependencies**
   ```bash
   # Add to requirements-test.txt
   hypothesis>=6.0.0      # Property-based testing
   pytest-benchmark>=3.4  # Performance benchmarks
   pytest-xdist>=2.5     # Parallel execution
   pytest-timeout>=2.1   # Test timeouts
   pytest-mock>=3.6      # Enhanced mocking
   ```

3. **Create Migration Scripts Directory**
   ```bash
   mkdir -p scripts/test_migration
   touch scripts/test_migration/__init__.py
   ```

### Phase 1: Core Infrastructure (5 days)

#### Day 3-4: Create New Directory Structure

1. **Create Directory Structure Script**
   ```python
   # scripts/test_migration/create_structure.py
   import os
   from pathlib import Path
   
   def create_test_structure():
       """Create new test directory structure"""
       base_dir = Path("tests")
       
       # Define new structure
       directories = [
           "invariants/core",
           "invariants/runners",
           "scenarios/common",
           "scenarios/edge_cases",
           "scenarios/attack_vectors",
           "scenarios/regression",
           "components",
           "integration",
           "performance/benchmarks",
           "performance/stress",
           "fixtures/builders",
           "fixtures/generators",
           "fixtures/validators",
           "fixtures/test_data",
           "utils",
       ]
       
       for dir_path in directories:
           full_path = base_dir / dir_path
           full_path.mkdir(parents=True, exist_ok=True)
           
           # Create __init__.py
           init_file = full_path / "__init__.py"
           init_file.touch()
           
       print(f"Created {len(directories)} directories")
       
   if __name__ == "__main__":
       create_test_structure()
   ```

2. **Create README for New Structure**
   ```markdown
   # tests/README.md
   # Fee Simulator Test Suite
   
   ## Directory Structure
   - `invariants/`: System-wide invariants (the specification)
   - `scenarios/`: Real-world test scenarios
   - `components/`: Unit tests for individual components
   - `integration/`: Integration tests
   - `performance/`: Performance and stress tests
   - `fixtures/`: Shared test utilities
   - `utils/`: Test helpers
   
   ## Running Tests
   - Quick: `pytest -m quick`
   - Standard: `pytest -m "not slow"`
   - Full: `pytest`
   ```

#### Day 5-6: Implement Core Components

1. **InvariantRegistry Implementation**
   ```python
   # tests/invariants/registry.py
   from abc import ABC, abstractmethod
   from dataclasses import dataclass
   from typing import Dict, List, Set, Optional, Any
   from enum import Enum
   import json
   
   class InvariantPriority(Enum):
       CRITICAL = "critical"
       HIGH = "high"
       MEDIUM = "medium"
       LOW = "low"
   
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
       
       def to_json(self) -> str:
           return json.dumps({
               "invariant_id": self.invariant_id,
               "message": self.message,
               "severity": self.severity.value,
               "context": self.context
           }, indent=2)
   
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
       
       _instance = None
       
       def __new__(cls):
           if cls._instance is None:
               cls._instance = super().__new__(cls)
               cls._instance._initialized = False
           return cls._instance
       
       def __init__(self):
           if self._initialized:
               return
           self._invariants: Dict[str, Invariant] = {}
           self._groups: Dict[InvariantGroup, Set[str]] = {
               group: set() for group in InvariantGroup
           }
           self._initialized = True
       
       def register(self, invariant: Invariant) -> None:
           """Register an invariant"""
           if invariant.id in self._invariants:
               raise ValueError(f"Invariant {invariant.id} already registered")
           
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
           for inv_id in self._groups.get(group, []):
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
       
       def get_summary(self) -> Dict[str, Any]:
           """Get summary of registered invariants"""
           return {
               "total": len(self._invariants),
               "by_priority": {
                   priority.value: sum(1 for inv in self._invariants.values() 
                                     if inv.priority == priority)
                   for priority in InvariantPriority
               },
               "by_group": {
                   group.value: len(self._groups[group])
                   for group in InvariantGroup
                   if group != InvariantGroup.ALL
               }
           }
   ```

2. **SystemState Implementation**
   ```python
   # tests/invariants/core/state.py
   from dataclasses import dataclass, field
   from typing import List, Dict, Optional
   from fee_simulator.models import TransactionRoundResults, TransactionBudget, FeeEvent
   from fee_simulator.types import RoundLabel
   
   @dataclass
   class SystemState:
       """Complete system state for invariant checking"""
       
       # Input
       transaction_results: TransactionRoundResults
       transaction_budget: TransactionBudget
       addresses: List[str]
       
       # Output  
       fee_events: List[FeeEvent]
       round_labels: List[RoundLabel]
       
       # Derived (computed on demand)
       _address_balances: Optional[Dict[str, int]] = field(default=None, init=False)
       _total_costs: Optional[int] = field(default=None, init=False)
       _total_earnings: Optional[int] = field(default=None, init=False)
       _total_burns: Optional[int] = field(default=None, init=False)
       _total_slashed: Optional[int] = field(default=None, init=False)
       
       @property
       def address_balances(self) -> Dict[str, int]:
           """Calculate and cache address balances"""
           if self._address_balances is None:
               self._calculate_balances()
           return self._address_balances
       
       @property
       def total_costs(self) -> int:
           """Total costs paid"""
           if self._total_costs is None:
               self._total_costs = sum(e.cost for e in self.fee_events if e.cost)
           return self._total_costs
       
       @property
       def total_earnings(self) -> int:
           """Total earnings distributed"""
           if self._total_earnings is None:
               self._total_earnings = sum(e.earned for e in self.fee_events if e.earned)
           return self._total_earnings
       
       @property
       def total_burns(self) -> int:
           """Total amount burned"""
           if self._total_burns is None:
               self._total_burns = sum(e.burned for e in self.fee_events if e.burned)
           return self._total_burns
       
       @property
       def total_slashed(self) -> int:
           """Total amount slashed"""
           if self._total_slashed is None:
               self._total_slashed = sum(e.slashed for e in self.fee_events if e.slashed)
           return self._total_slashed
       
       def _calculate_balances(self):
           """Calculate final balances for all addresses"""
           self._address_balances = {}
           for event in self.fee_events:
               addr = event.address
               if addr not in self._address_balances:
                   self._address_balances[addr] = 0
               
               if event.earned:
                   self._address_balances[addr] += event.earned
               if event.cost:
                   self._address_balances[addr] -= event.cost
               if event.burned:
                   self._address_balances[addr] -= event.burned
               if event.slashed:
                   self._address_balances[addr] -= event.slashed
       
       def get_summary(self) -> Dict[str, Any]:
           """Get summary statistics"""
           return {
               "rounds": len(self.transaction_results.rounds),
               "addresses": len(self.addresses),
               "fee_events": len(self.fee_events),
               "total_costs": self.total_costs,
               "total_earnings": self.total_earnings,
               "total_burns": self.total_burns,
               "total_slashed": self.total_slashed,
               "unique_labels": list(set(self.round_labels)),
           }
   ```

#### Day 7: Implement First Critical Invariants

1. **Conservation Invariant**
   ```python
   # tests/invariants/core/conservation.py
   from typing import Optional
   from ..registry import Invariant, InvariantViolation, InvariantPriority, InvariantGroup
   from .state import SystemState
   from fee_simulator.core.refunds import compute_sender_refund
   
   class ConservationInvariant(Invariant):
       """Total money in = Total money out + burns"""
       
       def __init__(self):
           super().__init__(
               id="INV-001",
               description="Total costs must equal earnings + burns + refunds",
               priority=InvariantPriority.CRITICAL,
               groups=[InvariantGroup.FINANCIAL]
           )
       
       def check(self, state: SystemState) -> Optional[InvariantViolation]:
           # Calculate refund
           refund = compute_sender_refund(
               state.transaction_budget.senderAddress,
               state.fee_events,
               state.transaction_budget,
               state.round_labels
           )
           
           # Check conservation
           total_in = state.total_costs
           total_out = state.total_earnings + state.total_burns + refund
           
           if abs(total_in - total_out) > 1:  # Allow 1 wei rounding error
               return InvariantViolation(
                   invariant_id=self.id,
                   message=f"Conservation violated: {total_in} != {total_out}",
                   severity=self.priority,
                   context={
                       "total_costs": total_in,
                       "total_earnings": state.total_earnings,
                       "total_burns": state.total_burns,
                       "refund": refund,
                       "difference": total_in - total_out,
                       "rounds": len(state.round_labels),
                   }
               )
           return None
   
   class NonNegativeBalanceInvariant(Invariant):
       """No address should have negative balance"""
       
       def __init__(self):
           super().__init__(
               id="INV-002",
               description="All addresses must have non-negative final balance",
               priority=InvariantPriority.CRITICAL,
               groups=[InvariantGroup.FINANCIAL, InvariantGroup.FAIRNESS]
           )
       
       def check(self, state: SystemState) -> Optional[InvariantViolation]:
           for addr, balance in state.address_balances.items():
               if balance < 0:
                   # Find all events for this address for debugging
                   addr_events = [e for e in state.fee_events if e.address == addr]
                   
                   return InvariantViolation(
                       invariant_id=self.id,
                       message=f"Address {addr[:10]}... has negative balance: {balance}",
                       severity=self.priority,
                       context={
                           "address": addr,
                           "balance": balance,
                           "events_count": len(addr_events),
                           "total_earned": sum(e.earned for e in addr_events if e.earned),
                           "total_cost": sum(e.cost for e in addr_events if e.cost),
                           "total_burned": sum(e.burned for e in addr_events if e.burned),
                           "total_slashed": sum(e.slashed for e in addr_events if e.slashed),
                       }
                   )
           return None
   ```

### Phase 2: Test Migration (10 days)

#### Day 8-9: Create Migration Mapping

1. **Analyze Current Tests**
   ```python
   # scripts/test_migration/analyze_tests.py
   import ast
   import os
   from pathlib import Path
   from typing import Dict, List, Set
   
   class TestAnalyzer(ast.NodeVisitor):
       """Analyze test files to understand structure"""
       
       def __init__(self):
           self.test_functions = []
           self.imports = []
           self.fixtures_used = set()
       
       def visit_FunctionDef(self, node):
           if node.name.startswith('test_'):
               # Extract fixture usage from parameters
               fixtures = [arg.arg for arg in node.args.args 
                         if arg.arg not in ['self']]
               
               self.test_functions.append({
                   'name': node.name,
                   'fixtures': fixtures,
                   'line': node.lineno,
                   'decorators': [d.id if hasattr(d, 'id') else str(d) 
                                for d in node.decorator_list]
               })
               self.fixtures_used.update(fixtures)
           
           self.generic_visit(node)
       
       def visit_Import(self, node):
           for alias in node.names:
               self.imports.append(alias.name)
           self.generic_visit(node)
       
       def visit_ImportFrom(self, node):
           self.imports.append(f"{node.module}.{node.names[0].name}")
           self.generic_visit(node)
   
   def analyze_test_directory():
       """Analyze all test files"""
       results = {}
       
       for test_file in Path('tests').rglob('test_*.py'):
           with open(test_file, 'r') as f:
               tree = ast.parse(f.read())
           
           analyzer = TestAnalyzer()
           analyzer.visit(tree)
           
           results[str(test_file)] = {
               'test_count': len(analyzer.test_functions),
               'tests': analyzer.test_functions,
               'fixtures_used': list(analyzer.fixtures_used),
               'imports': analyzer.imports[:10]  # First 10 imports
           }
       
       return results
   
   def create_migration_map(analysis: Dict) -> Dict[str, str]:
       """Create mapping from old location to new location"""
       migration_map = {}
       
       for old_path, info in analysis.items():
           # Determine new location based on test type
           if 'invariant' in old_path:
               new_path = old_path.replace('fee_distributions/check_invariants', 
                                         'invariants/core')
           elif 'round_labeling' in old_path:
               new_path = old_path.replace('round_labeling', 'components')
           elif 'simple_round_types' in old_path or 'round_types_tests' in old_path:
               new_path = old_path.replace('simple_round_types_tests', 'scenarios/common')
               new_path = new_path.replace('round_types_tests', 'scenarios/common')
           elif 'slashing' in old_path:
               new_path = old_path.replace('slashing', 'scenarios/edge_cases')
           elif 'budget_and_refunds' in old_path:
               new_path = old_path.replace('budget_and_refunds', 'components')
           elif 'round_combinations' in old_path:
               new_path = old_path.replace('round_combinations', 'integration')
           else:
               new_path = old_path  # Keep in same location
           
           migration_map[old_path] = new_path
       
       return migration_map
   
   if __name__ == "__main__":
       analysis = analyze_test_directory()
       migration_map = create_migration_map(analysis)
       
       # Save analysis
       import json
       with open('docs/test_analysis.json', 'w') as f:
           json.dump(analysis, f, indent=2)
       
       with open('docs/test_migration_map.json', 'w') as f:
           json.dump(migration_map, f, indent=2)
       
       # Print summary
       total_tests = sum(info['test_count'] for info in analysis.values())
       print(f"Total test files: {len(analysis)}")
       print(f"Total test functions: {total_tests}")
       print(f"Unique fixtures used: {len(set().union(*[set(info['fixtures_used']) for info in analysis.values()]))}")
   ```

#### Day 10-12: Create Test Builders

1. **TransactionBuilder Implementation**
   ```python
   # tests/fixtures/builders/transaction_builder.py
   from typing import List, Dict, Optional, Tuple
   from dataclasses import dataclass, field
   from fee_simulator.models import (
       TransactionRoundResults, TransactionBudget, Round, 
       Rotation, Appeal, FeeEvent
   )
   from fee_simulator.types import Vote, RoundLabel
   from fee_simulator.utils import generate_random_eth_address
   from fee_simulator.core.transaction_processing import process_transaction
   from fee_simulator.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES
   
   @dataclass
   class TransactionBuilder:
       """Fluent interface for building test transactions"""
       
       _rounds: List[Round] = field(default_factory=list)
       _budget: Optional[TransactionBudget] = None
       _addresses: List[str] = field(default_factory=list)
       _normal_round_count: int = 0
       _appeal_round_count: int = 0
       _appeals: List[Appeal] = field(default_factory=list)
       
       def __post_init__(self):
           # Pre-generate addresses
           if not self._addresses:
               self._addresses = [generate_random_eth_address() 
                                for _ in range(100)]
       
       def with_normal_round(self, 
                           majority: str = "AGREE",
                           leader_timeout: bool = False,
                           custom_votes: Optional[Dict[str, Vote]] = None) -> 'TransactionBuilder':
           """Add a normal round with specified parameters"""
           
           # Determine round size
           size = NORMAL_ROUND_SIZES[self._normal_round_count] \
                   if self._normal_round_count < len(NORMAL_ROUND_SIZES) \
                   else NORMAL_ROUND_SIZES[-1]
           
           # Get addresses for this round
           start_idx = len(self._get_used_addresses())
           round_addresses = self._addresses[start_idx:start_idx + size]
           
           if custom_votes:
               votes = custom_votes
           else:
               votes = self._generate_normal_round_votes(
                   round_addresses, majority, leader_timeout
               )
           
           self._rounds.append(Round(rotations=[Rotation(votes=votes)]))
           self._normal_round_count += 1
           return self
       
       def with_appeal_round(self, 
                           appeal_type: str = "VALIDATOR",
                           successful: bool = True) -> 'TransactionBuilder':
           """Add an appeal round"""
           
           # Determine round size
           size = APPEAL_ROUND_SIZES[self._appeal_round_count] \
                   if self._appeal_round_count < len(APPEAL_ROUND_SIZES) \
                   else APPEAL_ROUND_SIZES[-1]
           
           # Get addresses
           start_idx = len(self._get_used_addresses())
           round_addresses = self._addresses[start_idx:start_idx + size]
           
           # Create appeal
           appealant_addr = self._addresses[90 + self._appeal_round_count]
           self._appeals.append(Appeal(appealantAddress=appealant_addr))
           
           # Generate votes
           votes = self._generate_appeal_round_votes(
               round_addresses, appeal_type, successful
           )
           
           self._rounds.append(Round(rotations=[Rotation(votes=votes)]))
           self._appeal_round_count += 1
           return self
       
       def with_budget(self, 
                      leader_timeout: int = 100,
                      validators_timeout: int = 200) -> 'TransactionBuilder':
           """Set the transaction budget"""
           self._budget = TransactionBudget(
               leaderTimeout=leader_timeout,
               validatorsTimeout=validators_timeout,
               appealRounds=self._appeal_round_count,
               rotations=[0] * len(self._rounds),
               senderAddress=self._addresses[99],
               appeals=self._appeals,
               staking_distribution="constant"
           )
           return self
       
       def build(self) -> 'SystemState':
           """Build the complete system state"""
           from tests.invariants.core.state import SystemState
           
           if not self._budget:
               self.with_budget()
           
           transaction = TransactionRoundResults(rounds=self._rounds)
           used_addresses = self._get_used_addresses()
           
           # Process transaction
           fee_events, labels = process_transaction(
               used_addresses, transaction, self._budget
           )
           
           return SystemState(
               transaction_results=transaction,
               transaction_budget=self._budget,
               addresses=used_addresses,
               fee_events=fee_events,
               round_labels=labels
           )
       
       def _get_used_addresses(self) -> List[str]:
           """Get all addresses used in rounds"""
           addresses = []
           for round_obj in self._rounds:
               for rotation in round_obj.rotations:
                   addresses.extend(rotation.votes.keys())
           # Add sender and appealants
           if self._budget:
               addresses.append(self._budget.senderAddress)
               addresses.extend([a.appealantAddress for a in self._appeals])
           return list(dict.fromkeys(addresses))  # Remove duplicates, preserve order
       
       def _generate_normal_round_votes(self, 
                                      addresses: List[str],
                                      majority: str,
                                      leader_timeout: bool) -> Dict[str, Vote]:
           """Generate votes for a normal round"""
           votes = {}
           
           if leader_timeout:
               votes[addresses[0]] = ["LEADER_TIMEOUT", "NA"]
               for addr in addresses[1:]:
                   votes[addr] = "NA"
           else:
               # Leader vote
               votes[addresses[0]] = ["LEADER_RECEIPT", majority]
               
               # Validator votes based on desired majority
               if majority == "AGREE":
                   # 70% agree, 20% disagree, 10% timeout
                   for i, addr in enumerate(addresses[1:]):
                       if i < int(len(addresses) * 0.7):
                           votes[addr] = "AGREE"
                       elif i < int(len(addresses) * 0.9):
                           votes[addr] = "DISAGREE"
                       else:
                           votes[addr] = "TIMEOUT"
               
               elif majority == "DISAGREE":
                   # Opposite distribution
                   for i, addr in enumerate(addresses[1:]):
                       if i < int(len(addresses) * 0.7):
                           votes[addr] = "DISAGREE"
                       elif i < int(len(addresses) * 0.9):
                           votes[addr] = "AGREE"
                       else:
                           votes[addr] = "TIMEOUT"
               
               else:  # UNDETERMINED
                   # Equal distribution
                   for i, addr in enumerate(addresses[1:]):
                       if i % 3 == 0:
                           votes[addr] = "AGREE"
                       elif i % 3 == 1:
                           votes[addr] = "DISAGREE"
                       else:
                           votes[addr] = "TIMEOUT"
           
           return votes
       
       def _generate_appeal_round_votes(self,
                                      addresses: List[str],
                                      appeal_type: str,
                                      successful: bool) -> Dict[str, Vote]:
           """Generate votes for an appeal round"""
           votes = {}
           
           if appeal_type == "LEADER":
               # All NA for leader appeal
               for addr in addresses:
                   votes[addr] = "NA"
           else:  # VALIDATOR appeal
               if successful:
                   # Majority disagree with original decision
                   for i, addr in enumerate(addresses):
                       if i < int(len(addresses) * 0.7):
                           votes[addr] = "DISAGREE"
                       else:
                           votes[addr] = "AGREE"
               else:
                   # Majority agree with original decision
                   for i, addr in enumerate(addresses):
                       if i < int(len(addresses) * 0.7):
                           votes[addr] = "AGREE"
                       else:
                           votes[addr] = "DISAGREE"
           
           return votes
   ```

#### Day 13-15: Migrate Core Tests

1. **Create Test Migration Script**
   ```python
   # scripts/test_migration/migrate_test.py
   import re
   import ast
   from pathlib import Path
   from typing import List, Tuple
   
   class TestMigrator:
       """Migrate tests to new architecture"""
       
       def __init__(self, old_path: str, new_path: str):
           self.old_path = Path(old_path)
           self.new_path = Path(new_path)
       
       def migrate(self) -> bool:
           """Migrate a test file"""
           if not self.old_path.exists():
               print(f"Source file not found: {self.old_path}")
               return False
           
           # Read old test
           old_content = self.old_path.read_text()
           
           # Transform content
           new_content = self._transform_content(old_content)
           
           # Ensure target directory exists
           self.new_path.parent.mkdir(parents=True, exist_ok=True)
           
           # Write new test
           self.new_path.write_text(new_content)
           
           print(f"Migrated: {self.old_path} -> {self.new_path}")
           return True
       
       def _transform_content(self, content: str) -> str:
           """Transform test content to new architecture"""
           
           # Update imports
           content = self._update_imports(content)
           
           # Add invariant checks
           content = self._add_invariant_checks(content)
           
           # Convert to builder pattern
           content = self._convert_to_builders(content)
           
           # Add proper markers
           content = self._add_test_markers(content)
           
           return content
       
       def _update_imports(self, content: str) -> str:
           """Update import statements"""
           
           # Add new imports at the top
           new_imports = [
               "from tests.invariants.registry import InvariantRegistry",
               "from tests.fixtures.builders import TransactionBuilder",
               "from tests.invariants.core.state import SystemState",
           ]
           
           # Find first import line
           lines = content.split('\n')
           import_idx = 0
           for i, line in enumerate(lines):
               if line.startswith('import ') or line.startswith('from '):
                   import_idx = i
                   break
           
           # Insert new imports
           for imp in new_imports:
               lines.insert(import_idx, imp)
               import_idx += 1
           
           return '\n'.join(lines)
       
       def _add_invariant_checks(self, content: str) -> str:
           """Add invariant checking to tests"""
           
           # Pattern to find test functions
           pattern = r'(def test_\w+\(.*?\):.*?)(\n\s+""".*?""")?(\n.*?)(?=\ndef|\nclass|\Z)'
           
           def add_invariants(match):
               func_def = match.group(1)
               docstring = match.group(2) or ""
               body = match.group(3)
               
               # Add invariant_registry to parameters if not present
               if 'invariant_registry' not in func_def:
                   func_def = func_def.rstrip(':')
                   if ',' in func_def:
                       func_def += ', invariant_registry):'
                   else:
                       func_def = func_def.rstrip(')') + ', invariant_registry):'
               
               # Add invariant check at end of test
               invariant_check = """
       # Check invariants
       violations = invariant_registry.check_all(state)
       assert not violations, f"Invariant violations: {violations}"
   """
               
               return func_def + docstring + body.rstrip() + invariant_check
           
           return re.sub(pattern, add_invariants, content, flags=re.DOTALL | re.MULTILINE)
       
       def _convert_to_builders(self, content: str) -> str:
           """Convert manual test setup to builder pattern"""
           
           # This is complex and would need custom logic per test type
           # For now, we'll just add a comment
           if 'TransactionRoundResults(' in content:
               content = "# TODO: Convert to TransactionBuilder\n" + content
           
           return content
       
       def _add_test_markers(self, content: str) -> str:
           """Add pytest markers based on test type"""
           
           markers = []
           
           # Determine markers based on content and location
           if 'invariant' in str(self.new_path):
               markers.append("@pytest.mark.invariants")
           elif 'scenarios' in str(self.new_path):
               markers.append("@pytest.mark.scenarios")
           elif 'performance' in str(self.new_path):
               markers.append("@pytest.mark.performance")
           
           # Quick test if it's simple
           if content.count('def test_') == 1 and len(content) < 2000:
               markers.append("@pytest.mark.quick")
           
           # Add markers before class definitions
           if markers:
               marker_str = '\n'.join(markers) + '\n'
               content = re.sub(r'(class Test\w+.*?:)', 
                              marker_str + r'\1', 
                              content)
           
           return content
   
   def migrate_all_tests():
       """Migrate all tests based on migration map"""
       import json
       
       # Load migration map
       with open('docs/test_migration_map.json', 'r') as f:
           migration_map = json.load(f)
       
       success_count = 0
       fail_count = 0
       
       for old_path, new_path in migration_map.items():
           migrator = TestMigrator(old_path, new_path)
           if migrator.migrate():
               success_count += 1
           else:
               fail_count += 1
       
       print(f"\nMigration complete: {success_count} success, {fail_count} failed")
   
   if __name__ == "__main__":
       migrate_all_tests()
   ```

#### Day 16-17: Create Test Oracle

1. **Test Oracle Implementation**
   ```python
   # tests/utils/oracle.py
   from typing import Dict, List, Tuple, Optional
   from dataclasses import dataclass, field
   from fee_simulator.models import TransactionRoundResults, TransactionBudget, Round
   from fee_simulator.types import RoundLabel, Vote
   from fee_simulator.core.majority import compute_majority
   from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT
   
   @dataclass
   class ExpectedOutcome:
       """Expected outcome for a transaction"""
       
       earnings: Dict[str, int] = field(default_factory=dict)
       costs: Dict[str, int] = field(default_factory=dict) 
       burns: Dict[str, int] = field(default_factory=dict)
       slashes: Dict[str, int] = field(default_factory=dict)
       labels: List[RoundLabel] = field(default_factory=list)
       refund: int = 0
       
       def add_earning(self, address: str, amount: int):
           self.earnings[address] = self.earnings.get(address, 0) + amount
       
       def add_cost(self, address: str, amount: int):
           self.costs[address] = self.costs.get(address, 0) + amount
       
       def add_burn(self, address: str, amount: int):
           self.burns[address] = self.burns.get(address, 0) + amount
       
       def add_slash(self, address: str, amount: int):
           self.slashes[address] = self.slashes.get(address, 0) + amount
   
   class FeeDistributionOracle:
       """Calculates expected outcomes for test verification"""
       
       def calculate_expected(self, 
                            transaction: TransactionRoundResults,
                            budget: TransactionBudget) -> ExpectedOutcome:
           """Calculate what the outcome SHOULD be based on business rules"""
           expected = ExpectedOutcome()
           
           # Process each round
           for round_idx, round_obj in enumerate(transaction.rounds):
               self._process_round(round_obj, round_idx, budget, expected)
           
           # Calculate refund
           total_cost = self._calculate_total_cost(budget, transaction)
           total_used = sum(expected.costs.values())
           expected.refund = max(0, total_cost - total_used)
           
           return expected
       
       def _process_round(self, 
                         round_obj: Round,
                         round_idx: int,
                         budget: TransactionBudget,
                         expected: ExpectedOutcome):
           """Process a single round"""
           
           if not round_obj.rotations:
               expected.labels.append("EMPTY_ROUND")
               return
           
           votes = round_obj.rotations[-1].votes
           
           # Determine round type
           if self._is_appeal_round(votes):
               self._process_appeal_round(votes, round_idx, budget, expected)
           else:
               self._process_normal_round(votes, round_idx, budget, expected)
       
       def _is_appeal_round(self, votes: Dict[str, Vote]) -> bool:
           """Check if round is an appeal"""
           # All NA votes = leader appeal
           if all(v == "NA" for v in votes.values()):
               return True
           
           # No leader receipt/timeout = validator appeal
           has_leader_action = any(
               isinstance(v, list) and v[0] in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]
               for v in votes.values()
           )
           return not has_leader_action
       
       def _process_normal_round(self,
                               votes: Dict[str, Vote],
                               round_idx: int,
                               budget: TransactionBudget,
                               expected: ExpectedOutcome):
           """Process normal round expected outcomes"""
           
           # Find leader
           leader_addr = None
           for addr, vote in votes.items():
               if isinstance(vote, list) and vote[0] in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]:
                   leader_addr = addr
                   break
           
           # Calculate majority
           majority = compute_majority(votes)
           
           if majority == "UNDETERMINED":
               expected.labels.append("NORMAL_ROUND")
               # Leader earns timeout
               if leader_addr:
                   expected.add_earning(leader_addr, budget.leaderTimeout)
               # All validators earn timeout
               for addr in votes:
                   expected.add_earning(addr, budget.validatorsTimeout)
           else:
               expected.labels.append("NORMAL_ROUND")
               # Leader earns full amount
               if leader_addr:
                   expected.add_earning(leader_addr, 
                                      budget.leaderTimeout + budget.validatorsTimeout)
               
               # Process validators
               for addr, vote in votes.items():
                   if addr == leader_addr:
                       continue
                   
                   vote_type = self._normalize_vote(vote)
                   if vote_type == majority:
                       expected.add_earning(addr, budget.validatorsTimeout)
                   else:
                       expected.add_burn(addr, 
                                       PENALTY_REWARD_COEFFICIENT * budget.validatorsTimeout)
       
       def _normalize_vote(self, vote: Vote) -> str:
           """Extract vote type from complex vote structure"""
           if isinstance(vote, list):
               return vote[1] if len(vote) > 1 else vote[0]
           return vote
       
       def verify_actual(self, 
                        expected: ExpectedOutcome,
                        actual_events: List['FeeEvent'],
                        actual_labels: List[RoundLabel]) -> List[str]:
           """Verify actual matches expected, return discrepancies"""
           discrepancies = []
           
           # Check labels
           if expected.labels != actual_labels:
               discrepancies.append(
                   f"Label mismatch: expected {expected.labels}, got {actual_labels}"
               )
           
           # Check earnings
           for addr, expected_earning in expected.earnings.items():
               actual_earning = sum(e.earned for e in actual_events 
                                  if e.address == addr and e.earned)
               if abs(expected_earning - actual_earning) > 1:  # Allow 1 wei difference
                   discrepancies.append(
                       f"Earnings mismatch for {addr[:10]}...: "
                       f"expected {expected_earning}, got {actual_earning}"
                   )
           
           # Check burns
           for addr, expected_burn in expected.burns.items():
               actual_burn = sum(e.burned for e in actual_events 
                               if e.address == addr and e.burned)
               if abs(expected_burn - actual_burn) > 1:
                   discrepancies.append(
                       f"Burn mismatch for {addr[:10]}...: "
                       f"expected {expected_burn}, got {actual_burn}"
                   )
           
           return discrepancies
       
       def _calculate_total_cost(self, 
                               budget: TransactionBudget,
                               transaction: TransactionRoundResults) -> int:
           """Calculate total transaction cost"""
           # This is simplified - real implementation in fee_simulator.utils
           base_cost = len(transaction.rounds) * (
               budget.leaderTimeout + 
               5 * budget.validatorsTimeout  # Assuming 5 validators minimum
           )
           return base_cost
   ```

### Phase 3: Integration and Validation (5 days)

#### Day 18-19: Create Test Validators

1. **Custom Assertions**
   ```python
   # tests/fixtures/validators/fee_validators.py
   from typing import List, Dict, Optional
   from fee_simulator.models import FeeEvent
   
   class FeeEventValidator:
       """Custom assertions for fee events"""
       
       @staticmethod
       def assert_conservation(fee_events: List[FeeEvent], 
                             total_budget: int,
                             tolerance: int = 1):
           """Assert conservation of value"""
           total_in = sum(e.cost for e in fee_events if e.cost)
           total_out = sum(e.earned for e in fee_events if e.earned)
           total_burned = sum(e.burned for e in fee_events if e.burned)
           
           assert abs(total_in - (total_out + total_burned)) <= tolerance, \
               f"Conservation failed: {total_in} != {total_out} + {total_burned}"
       
       @staticmethod
       def assert_no_negative_balances(fee_events: List[FeeEvent]):
           """Assert no address has negative balance"""
           balances = {}
           
           for event in fee_events:
               addr = event.address
               if addr not in balances:
                   balances[addr] = 0
               
               if event.earned:
                   balances[addr] += event.earned
               if event.cost:
                   balances[addr] -= event.cost
               if event.burned:
                   balances[addr] -= event.burned
               if event.slashed:
                   balances[addr] -= event.slashed
           
           for addr, balance in balances.items():
               assert balance >= 0, \
                   f"Address {addr[:10]}... has negative balance: {balance}"
       
       @staticmethod
       def assert_role_consistency(fee_events: List[FeeEvent]):
           """Assert each address has consistent role per round"""
           round_roles = {}
           
           for event in fee_events:
               if event.round_index is None:
                   continue
               
               key = (event.round_index, event.address)
               if key in round_roles and round_roles[key] != event.role:
                   raise AssertionError(
                       f"Address {event.address[:10]}... has multiple roles "
                       f"in round {event.round_index}: {round_roles[key]} and {event.role}"
                   )
               round_roles[key] = event.role
   ```

#### Day 20-21: Create Integration Tests

1. **Full Flow Integration Test**
   ```python
   # tests/integration/test_full_flow.py
   import pytest
   from tests.fixtures.builders import TransactionBuilder
   from tests.utils.oracle import FeeDistributionOracle
   from tests.fixtures.validators import FeeEventValidator
   
   @pytest.mark.integration
   class TestFullTransactionFlow:
       """Test complete transaction processing flows"""
       
       def test_simple_successful_flow(self, invariant_registry):
           """Test simple successful transaction flow"""
           # Build transaction
           state = (TransactionBuilder()
                   .with_normal_round(majority="AGREE")
                   .build())
           
           # Verify basic properties
           assert len(state.fee_events) > 0
           assert len(state.round_labels) == 1
           assert state.round_labels[0] == "NORMAL_ROUND"
           
           # Check invariants
           violations = invariant_registry.check_all(state)
           assert not violations
           
           # Custom validations
           FeeEventValidator.assert_conservation(
               state.fee_events, 
               state.total_costs
           )
           FeeEventValidator.assert_no_negative_balances(state.fee_events)
           FeeEventValidator.assert_role_consistency(state.fee_events)
       
       def test_complex_appeal_chain(self, invariant_registry, oracle):
           """Test complex chain of appeals"""
           # Build complex scenario
           builder = TransactionBuilder()
           
           # Add multiple rounds with appeals
           for i in range(3):
               builder.with_normal_round(majority="AGREE" if i % 2 == 0 else "DISAGREE")
               builder.with_appeal_round(appeal_type="VALIDATOR", successful=i % 2 == 1)
           
           builder.with_normal_round(majority="UNDETERMINED")
           state = builder.build()
           
           # Calculate expected outcome
           expected = oracle.calculate_expected(
               state.transaction_results,
               state.transaction_budget
           )
           
           # Verify against oracle
           discrepancies = oracle.verify_actual(
               expected,
               state.fee_events,
               state.round_labels
           )
           assert not discrepancies, f"Oracle validation failed: {discrepancies}"
           
           # Check invariants
           violations = invariant_registry.check_all(state)
           assert not violations
       
       @pytest.mark.parametrize("num_rounds", [1, 5, 10, 20])
       def test_scaling_behavior(self, num_rounds, invariant_registry):
           """Test system scales correctly with more rounds"""
           builder = TransactionBuilder()
           
           for i in range(num_rounds):
               builder.with_normal_round(
                   majority=["AGREE", "DISAGREE", "UNDETERMINED"][i % 3]
               )
           
           state = builder.build()
           
           # Basic sanity checks
           assert len(state.round_labels) == num_rounds
           assert len(state.fee_events) >= num_rounds  # At least one event per round
           
           # Invariants should hold regardless of size
           violations = invariant_registry.check_critical(state)
           assert not violations
   ```

#### Day 22: Parallel Testing Setup

1. **Configure Parallel Execution**
   ```python
   # tests/conftest.py (additions)
   import pytest
   from _pytest.config import Config
   from typing import Dict, Any
   
   def pytest_configure(config: Config):
       """Configure pytest with custom options"""
       
       # Add markers
       config.addinivalue_line("markers", "quick: marks tests as quick (<1s)")
       config.addinivalue_line("markers", "slow: marks tests as slow (>10s)")
       config.addinivalue_line("markers", "invariants: marks invariant tests")
       config.addinivalue_line("markers", "scenarios: marks scenario tests")
       config.addinivalue_line("markers", "integration: marks integration tests")
       config.addinivalue_line("markers", "performance: marks performance tests")
       
       # Configure xdist for parallel execution
       if hasattr(config, 'workerinput'):
           # We're in a worker process
           worker_id = config.workerinput['workerid']
           # Each worker gets its own test database/state
           config.test_worker_id = worker_id
   
   def pytest_collection_modifyitems(config, items):
       """Modify test collection for better parallel execution"""
       
       # Group tests by marker for better distribution
       quick_tests = []
       slow_tests = []
       other_tests = []
       
       for item in items:
           if item.get_closest_marker('slow'):
               slow_tests.append(item)
           elif item.get_closest_marker('quick'):
               quick_tests.append(item)
           else:
               other_tests.append(item)
       
       # Reorder so quick tests run first
       items[:] = quick_tests + other_tests + slow_tests
   
   @pytest.fixture(scope="session")
   def worker_id(request):
       """Get worker ID for parallel execution"""
       if hasattr(request.config, 'workerinput'):
           return request.config.workerinput['workerid']
       return "master"
   ```

### Phase 4: Validation and Cutover (3 days)

#### Day 23: Create Comparison Tests

1. **Test Comparison Script**
   ```python
   # scripts/test_migration/compare_tests.py
   import subprocess
   import json
   from pathlib import Path
   from typing import Dict, List, Tuple
   
   def run_tests(test_path: str, marker: str = "") -> Dict[str, Any]:
       """Run tests and capture results"""
       cmd = ["pytest", test_path, "--json-report", "--json-report-file=report.json"]
       if marker:
           cmd.extend(["-m", marker])
       
       result = subprocess.run(cmd, capture_output=True, text=True)
       
       # Load report
       with open("report.json", "r") as f:
           report = json.load(f)
       
       return {
           "total": report["summary"]["total"],
           "passed": report["summary"]["passed"],
           "failed": report["summary"]["failed"],
           "duration": report["duration"],
           "exit_code": result.returncode
       }
   
   def compare_test_results():
       """Compare old and new test results"""
       
       comparisons = [
           ("Old Invariant Tests", "tests/fee_distributions/check_invariants", 
            "New Invariant Tests", "tests/invariants"),
           
           ("Old Round Type Tests", "tests/round_types_tests",
            "New Scenario Tests", "tests/scenarios/common"),
           
           ("Old Integration", "tests/round_combinations",
            "New Integration", "tests/integration"),
       ]
       
       results = []
       
       for old_name, old_path, new_name, new_path in comparisons:
           print(f"\nComparing {old_name} vs {new_name}")
           
           old_results = run_tests(old_path)
           new_results = run_tests(new_path)
           
           comparison = {
               "category": old_name.split()[1],
               "old": old_results,
               "new": new_results,
               "status": "PASS" if (
                   new_results["passed"] >= old_results["passed"] and
                   new_results["failed"] <= old_results["failed"]
               ) else "FAIL"
           }
           
           results.append(comparison)
           
           print(f"  Old: {old_results['passed']}/{old_results['total']} passed")
           print(f"  New: {new_results['passed']}/{new_results['total']} passed")
           print(f"  Status: {comparison['status']}")
       
       # Save results
       with open("docs/test_comparison_results.json", "w") as f:
           json.dump(results, f, indent=2)
       
       # Overall status
       all_pass = all(r["status"] == "PASS" for r in results)
       print(f"\nOverall Status: {'PASS' if all_pass else 'FAIL'}")
       
       return all_pass
   
   if __name__ == "__main__":
       success = compare_test_results()
       exit(0 if success else 1)
   ```

#### Day 24: Performance Benchmarks

1. **Create Performance Baselines**
   ```python
   # tests/performance/benchmarks/create_baseline.py
   import pytest
   import json
   import time
   from pathlib import Path
   from typing import Dict, List
   from tests.fixtures.builders import TransactionBuilder
   from fee_simulator.core.transaction_processing import process_transaction
   
   class PerformanceBaseline:
       """Create performance baselines for the system"""
       
       def __init__(self):
           self.results = {}
       
       def benchmark_transaction_processing(self):
           """Benchmark transaction processing at different scales"""
           
           scales = [1, 5, 10, 20, 50]
           results = {}
           
           for num_rounds in scales:
               # Build transaction
               builder = TransactionBuilder()
               for _ in range(num_rounds):
                   builder.with_normal_round()
               
               state = builder.build()
               
               # Measure processing time
               times = []
               for _ in range(10):  # 10 runs
                   start = time.perf_counter()
                   fee_events, labels = process_transaction(
                       state.addresses,
                       state.transaction_results,
                       state.transaction_budget
                   )
                   end = time.perf_counter()
                   times.append(end - start)
               
               results[num_rounds] = {
                   "mean": sum(times) / len(times),
                   "min": min(times),
                   "max": max(times),
                   "rounds": num_rounds,
                   "events": len(fee_events)
               }
           
           self.results["transaction_processing"] = results
       
       def benchmark_invariant_checking(self):
           """Benchmark invariant checking performance"""
           
           from tests.invariants.registry import InvariantRegistry
           from tests.invariants.core import all_invariants
           
           registry = InvariantRegistry()
           for inv in all_invariants():
               registry.register(inv)
           
           # Create test states
           states = []
           for num_rounds in [1, 5, 10]:
               builder = TransactionBuilder()
               for _ in range(num_rounds):
                   builder.with_normal_round()
               states.append(builder.build())
           
           results = {}
           
           for state in states:
               times = []
               for _ in range(100):  # 100 runs
                   start = time.perf_counter()
                   violations = registry.check_all(state)
                   end = time.perf_counter()
                   times.append(end - start)
               
               results[len(state.round_labels)] = {
                   "mean": sum(times) / len(times),
                   "min": min(times),
                   "max": max(times),
                   "invariants_checked": len(registry._invariants)
               }
           
           self.results["invariant_checking"] = results
       
       def save_baseline(self):
           """Save baseline to file"""
           baseline_file = Path("tests/performance/benchmarks/baseline_metrics.json")
           baseline_file.parent.mkdir(parents=True, exist_ok=True)
           
           with open(baseline_file, "w") as f:
               json.dump(self.results, f, indent=2)
           
           print(f"Baseline saved to {baseline_file}")
   
   if __name__ == "__main__":
       baseline = PerformanceBaseline()
       
       print("Creating transaction processing baseline...")
       baseline.benchmark_transaction_processing()
       
       print("Creating invariant checking baseline...")
       baseline.benchmark_invariant_checking()
       
       baseline.save_baseline()
       
       # Print summary
       for category, results in baseline.results.items():
           print(f"\n{category}:")
           for scale, metrics in results.items():
               print(f"  Scale {scale}: {metrics['mean']*1000:.2f}ms average")
   ```

#### Day 25: Final Validation and Cutover

1. **Cutover Checklist**
   ```markdown
   # docs/test_cutover_checklist.md
   
   ## Pre-Cutover Validation
   
   - [ ] All tests migrated to new structure
   - [ ] Test count comparison shows no regression
   - [ ] Coverage metrics maintained or improved
   - [ ] Performance baselines established
   - [ ] Parallel execution configured and tested
   - [ ] CI/CD pipelines updated
   
   ## Cutover Steps
   
   1. [ ] Create backup branch of current tests
      ```bash
      git checkout -b backup/old-test-structure
      git push origin backup/old-test-structure
      ```
   
   2. [ ] Run final comparison
      ```bash
      python scripts/test_migration/compare_tests.py
      ```
   
   3. [ ] Update CI configuration
      - [ ] Update `.github/workflows/tests.yml`
      - [ ] Update `pytest.ini`
      - [ ] Update test commands in README
   
   4. [ ] Remove old test directories
      ```bash
      rm -rf tests/round_types_tests  # Duplicate directory
      rm -rf tests/fee_distributions/simple_round_types_tests  # Migrated
      ```
   
   5. [ ] Run full test suite
      ```bash
      pytest --cov=fee_simulator --cov-report=html
      ```
   
   6. [ ] Update documentation
      - [ ] Update TESTING.md
      - [ ] Update contribution guidelines
      - [ ] Update onboarding docs
   
   ## Post-Cutover
   
   - [ ] Monitor CI/CD for any issues
   - [ ] Gather team feedback
   - [ ] Create issues for any remaining work
   - [ ] Schedule retrospective
   ```

2. **Final Migration Script**
   ```python
   # scripts/test_migration/finalize_migration.py
   import shutil
   import subprocess
   from pathlib import Path
   from datetime import datetime
   
   def finalize_migration():
       """Finalize the test migration"""
       
       print("Starting test migration finalization...")
       
       # 1. Create backup
       timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
       backup_dir = Path(f"tests_backup_{timestamp}")
       print(f"Creating backup in {backup_dir}")
       shutil.copytree("tests", backup_dir)
       
       # 2. Run final test comparison
       print("\nRunning test comparison...")
       result = subprocess.run(
           ["python", "scripts/test_migration/compare_tests.py"],
           capture_output=True
       )
       
       if result.returncode != 0:
           print("ERROR: Test comparison failed!")
           print("Aborting migration.")
           return False
       
       # 3. Remove old directories
       old_dirs = [
           "tests/round_types_tests",
           "tests/fee_distributions/simple_round_types_tests",
           "tests/fee_distributions/check_invariants",
       ]
       
       for old_dir in old_dirs:
           if Path(old_dir).exists():
               print(f"Removing {old_dir}")
               shutil.rmtree(old_dir)
       
       # 4. Update pytest.ini
       pytest_ini = """[pytest]
   markers =
       quick: Quick smoke tests (< 1 minute total)
       standard: Standard test suite (< 10 minutes)
       slow: Slow exhaustive tests (> 10 minutes)
       invariants: Invariant-focused tests
       scenarios: Real-world scenario tests
       integration: Integration tests
       performance: Performance benchmarks
       
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   
   addopts = 
       --strict-markers
       --tb=short
       -ra
   """
       
       with open("pytest.ini", "w") as f:
           f.write(pytest_ini)
       
       print("\nUpdated pytest.ini")
       
       # 5. Run full test suite
       print("\nRunning full test suite...")
       result = subprocess.run(
           ["pytest", "--cov=fee_simulator", "--cov-report=term"],
           capture_output=False
       )
       
       if result.returncode != 0:
           print("\nWARNING: Some tests failed in new structure")
           print("Please review and fix before committing")
       else:
           print("\nSUCCESS: All tests passing in new structure!")
       
       # 6. Create summary report
       summary = f"""
   # Test Migration Summary
   
   Date: {datetime.now().isoformat()}
   
   ## Actions Taken
   - Created backup in {backup_dir}
   - Migrated all tests to new structure
   - Removed duplicate/old test directories
   - Updated pytest configuration
   - Ran full test suite
   
   ## Next Steps
   1. Review test results
   2. Commit changes
   3. Update CI/CD configuration
   4. Notify team
   
   ## New Test Structure
   - tests/invariants/     - System invariants (22 invariants)
   - tests/scenarios/      - Real-world test scenarios  
   - tests/components/     - Component unit tests
   - tests/integration/    - Integration tests
   - tests/performance/    - Performance benchmarks
   - tests/fixtures/       - Shared test utilities
   """
       
       with open("docs/test_migration_summary.md", "w") as f:
           f.write(summary)
       
       print("\nMigration complete! Summary saved to docs/test_migration_summary.md")
       return True
   
   if __name__ == "__main__":
       success = finalize_migration()
       exit(0 if success else 1)
   ```

## Success Metrics

### Quantitative Metrics
- **Test Execution Time**: 50% reduction for standard test suite
- **Test Maintenance**: 70% reduction in lines of test code
- **Coverage**: Maintain 100% coverage with fewer tests
- **Duplication**: Zero duplicate tests

### Qualitative Metrics
- **Developer Confidence**: Invariants catch bugs early
- **Test Clarity**: Each test has one clear purpose
- **Debugging Speed**: Invariant violations pinpoint issues
- **Onboarding**: New developers understand test structure quickly

## Risk Mitigation

### Risk 1: Test Regression
**Mitigation**: 
- Keep old tests running in parallel during migration
- Run comparison tests at each phase
- Only remove old tests after validation

### Risk 2: Team Disruption
**Mitigation**:
- Communicate plan clearly
- Migrate in small batches
- Provide training on new patterns
- Document extensively

### Risk 3: CI/CD Breakage
**Mitigation**:
- Test CI changes in separate branch
- Have rollback plan ready
- Update in stages (quick tests first)

## Timeline Summary

### Week 1: Infrastructure
- Days 1-2: Preparation and planning
- Days 3-7: Core infrastructure implementation

### Week 2-3: Migration
- Days 8-12: Test builders and utilities
- Days 13-17: Migrate core tests

### Week 4: Integration
- Days 18-22: Integration and validation
- Days 23-25: Final cutover

### Week 5: Stabilization
- Monitor and fix any issues
- Gather feedback
- Plan phase 2 improvements

## Conclusion

This migration strategy provides a clear, step-by-step path from the current test architecture to the new invariant-first approach. By following this plan, we can achieve a more maintainable, reliable, and efficient test suite while minimizing risk and disruption to the team.

The key to success is the incremental approach - each phase provides value on its own, and we can pause or adjust based on feedback and results.