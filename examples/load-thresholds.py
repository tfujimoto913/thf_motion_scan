#!/usr/bin/env python3
"""
Example: Load and use thresholds.json

Purpose: Demonstrate how to load thresholds.json and access threshold values
Responsibility: Sample code for integration
Created: 2025-11-02
Decision Log: ADR-028 (thresholds.json v1.0.0 export)

Usage:
    python examples/load-thresholds.py
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError:
    print("Warning: jsonschema not installed. Skipping schema validation.")
    jsonschema = None


class ThresholdLoader:
    """
    Load and access threshold configurations.

    What: Centralize thresholds.json loading and access patterns
    Why: Provide reusable interface for threshold lookup
    Design Decision: Validate on load, cache in memory
    """

    def __init__(self, thresholds_path: Path, schema_path: Optional[Path] = None):
        """
        Initialize loader and load thresholds.

        Args:
            thresholds_path: Path to thresholds.json
            schema_path: Optional path to schema (for validation)
        """
        self.thresholds_path = thresholds_path
        self.schema_path = schema_path
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load and optionally validate thresholds.json."""
        with open(self.thresholds_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Optional schema validation
        if self.schema_path and jsonschema:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            validator = Draft7Validator(schema)
            validator.validate(data)
            print(f"✅ Schema validation passed")

        return data

    def get_versions(self) -> Dict[str, str]:
        """
        Get version information.

        Returns: Dict with rules_version, normalization_version, artifact_sha
        """
        return self._data.get("versions", {})

    def get_test_thresholds(self, test_code: str) -> Optional[Dict[str, Any]]:
        """
        Get threshold configuration for a specific test.

        Args:
            test_code: Test code (e.g., 'single_leg_squat')

        Returns: Test threshold dict or None if not found
        """
        return self._data.get("tests", {}).get(test_code)

    def get_bands(self, test_code: str) -> list:
        """
        Get primary threshold bands for a test.

        Args:
            test_code: Test code

        Returns: List of band dicts
        """
        test_config = self.get_test_thresholds(test_code)
        if not test_config:
            return []
        return test_config.get("thresholds", {}).get("primary", {}).get("bands", [])

    def classify_value(self, test_code: str, value: float) -> Optional[str]:
        """
        Classify a measurement value against threshold bands.

        What: Evaluate value against bands and return classification name
        Why: Demonstrate threshold evaluation logic
        Design Decision: Simple sequential check (first match wins)

        CRITICAL: This is a simplified example. Production code should handle
                  overlapping bands, hysteresis, and edge cases properly.

        Args:
            test_code: Test code
            value: Measured value to classify

        Returns: Band name ('pass', 'border', 'fail') or None if no match
        """
        bands = self.get_bands(test_code)

        for band in bands:
            op = band.get("op")
            threshold = band.get("value")
            name = band.get("name")

            matched = False
            if op == "gte" and value >= threshold:
                matched = True
            elif op == "gt" and value > threshold:
                matched = True
            elif op == "lte" and value <= threshold:
                matched = True
            elif op == "lt" and value < threshold:
                matched = True
            elif op == "eq" and value == threshold:
                matched = True
            elif op == "range_inc" and isinstance(threshold, list) and len(threshold) == 2:
                if threshold[0] <= value <= threshold[1]:
                    matched = True

            if matched:
                return name

        return None


def main():
    """Demonstrate ThresholdLoader usage."""

    # Paths
    repo_root = Path(__file__).parent.parent
    thresholds_path = repo_root / "config" / "thresholds.json"
    schema_path = repo_root / "schema" / "thresholds.schema.json"

    print(f"Loading thresholds from: {thresholds_path}")
    print("-" * 60)

    # Load thresholds
    loader = ThresholdLoader(thresholds_path, schema_path)

    # Display versions
    versions = loader.get_versions()
    print(f"\nVersions:")
    print(f"  rules_version: {versions.get('rules_version')}")
    print(f"  normalization_version: {versions.get('normalization_version')}")
    print(f"  artifact_sha: {versions.get('artifact_sha')}")

    # Example: Get thresholds for single_leg_squat
    test_code = "single_leg_squat"
    print(f"\nThresholds for '{test_code}':")
    bands = loader.get_bands(test_code)
    for i, band in enumerate(bands):
        print(f"  Band {i}: {band['name']} (op={band['op']}, value={band['value']})")

    # Example: Classify values
    print(f"\nClassification examples for '{test_code}':")
    test_values = [50, 70, 85]
    for value in test_values:
        classification = loader.classify_value(test_code, value)
        print(f"  Value {value} → {classification}")

    print("\n✅ Example completed successfully")


if __name__ == "__main__":
    main()
