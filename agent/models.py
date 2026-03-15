"""Uniform content item that all sources normalize into."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContentItem:
    """A single piece of content from any source.

    Every fetcher must produce a list of these. The processing layer
    never sees source-specific formats.
    """

    title: str
    body: str  # plain text summary / snippet
    url: str
    source: str  # e.g. "nyt/Technology", "wsj", "x/@username"
    author: str = ""
    published: datetime | None = None
    tags: list[str] = field(default_factory=list)
    discussion_url: str = ""  # e.g. HN thread URL when different from article URL

    # Set by the processing layer, not by fetchers
    action_type: str = ""  # "read_in_depth", "check_it_out", "fyi"
    relevance_score: float = 0.0
    summary: str = ""

    @property
    def id(self) -> str:
        """Stable identifier for deduplication."""
        return self.url

    def to_prompt_str(self) -> str:
        """Compact representation for LLM context."""
        parts = [
            f"[{self.source}] {self.title}",
            f"  URL: {self.url}",
        ]
        if self.author:
            parts.append(f"  Author: {self.author}")
        if self.body:
            # Truncate body to ~300 chars to save tokens
            truncated = self.body[:300].rsplit(" ", 1)[0] + ("..." if len(self.body) > 300 else "")
            parts.append(f"  Snippet: {truncated}")
        return "\n".join(parts)
