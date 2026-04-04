from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.models import ContentItem
from agent import processor


class ProcessorTests(unittest.TestCase):
    def test_parse_selections_handles_fenced_json(self) -> None:
        raw = """```json
        {
          "selections": [
            {
              "url": "https://example.com/article",
              "action_type": "fyi",
              "relevance_score": 0.7,
              "summary": "Short summary."
            }
          ]
        }
        ```"""

        selections, parsed_ok = processor._parse_selections(raw)

        self.assertTrue(parsed_ok)
        self.assertEqual(1, len(selections))
        self.assertEqual("https://example.com/article", selections[0]["url"])

    def test_process_items_retries_after_malformed_json(self) -> None:
        item = ContentItem(
            title="Example",
            body="Example body",
            url="https://example.com/article",
            source="test/source",
        )
        config = {
            "profile": {
                "name": "Xinyu",
                "location": "Santa Clara",
                "background": "Engineer",
                "interests": ["AI"],
            },
            "digest": {
                "max_items": {
                    "read_in_depth": 1,
                    "check_it_out": 1,
                    "fyi": 1,
                },
            },
            "llm": {
                "provider": "anthropic",
                "api_key": "test-key",
            },
        }
        malformed = '{"selections":[{"url":"https://example.com/article","action_type":"fyi","summary":"oops}'
        valid = (
            '{"selections":[{"url":"https://example.com/article",'
            '"action_type":"fyi","relevance_score":0.8,"summary":"Recovered."}]}'
        )

        with patch("agent.processor._call_llm", side_effect=[malformed, valid]) as mock_call:
            selected = processor.process_items([item], config)

        self.assertEqual(2, mock_call.call_count)
        self.assertEqual(1, len(selected))
        self.assertEqual("Recovered.", selected[0].summary)
        self.assertEqual("fyi", selected[0].action_type)


if __name__ == "__main__":
    unittest.main()
