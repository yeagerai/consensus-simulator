"""
Round Combinations Analysis Package

A clean, modular implementation for analyzing transaction paths
in the fee simulator system.
"""

from .path_types import (
    PathConstraints,
    PathStatistics,
    CountingResult,
    NodeName,
    Path,
    Graph,
)

from .graph_data import TRANSACTION_GRAPH, get_graph

from .path_counter import count_paths_between_nodes, get_reachable_nodes

from .path_generator import (
    generate_all_paths,
    generate_paths_lazy,
    filter_paths_containing_pattern,
    count_paths_by_length,
)

from .path_analyzer import (
    analyze_paths,
    find_extreme_paths,
    find_paths_with_rare_patterns,
    calculate_path_diversity,
    group_paths_by_feature,
)

from .round_combinations import TransactionPathAnalyzer

__version__ = "1.0.0"

__all__ = [
    # Types
    "PathConstraints",
    "PathStatistics",
    "CountingResult",
    "NodeName",
    "Path",
    "Graph",
    # Data
    "TRANSACTION_GRAPH",
    "get_graph",
    # Counting
    "count_paths_between_nodes",
    "get_reachable_nodes",
    # Generation
    "generate_all_paths",
    "generate_paths_lazy",
    "filter_paths_containing_pattern",
    "count_paths_by_length",
    # Analysis
    "analyze_paths",
    "find_extreme_paths",
    "find_paths_with_rare_patterns",
    "calculate_path_diversity",
    "group_paths_by_feature",
    # High-level
    "TransactionPathAnalyzer",
]
