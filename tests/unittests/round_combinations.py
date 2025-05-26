import numpy as np


def count_paths_adj_matrix(dependency_graph, max_rounds, source_nodes, verbose=False):
    nodes = sorted(dependency_graph.keys())
    n = len(nodes)
    A = np.zeros((n, n), dtype=int)

    for i, node in enumerate(nodes):
        for next_node in dependency_graph[node]:
            j = nodes.index(next_node)
            A[i, j] = 1

    source_indices = [nodes.index(node) for node in source_nodes]
    total_paths = len(source_nodes)
    if verbose:
        print(f"Length 1: {total_paths}")

    current_power = A
    for k in range(1, max_rounds):
        paths_k = sum(np.sum(current_power[idx]) for idx in source_indices)
        total_paths += paths_k
        if verbose:
            print(f"Length {k+1}: {paths_k}")
        current_power = np.dot(current_power, A)

    return total_paths


def generate_all_paths(graph, max_depth, source_nodes, verbose=False):
    def dfs(current_node, current_path, depth):
        # Add the current path at every step (including length 1)
        length = len(current_path)  # depth 0 -> length 1, depth 1 -> length 2, etc.
        length_counts[length] = length_counts.get(length, 0) + 1
        all_paths.append(current_path[:])

        # Stop if we've reached the maximum depth
        if depth >= max_depth:
            return

        # Explore next nodes
        next_nodes = graph.get(current_node, [])
        for next_node in next_nodes:
            current_path.append(next_node)
            dfs(next_node, current_path, depth + 1)
            current_path.pop()

    all_paths = []
    length_counts = {}

    for start_node in source_nodes:
        dfs(start_node, [start_node], 0)

    if verbose:
        for length in range(1, max_depth + 1):
            print(f"Generate all paths Length {length}: {length_counts.get(length, 0)}")

    return all_paths


# Combined Dependency Graph
combined_graph = {
    "LEADER_RECEIPT": [
        "MAJORITY_AGREE",
        "UNDETERMINED",
        "MAJORITY_DISAGREE",
        "MAJORITY_TIMEOUT",
    ],
    "LEADER_TIMEOUT": ["LEADER_APPEAL"],
    "MAJORITY_AGREE": ["VALIDATOR_APPEAL"],
    "UNDETERMINED": ["LEADER_APPEAL"],
    "MAJORITY_DISAGREE": ["LEADER_APPEAL"],
    "MAJORITY_TIMEOUT": ["VALIDATOR_APPEAL"],
    "VALIDATOR_APPEAL": ["LEADER_RECEIPT", "LEADER_TIMEOUT"],
    "LEADER_APPEAL": ["LEADER_RECEIPT", "LEADER_TIMEOUT"],
}

depth = 17
source_nodes = ["LEADER_RECEIPT", "LEADER_TIMEOUT"]
dfs_depth = depth - 1
all_paths = generate_all_paths(combined_graph, dfs_depth, source_nodes)

if __name__ == "__main__":
    # Compute total paths (adjacency matrix)
    depth = 17
    source_nodes = ["LEADER_RECEIPT", "LEADER_TIMEOUT"]
    total_paths = count_paths_adj_matrix(combined_graph, depth, source_nodes)
    print(
        f"Total Transactions (up to depth {depth}, starting from {source_nodes}): {total_paths}"
    )

    # Print all paths (DFS, adjust max_depth to match lengths 1 to 17)
    dfs_depth = depth - 1  # Depth 16 gives paths of length 1 to 17
    all_paths = generate_all_paths(combined_graph, dfs_depth, source_nodes)
print(
    f"All Paths (up to depth {dfs_depth}, starting from {source_nodes}): length {len(all_paths)}"
)
