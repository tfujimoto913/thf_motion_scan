#!/usr/bin/env python3
"""
Example: Check thresholds.json version compatibility

Purpose: Demonstrate compatibility checking between current and required versions
Responsibility: CLI tool for version compatibility validation
Created: 2025-11-03
Decision Log: ADR-031 (thresholds.json compatibility checker)

Usage:
    # Basic usage
    python examples/check-compat.py

    # With custom thresholds file
    python examples/check-compat.py --current config/thresholds.json

    # Strict mode (treat WARN as ERROR)
    COMPAT_POLICY=strict python examples/check-compat.py

    # Permissive mode (all non-ERROR as OK)
    COMPAT_POLICY=permissive python examples/check-compat.py
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_thresholds, get_versions
from src.config.compat import check_compat


def main():
    """Run compatibility check CLI."""

    parser = argparse.ArgumentParser(
        description="Check thresholds.json version compatibility"
    )
    parser.add_argument(
        "--current",
        type=str,
        default="config/thresholds.json",
        help="Path to current thresholds.json (default: config/thresholds.json)"
    )
    parser.add_argument(
        "--required-rules-version",
        type=str,
        default="v0.1.0",
        help="Required rules_version (default: v0.1.0)"
    )
    parser.add_argument(
        "--required-normalization-version",
        type=str,
        default="none",
        help="Required normalization_version (default: none)"
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    current_path = repo_root / args.current

    print("=" * 60)
    print("Thresholds.json Version Compatibility Check")
    print("=" * 60)
    print()

    # Load current thresholds
    try:
        print(f"Loading current thresholds from: {current_path}")
        current_data = load_thresholds(str(current_path))
        current_versions = get_versions(current_data)
        print(f"✅ Loaded successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to load thresholds: {e}")
        sys.exit(1)

    # Display current versions
    print("Current versions:")
    for key, value in current_versions.items():
        print(f"  {key}: {value}")
    print()

    # Build required versions
    required_versions = {
        "rules_version": args.required_rules_version,
        "normalization_version": args.required_normalization_version
    }

    print("Required versions:")
    for key, value in required_versions.items():
        print(f"  {key}: {value}")
    print()

    # Run compatibility check
    print("-" * 60)
    print("Compatibility check:")
    print("-" * 60)
    result = check_compat(current_versions, required_versions)

    # Display results
    print(f"Status: {result['status']}")
    print(f"Reason: {result['reason']}")
    print()

    # Display details
    print("Details:")
    for field, detail in result["details"].items():
        status_symbol = "✅" if detail["compatible"] else "❌"
        print(f"  {status_symbol} {field}:")
        print(f"      current:  {detail['current']}")
        print(f"      required: {detail['required']}")
        print(f"      status:   {detail['status']}")
    print()

    # Check environment variable for policy override
    compat_policy = os.getenv("COMPAT_POLICY", "default")

    exit_code = 0
    if compat_policy == "strict":
        # Strict mode: WARN and ERROR both exit with code 1
        if result["status"] in ["WARN", "ERROR"]:
            print("⚠️  COMPAT_POLICY=strict: Treating WARN as ERROR")
            exit_code = 1
    elif compat_policy == "permissive":
        # Permissive mode: Only ERROR exits with code 1
        if result["status"] == "ERROR":
            exit_code = 1
        else:
            print("ℹ️  COMPAT_POLICY=permissive: Allowing execution despite warnings")
    else:
        # Default mode: ERROR exits with code 1, WARN exits with code 0
        if result["status"] == "ERROR":
            exit_code = 1

    print("=" * 60)
    if exit_code == 0:
        print("✅ Compatibility check passed")
    else:
        print("❌ Compatibility check failed")
    print("=" * 60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
