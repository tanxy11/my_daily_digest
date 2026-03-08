"""Load and resolve config.yaml with environment variable substitution."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load YAML config and substitute ${ENV_VAR} references."""
    raw = Path(path).read_text()
    resolved = _resolve_env_vars(raw)
    return yaml.safe_load(resolved)


def _resolve_env_vars(text: str) -> str:
    """Replace ${VAR_NAME} with os.environ[VAR_NAME].

    Leaves the placeholder as-is if the env var is not set,
    so you get a clear error downstream rather than a silent empty string.
    """
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return re.sub(r"\$\{(\w+)\}", replacer, text)
