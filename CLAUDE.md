# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A personal daily news digest agent. Fetches RSS feeds, uses an LLM (Claude/OpenAI) to filter and classify articles based on user interests, then delivers a curated HTML email. All personalization lives in `config.yaml`.

## Running

```bash
# Activate venv first
source .venv/bin/activate

# Full run (fetch → LLM process → send email)
python main.py

# Debug: just fetch and print articles
python main.py --fetch-only

# Process but skip email delivery
python main.py --no-send

# Save HTML preview to file
python main.py --preview out.html

# Use alternate config
python main.py --config custom.yaml
```

## Setup

```bash
pip install -r requirements.txt
# Also needs: pip install python-dotenv
```

Secrets go in `.env` (loaded via `python-dotenv` in `main.py`):
- `ANTHROPIC_API_KEY` — Claude API key
- `SMTP_USERNAME` / `SMTP_PASSWORD` — Gmail App Password for sending
- `DIGEST_TO_EMAIL` — Recipient address

Config references these as `${VAR_NAME}` — resolved by `agent/config_loader.py`.

## Architecture

Pipeline: **Fetch → Dedup → Process (LLM) → Format → Deliver**

- `main.py` — Orchestrator, runs the pipeline end-to-end
- `agent/fetcher.py` — Parses RSS feeds via `feedparser`, deduplicates by URL
- `agent/state.py` — `SeenTracker` persists delivered URLs to `state/seen.json`, auto-prunes after 14 days
- `agent/processor.py` — Builds prompts from user profile + articles, calls LLM, parses JSON response with selections
- `agent/formatter.py` — Renders selected items into styled HTML email, grouped by action type
- `agent/deliverer.py` — Sends via SMTP (Gmail TLS on port 587)
- `agent/models.py` — `ContentItem` dataclass: the universal data structure all sources normalize into
- `agent/config_loader.py` — Loads YAML config with `${ENV_VAR}` substitution from `os.environ`

## Key Concepts

- **ContentItem** (`agent/models.py`): All sources produce these. After LLM processing, items get enriched with `action_type`, `relevance_score`, and `summary`.
- **Three action types**: `read_in_depth` (worth clicking), `check_it_out` (media/events), `fyi` (summary is enough)
- **LLM response format**: The processor expects JSON with `{"selections": [{url, action_type, relevance_score, summary}]}`. Parsing handles markdown fences and bare arrays.
- **Config-driven**: `config.yaml` holds user profile, feed URLs, digest limits, LLM settings, and delivery config. Code is the skeleton; config makes it personal.
