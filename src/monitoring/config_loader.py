"""
Monitoring Configuration Loader with Environment-Specific Overrides

Purpose: Load monitoring thresholds with env-specific overrides and fallback
Responsibility: Config loading, merging, validation, and error handling
Created: 2025-11-04
Decision Log: ADR-040 (UI Monitoring System)

CRITICAL: Fallback to base config on any error to ensure system stability
"""

import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Default paths
CONFIG_DIR = Path(__file__).parent.parent.parent / "config" / "monitoring"
BASE_CONFIG_FILE = "base.yaml"


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with override taking precedence.

    What: Recursively merges nested dictionaries
    Why: Environment-specific configs override base configs at any depth
    """
    result = deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result


def load_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load YAML file with error handling.
    
    CRITICAL: Returns None on any error to enable fallback behavior
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            logger.info(f"Loaded config from {file_path}")
            return data
    except FileNotFoundError:
        logger.warning(f"Config file not found: {file_path}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading {file_path}: {e}")
        return None


def load_monitoring_config(
    environment: Optional[str] = None,
    config_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Load monitoring configuration with environment-specific overrides.

    Fallback Behavior:
        1. Load base.yaml
        2. If env-specific file exists, merge it
        3. If any error occurs, use base.yaml only
        4. If base.yaml fails, return empty dict
    """
    if environment is None:
        environment = os.getenv('ENVIRONMENT', 'dev')

    if config_dir is None:
        config_dir = CONFIG_DIR

    logger.info(f"Loading monitoring config for environment: {environment}")

    # Load base configuration
    base_file = config_dir / BASE_CONFIG_FILE
    base_config = load_yaml_file(base_file)

    if base_config is None:
        logger.error(
            f"CRITICAL: Failed to load base config from {base_file}. "
            "Returning empty config."
        )
        return {}

    # Load environment-specific overrides
    env_file = config_dir / f"{environment}.yaml"
    env_config = load_yaml_file(env_file)

    if env_config is None:
        logger.warning(
            f"No environment-specific config for '{environment}'. "
            "Using base config only."
        )
        return base_config

    # Merge configs
    try:
        merged_config = deep_merge(base_config, env_config)
        logger.info(f"Successfully merged base config with {environment} overrides")
        return merged_config
    except Exception as e:
        logger.error(f"Error merging configs: {e}. Falling back to base config.")
        return base_config


def get_threshold(
    config: Dict[str, Any],
    path: str,
    default: Any = None
) -> Any:
    """
    Get threshold value from config using dot-notation path.
    
    Safe nested dictionary access with fallback.
    """
    keys = path.split('.')
    value = config

    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        logger.warning(f"Threshold path '{path}' not found. Using default: {default}")
        return default
