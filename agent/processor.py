"""Process fetched content with an LLM: filter, classify, summarize."""

from __future__ import annotations

import json
import logging
from typing import Any

from agent.models import ContentItem

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────

FILTER_SYSTEM_PROMPT = """\
You are a personal news curator. Your job is to read a list of content items \
(news articles, Hacker News stories/comments, and Reddit posts) and select \
the ones most relevant and interesting to the reader.

READER PROFILE:
{profile_block}

INSTRUCTIONS:
1. Read all the items below. Items come from different sources (e.g. nyt/*, \
hn/*, reddit/*). Treat them equally — judge by substance, not source. An \
insightful HN comment or Reddit discussion can be more valuable than a thin \
news article.
2. Select up to {max_total} items that this specific reader would find \
valuable. Skip generic/fluffy pieces.
3. Classify each selected item into exactly one action type:
   - "read_in_depth": Substantive article the reader should actually open \
and read. The summary alone won't do it justice.
   - "check_it_out": A movie, book, show, live performance, exhibition, or \
event the reader might want to experience. Include practical info \
(where to watch/find it, whether it's available now).
   - "fyi": The reader should know about this, but the summary is enough. \
No need to click through.
4. Write a concise summary for each (2-3 sentences). Match the reader's \
technical level. No fluff.
5. Assign a relevance score from 0 to 1 for ranking.

Respond ONLY with valid JSON — no markdown fences, no preamble. Use this schema:
{{
  "selections": [
    {{
      "url": "...",
      "action_type": "read_in_depth" | "check_it_out" | "fyi",
      "relevance_score": 0.0-1.0,
      "summary": "..."
    }}
  ]
}}
"""

ARTICLES_USER_PROMPT = """\
Here are today's items (articles and discussions):

{articles_block}

Select and summarize the most relevant ones for the reader.
"""


def build_profile_block(config: dict[str, Any]) -> str:
    """Format the user profile section of the prompt."""
    profile = config["profile"]
    lines = [
        f"Name: {profile['name']}",
        f"Location: {profile['location']}",
        f"Background: {profile['background'].strip()}",
        "Interests:",
    ]
    for interest in profile["interests"]:
        lines.append(f"  - {interest}")
    return "\n".join(lines)


def process_items(
    items: list[ContentItem],
    config: dict[str, Any],
) -> list[ContentItem]:
    """Filter, classify, and summarize items using the configured LLM.

    Returns the subset of items that were selected, with action_type,
    relevance_score, and summary populated.
    """
    if not items:
        logger.warning("No items to process")
        return []

    profile_block = build_profile_block(config)
    digest_cfg = config["digest"]
    max_total = (
        digest_cfg["max_items"]["read_in_depth"]
        + digest_cfg["max_items"]["check_it_out"]
        + digest_cfg["max_items"]["fyi"]
    )

    articles_block = "\n\n".join(
        f"--- Article {i+1} ---\n{item.to_prompt_str()}"
        for i, item in enumerate(items)
    )

    system_prompt = FILTER_SYSTEM_PROMPT.format(
        profile_block=profile_block,
        max_total=max_total,
    )
    user_prompt = ARTICLES_USER_PROMPT.format(articles_block=articles_block)

    llm_cfg = config["llm"]
    raw_response = _call_llm(system_prompt, user_prompt, llm_cfg)

    selections = _parse_selections(raw_response)

    url_to_item = {item.url: item for item in items}
    selected: list[ContentItem] = []

    for sel in selections:
        item = url_to_item.get(sel["url"])
        if item is None:
            logger.warning("LLM selected unknown URL: %s", sel["url"])
            continue
        item.action_type = sel["action_type"]
        item.relevance_score = sel.get("relevance_score", 0.5)
        item.summary = sel["summary"]
        selected.append(item)

    selected.sort(key=lambda x: x.relevance_score, reverse=True)
    logger.info("LLM selected %d items out of %d", len(selected), len(items))
    return selected


def _call_llm(system_prompt: str, user_prompt: str, llm_cfg: dict) -> str:
    """Call the configured LLM and return raw text response."""
    provider = llm_cfg.get("provider", "anthropic")

    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_prompt, llm_cfg)
    elif provider == "openai":
        return _call_openai(system_prompt, user_prompt, llm_cfg)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _call_anthropic(system_prompt: str, user_prompt: str, llm_cfg: dict) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=llm_cfg["api_key"])
    response = client.messages.create(
        model=llm_cfg.get("model", "claude-sonnet-4-20250514"),
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_openai(system_prompt: str, user_prompt: str, llm_cfg: dict) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=llm_cfg["api_key"])
    response = client.chat.completions.create(
        model=llm_cfg.get("model", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def _parse_selections(raw: str) -> list[dict]:
    """Parse JSON response from LLM, handling common formatting issues."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM JSON response:\n%s", text[:500])
        return []

    if isinstance(data, dict) and "selections" in data:
        return data["selections"]
    if isinstance(data, list):
        return data

    logger.error("Unexpected LLM response structure: %s", type(data))
    return []
