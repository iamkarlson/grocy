#!/usr/bin/env python3
"""
Validate consistency between test-feature-map.yaml and pytest markers.

Checks:
  1. Every test in the YAML map has a matching @pytest.mark.feature() marker
  2. Every @pytest.mark.feature() marker in test files is in the YAML map
  3. Every feature group has at least one test
  4. Summary of test counts per feature group

Run: uv run python docs/check_coverage.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "docs" / "test-feature-map.yaml"
TESTS_DIR = ROOT / "tests"


def load_yaml_map() -> dict:
    """Load and return the test-feature-map.yaml contents."""
    with open(YAML_PATH) as f:
        return yaml.safe_load(f)


def _extract_marker_names(decorator_node: ast.expr) -> list[str]:
    """Extract feature names from a pytest.mark.feature(...) decorator AST node."""
    # Match: @pytest.mark.feature("name")
    if not isinstance(decorator_node, ast.Call):
        return []

    func = decorator_node.func
    # pytest.mark.feature(...)
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "feature"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "mark"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "pytest"
    ):
        return [
            arg.value
            for arg in decorator_node.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        ]
    return []


def _extract_pytestmark_features(node: ast.Assign) -> list[str]:
    """Extract feature names from pytestmark = pytest.mark.feature(...)."""
    if not (
        len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "pytestmark"
    ):
        return []

    value = node.value
    # Single marker: pytestmark = pytest.mark.feature("name")
    if isinstance(value, ast.Call):
        return _extract_marker_names(value)

    # List of markers: pytestmark = [pytest.mark.feature("a"), ...]
    if isinstance(value, ast.List):
        names = []
        for elt in value.elts:
            names.extend(_extract_marker_names(elt))
        return names

    return []


def scan_test_file(filepath: Path) -> dict[str, set[str]]:
    """
    Scan a test file and return {function_name: {feature_names}} from markers.

    Handles:
    - Module-level pytestmark (applies to all test functions)
    - Class-level pytestmark (applies to all methods in class)
    - Function-level @pytest.mark.feature() decorators
    - Class-level @pytest.mark.feature() decorators
    """
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))

    result: dict[str, set[str]] = {}
    module_features: set[str] = set()

    # First pass: find module-level pytestmark
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            module_features.update(_extract_pytestmark_features(node))

    # Second pass: find functions and classes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("test_"):
                func_features = set(module_features)
                for dec in node.decorator_list:
                    func_features.update(_extract_marker_names(dec))
                result[node.name] = func_features

        elif isinstance(node, ast.ClassDef):
            class_features: set[str] = set()
            # Class-level decorators
            for dec in node.decorator_list:
                class_features.update(_extract_marker_names(dec))
            # Class-level pytestmark attribute
            for item in node.body:
                if isinstance(item, ast.Assign):
                    class_features.update(_extract_pytestmark_features(item))

            # Methods in class
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    if item.name.startswith("test_"):
                        func_features = set(module_features) | set(class_features)
                        for dec in item.decorator_list:
                            func_features.update(_extract_marker_names(dec))
                        result[item.name] = func_features

    return result


def build_yaml_index(data: dict) -> dict[str, dict[str, set[str]]]:
    """
    Build {file: {function: {features}}} from YAML data.

    Returns mapping of relative file path -> function name -> set of feature names.
    """
    index: dict[str, dict[str, set[str]]] = {}

    all_features = {}
    if "features" in data:
        all_features.update(data["features"])
    if "cross_cutting" in data:
        all_features["cross_cutting"] = data["cross_cutting"]

    for feature_key, feature_data in all_features.items():
        for test_entry in feature_data.get("tests", []):
            filepath = test_entry["file"]
            if filepath not in index:
                index[filepath] = {}
            for func_name in test_entry.get("functions", []):
                if func_name not in index[filepath]:
                    index[filepath][func_name] = set()
                index[filepath][func_name].add(feature_key)

    return index


def main() -> int:
    data = load_yaml_map()
    yaml_index = build_yaml_index(data)

    errors: list[str] = []
    warnings: list[str] = []

    # Collect all features and their test counts
    all_features: dict[str, int] = {}
    feature_sources = {}
    if "features" in data:
        feature_sources.update(data["features"])
    if "cross_cutting" in data:
        feature_sources["cross_cutting"] = data["cross_cutting"]

    for feature_key, feature_data in feature_sources.items():
        count = sum(
            len(entry.get("functions", [])) for entry in feature_data.get("tests", [])
        )
        all_features[feature_key] = count

    # Check 1: Features without tests
    for feature_key, count in all_features.items():
        if count == 0:
            errors.append(f"Feature '{feature_key}' has no tests mapped in YAML")

    # Check 2 & 3: Compare YAML map with actual markers in test files
    all_test_files = sorted(TESTS_DIR.glob("test_*.py"))
    yaml_only: list[str] = []  # in YAML but no marker
    marker_only: list[str] = []  # has marker but not in YAML
    mismatched: list[str] = []  # both exist but features differ

    for test_file in all_test_files:
        rel_path = f"tests/{test_file.name}"
        actual_markers = scan_test_file(test_file)
        yaml_functions = yaml_index.get(rel_path, {})

        # Functions in YAML but not in file
        for func_name in yaml_functions:
            if func_name not in actual_markers:
                errors.append(
                    f"YAML maps '{func_name}' in {rel_path} but function not found"
                )

        # Check each actual test function
        for func_name, marker_features in actual_markers.items():
            yaml_features = yaml_functions.get(func_name, set())

            if marker_features and not yaml_features:
                marker_only.append(
                    f"  {rel_path}::{func_name} markers={sorted(marker_features)}"
                )
            elif yaml_features and not marker_features:
                yaml_only.append(
                    f"  {rel_path}::{func_name} yaml={sorted(yaml_features)}"
                )
            elif marker_features != yaml_features:
                mismatched.append(
                    f"  {rel_path}::{func_name} "
                    f"markers={sorted(marker_features)} "
                    f"yaml={sorted(yaml_features)}"
                )

    # Check for YAML entries referencing non-existent files
    existing_files = {f"tests/{f.name}" for f in all_test_files}
    for filepath in yaml_index:
        if filepath not in existing_files:
            errors.append(f"YAML references non-existent file: {filepath}")

    # Report
    print("=" * 60)
    print("Feature Coverage Validation Report")
    print("=" * 60)

    # Summary table
    print("\nFeature Test Counts:")
    print("-" * 40)
    total = 0
    for feature_key in sorted(all_features):
        count = all_features[feature_key]
        total += count
        name = feature_sources[feature_key].get("name", feature_key)
        print(f"  {name:<30s} {count:>4d}")
    print("-" * 40)
    print(f"  {'Total (with overlap)':<30s} {total:>4d}")

    # Unique test count
    unique_tests: set[str] = set()
    for filepath, funcs in yaml_index.items():
        for func_name in funcs:
            unique_tests.add(f"{filepath}::{func_name}")
    print(f"  {'Unique test functions':<30s} {len(unique_tests):>4d}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  [ERROR] {e}")

    if yaml_only:
        print(f"\nIn YAML but missing marker ({len(yaml_only)}):")
        for item in yaml_only:
            print(item)

    if marker_only:
        print(f"\nHas marker but not in YAML ({len(marker_only)}):")
        for item in marker_only:
            print(item)

    if mismatched:
        print(f"\nFeature mismatch ({len(mismatched)}):")
        for item in mismatched:
            print(item)

    if not errors and not yaml_only and not marker_only and not mismatched:
        print("\nAll checks passed!")

    has_issues = bool(errors or yaml_only or marker_only or mismatched)
    print(f"\nStatus: {'FAIL' if has_issues else 'OK'}")
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
