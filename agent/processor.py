"""Process fetched content with an LLM: filter, classify, summarize."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent.models import ContentItem

logger = logging.getLogger(__name__)
_MAX_PARSE_ATTEMPTS = 2

# ── Prompt templates ──────────────────────────────────────────

FILTER_SYSTEM_PROMPT = """\
You are a personal news curator. Your job is to read a list of news articles \
and select the ones most relevant and interesting to the reader. This is a \
light morning briefing — the reader wants to know what's happening in their \
world, not do deep research.

READER PROFILE:
{profile_block}

INSTRUCTIONS:
1. Read all the articles below.
2. DEDUPLICATE: If multiple articles cover the same story or event, pick \
the single most informative one and skip the rest. Do not include the same \
story from different sources or angles.
3. SOURCE DIVERSITY: No single source (e.g. one subreddit) should account \
for more than ~30% of selections. Spread across the available sources.
4. Select up to {max_total} articles that this specific reader would find \
valuable. Skip generic/fluffy pieces.
5. Classify each selected article into exactly one action type:
   - "read_in_depth": Substantive article the reader should actually open \
and read. The summary alone won't do it justice.
   - "check_it_out": A movie, book, show, live performance, exhibition, or \
event the reader might genuinely want to experience. Include practical info \
(where to watch/find it, whether it's available now). ONLY use this category \
if the recommendation is genuinely compelling. If nothing qualifies, include \
zero items in this category — do not fill it with filler.
   - "fyi": The reader should know about this, but the summary is enough. \
No need to click through. Industry news, drama, and developments go here.
6. Write a concise summary for each (2-3 sentences). Match the reader's \
technical level. No fluff.
7. Assign a relevance score from 0 to 1 for ranking.

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
Here are today's articles:

{articles_block}

Select and summarize the most relevant ones for the reader.
"""

JSON_REPAIR_SYSTEM_PROMPT = """\
You repair malformed JSON produced by another model.

Return ONLY valid JSON matching this schema:
{
  "selections": [
    {
      "url": "...",
      "action_type": "read_in_depth" | "check_it_out" | "fyi",
      "relevance_score": 0.0-1.0,
      "summary": "..."
    }
  ]
}

Rules:
- Preserve complete items when possible.
- Drop incomplete or obviously corrupted trailing items instead of guessing.
- Do not add prose, markdown fences, or explanations.
"""

JSON_REPAIR_USER_PROMPT = """\
Repair this malformed JSON into valid JSON using the required schema.

Malformed response:
{raw_response}
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
    selections: list[dict[str, Any]] = []
    parsed_ok = False

    for attempt in range(1, _MAX_PARSE_ATTEMPTS + 1):
        raw_response = _call_llm(system_prompt, user_prompt, llm_cfg)
        selections, parsed_ok = _parse_selections(raw_response, llm_cfg)
        if parsed_ok:
            break
        if attempt < _MAX_PARSE_ATTEMPTS:
            logger.warning(
                "LLM returned malformed JSON on attempt %d/%d; retrying",
                attempt,
                _MAX_PARSE_ATTEMPTS,
            )

    if not parsed_ok:
        logger.error("Unable to recover a valid LLM selection payload")
        return []

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


def _parse_selections(
    raw: str,
    llm_cfg: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Parse JSON response from LLM.

    Returns a tuple of (selections, parsed_ok). An empty selection list can
    still be valid when the model intentionally returns zero picks.
    """
    text = _clean_json_text(raw)
    data = _load_json(text)

    if data is None:
        candidate = _extract_json_candidate(text)
        if candidate is not None and candidate != text:
            data = _load_json(candidate)

    if data is None and llm_cfg is not None:
        data = _repair_json_with_llm(text, llm_cfg)

    if data is None:
        logger.error("Failed to parse LLM JSON response:\n%s", text[:500])
        return [], False

    selections = _normalize_selections(data)
    if selections is None:
        return [], False
    return selections, True


def _clean_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _load_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_json_candidate(text: str) -> str | None:
    matches = re.findall(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return None


def _normalize_selections(data: Any) -> list[dict[str, Any]] | None:
    if isinstance(data, dict) and "selections" in data and isinstance(data["selections"], list):
        return data["selections"]
    if isinstance(data, list):
        return data

    logger.error("Unexpected LLM response structure: %s", type(data))
    return None


def _repair_json_with_llm(text: str, llm_cfg: dict[str, Any]) -> Any | None:
    logger.warning("Attempting LLM JSON repair after parse failure")
    repaired = _call_llm(
        JSON_REPAIR_SYSTEM_PROMPT,
        JSON_REPAIR_USER_PROMPT.format(raw_response=text[:12000]),
        llm_cfg,
    )
    repaired_text = _clean_json_text(repaired)
    repaired_data = _load_json(repaired_text)
    if repaired_data is None:
        logger.error("LLM JSON repair also failed:\n%s", repaired_text[:500])
    return repaired_data
