"""Simple state management: track which articles have been sent."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(__file__).parent.parent / "state" / "seen.json"


class SeenTracker:
    """Track URLs already included in a digest. Prunes old entries on save."""

    def __init__(self, path: Path = DEFAULT_STATE_PATH, max_age_days: int = 14):
        self.path = path
        self.max_age_days = max_age_days
        self._seen: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._seen = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self._seen = {}

    def is_seen(self, url: str) -> bool:
        return url in self._seen

    def mark_seen(self, urls: list[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for url in urls:
            self._seen[url] = now
        self._prune()
        self._save()

    def _prune(self) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - (self.max_age_days * 86400)
        self._seen = {
            url: ts for url, ts in self._seen.items()
            if _safe_timestamp(ts) >= cutoff
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._seen, indent=2))


def _safe_timestamp(iso_str: str) -> float:
    try:
        return datetime.fromisoformat(iso_str).timestamp()
    except ValueError:
        return 0.0
