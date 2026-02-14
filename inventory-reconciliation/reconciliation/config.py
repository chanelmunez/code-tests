"""Configuration loader for normalization rules.

Loads rules from a YAML config file, with sensible defaults so that
existing behavior is preserved when no config is provided.
"""

import copy
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "sku": {
        "pattern": r"^SKU-?(\d+)$",
        "format": "SKU-{:03d}",
        "case": "upper",
    },
    "quantity": {
        "allow_fractional": False,
        "allow_negative": False,
    },
    "date": {
        "formats": ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"],
        "output_format": "%Y-%m-%d",
    },
    "name": {
        "strip_whitespace": True,
        "unicode_normalize": "NFKC",
    },
    "location": {
        "title_case": True,
        "unicode_normalize": "NFKC",
    },
    "priority": {
        "high_threshold_pct": 10,
        "medium_threshold_pct": 5,
    },
}


def load_config(path: str | Path | None = None) -> dict:
    """Load normalization config from a YAML file, merged with defaults.

    Args:
        path: Path to a YAML config file. If None, returns defaults.

    Returns:
        Config dict with all keys populated (user overrides merged on top of defaults).
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path is not None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
        _deep_merge(config, user_config)
    return config


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base in-place, recursing into nested dicts."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
