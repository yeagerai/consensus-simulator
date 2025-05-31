#!/usr/bin/env python3
"""
Script to analyze test results from test_invariants_in_round_combinations.py
"""

import os
import sys
from collections import defaultdict
from datetime import datetime


def analyze_test_results(results_dir="test_results"):
    """Analyze test results and provide summary useful for sending it to an LLM"""

    if not os.path.exists(results_dir):
        print(f"Error: Results directory '{results_dir}' not found")
        return

    # Collect all result files
    success_files = []
    failed_files = []

    for filename in os.listdir(results_dir):
        if filename.endswith(".txt"):
            if filename.startswith("S_"):
                success_files.append(filename)
            elif filename.startswith("F_"):
                failed_files.append(filename)

    total_tests = len(success_files) + len(failed_files)

    print(f"\n{'='*60}")
    print(f"TEST RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {len(success_files)} ({len(success_files)/total_tests*100:.1f}%)")
    print(f"Failed: {len(failed_files)} ({len(failed_files)/total_tests*100:.1f}%)")
    print(f"{'='*60}\n")

    # Analyze failures
    if failed_files:
        print("FAILED TESTS ANALYSIS:")
        print("-" * 60)

        failure_patterns = defaultdict(list)

        for filename in sorted(failed_files):
            filepath = os.path.join(results_dir, filename)
            with open(filepath, "r") as f:
                content = f.read()

            # Extract test path
            path_line = content.split("\n")[0]
            if path_line.startswith("TEST PATH: "):
                test_path = path_line[11:]
            else:
                test_path = "Unknown"

            # Extract error message
            error_msg = "Unknown error"
            for line in content.split("\n"):
                if "Invariant failed:" in line:
                    error_msg = line.split("Invariant failed:", 1)[1].strip()
                    break
                elif "Test failed with error:" in line:
                    error_msg = line.split("Test failed with error:", 1)[1].strip()
                    break

            # Extract round labels if available
            round_labels = []
            for line in content.split("\n"):
                if line.startswith("ROUND LABELS:"):
                    next_line_idx = content.split("\n").index(line) + 1
                    if next_line_idx < len(content.split("\n")):
                        labels_line = content.split("\n")[next_line_idx]
                        if labels_line.startswith("[") and labels_line.endswith("]"):
                            round_labels = eval(labels_line)
                    break

            # Group by error pattern
            failure_patterns[error_msg].append((filename, test_path, round_labels))

            print(f"\n{filename}")
            print(f"  Path: {test_path}")
            print(f"  Error: {error_msg}")
            if round_labels:
                print(f"  Labels: {' -> '.join(round_labels)}")

        # Summary of failure patterns
        print(f"\n{'='*60}")
        print("FAILURE PATTERNS:")
        print("-" * 60)

        for error_msg, tests in sorted(
            failure_patterns.items(), key=lambda x: -len(x[1])
        ):
            print(f"\nError: {error_msg}")
            print(f"Count: {len(tests)}")
            print("Affected paths:")
            for filename, path, labels in tests[:5]:  # Show first 5
                print(f"  - {path}")
                if labels:
                    print(f"    Labels: {' -> '.join(labels)}")
            if len(tests) > 5:
                print(f"  ... and {len(tests) - 5} more")

    # Show some successful test examples
    if success_files:
        print(f"\n{'='*60}")
        print("SAMPLE SUCCESSFUL TESTS:")
        print("-" * 60)

        for filename in sorted(success_files)[:5]:
            filepath = os.path.join(results_dir, filename)
            with open(filepath, "r") as f:
                first_line = f.readline().strip()

            if first_line.startswith("TEST PATH: "):
                test_path = first_line[11:]
                print(f"  ✓ {test_path}")


def find_specific_pattern(results_dir="test_results", pattern=None):
    """Find tests with specific path patterns"""

    if not pattern:
        print("Please provide a pattern to search for")
        return

    matching_files = []

    for filename in os.listdir(results_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(results_dir, filename)
            with open(filepath, "r") as f:
                first_line = f.readline().strip()

            if first_line.startswith("TEST PATH: "):
                test_path = first_line[11:]
                if pattern.lower() in test_path.lower():
                    matching_files.append((filename, test_path))

    print(f"\nTests matching pattern '{pattern}':")
    print("-" * 60)

    for filename, path in sorted(matching_files):
        status = "✓" if filename.startswith("S_") else "✗"
        print(f"{status} {filename}: {path}")


def clean_results(results_dir="test_results"):
    """Clean up old test results"""

    response = input(
        f"Are you sure you want to delete all files in '{results_dir}'? (y/N): "
    )
    if response.lower() == "y":
        count = 0
        for filename in os.listdir(results_dir):
            if filename.endswith(".txt"):
                os.remove(os.path.join(results_dir, filename))
                count += 1
        print(f"Deleted {count} files")
    else:
        print("Cleanup cancelled")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze test results")
    parser.add_argument("--dir", default="test_results", help="Results directory")
    parser.add_argument("--find", help="Find tests with specific pattern")
    parser.add_argument("--clean", action="store_true", help="Clean all results")

    args = parser.parse_args()

    if args.clean:
        clean_results(args.dir)
    elif args.find:
        find_specific_pattern(args.dir, args.find)
    else:
        analyze_test_results(args.dir)
