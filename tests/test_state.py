from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.state import SeenTracker


class SeenTrackerTests(unittest.TestCase):
    def test_init_prunes_entries_older_than_seven_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "seen.json"
            now = datetime.now(timezone.utc)
            recent_ts = (now - timedelta(days=2)).isoformat()
            stale_ts = (now - timedelta(days=8)).isoformat()
            state_path.write_text(
                json.dumps(
                    {
                        "https://example.com/recent": recent_ts,
                        "https://example.com/stale": stale_ts,
                    }
                )
            )

            tracker = SeenTracker(path=state_path)

            self.assertTrue(tracker.is_seen("https://example.com/recent"))
            self.assertFalse(tracker.is_seen("https://example.com/stale"))
            persisted = json.loads(state_path.read_text())
            self.assertEqual(["https://example.com/recent"], sorted(persisted))


if __name__ == "__main__":
    unittest.main()
