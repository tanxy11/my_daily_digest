"""Load and validate config, substituting environment variables."""

import os
import re
from pathlib import Path
from typing import Any

import yaml


def _substitute_env_vars(obj: Any) -> Any:
    """Recursively replace ${VAR_NAME} with os.environ[VAR_NAME]."""
    if isinstance(obj, str):
        def _replace(match: re.Match) -> str:
            var = match.group(1)
            val = os.environ.get(var)
            if val is None:
                raise EnvironmentError(f"Missing environment variable: {var}")
            return val
        return re.sub(r"\$\{(\w+)\}", _replace, obj)
    elif isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    return obj


def load_config(path: str | Path = "config.yaml") -> dict:
    """Load config from YAML, substituting ${ENV_VAR} references."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    return _substitute_env_vars(raw)
