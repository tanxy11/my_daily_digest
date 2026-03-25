# Daily Digest

A personal daily news digest agent. It fetches RSS feeds, uses an LLM to pick the most relevant items for your interests, sends a styled HTML email, and can publish each digest to a small web archive.

The code is the skeleton. Your `config.yaml` is what makes it yours.

## What It Does

Pipeline:

`Fetch -> Dedup -> Process (LLM) -> Format -> Deliver + Publish`

Key behavior:
- Fetches from multiple RSS sources and deduplicates by URL
- Filters out previously delivered links using `state/seen.json`
- Uses Anthropic or OpenAI-compatible config settings to classify and summarize articles
- Groups picks into `read_in_depth`, `check_it_out`, and `fyi`
- Sends the digest by email
- Optionally saves a dated HTML page and regenerates a web archive index

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install python-dotenv
```

Create `.env` with the secrets you use:

```bash
ANTHROPIC_API_KEY=...
DIGEST_TO_EMAIL=you@example.com

# Preferred on VPS / cloud hosts
RESEND_API_KEY=...
RESEND_FROM_ADDRESS=Daily Digest <digest@yourdomain.com>

# Optional SMTP fallback
SMTP_USERNAME=...
SMTP_PASSWORD=...
```

Notes:
- If `RESEND_API_KEY` is present, email is sent through the Resend HTTPS API.
- If `RESEND_API_KEY` is missing, the app falls back to SMTP using `delivery.smtp` in `config.yaml`.
- On many VPS providers, outbound SMTP ports are blocked, so Resend is the safer default for production.

## Config

Edit `config.yaml` to define:
- your profile and interests
- RSS feeds
- digest size and writing style
- delivery settings
- LLM provider/model

Environment variables referenced as `${VAR_NAME}` inside `config.yaml` are resolved by [`agent/config_loader.py`](/Users/xinyutan/Documents/projects/my_daily_digest/agent/config_loader.py).

## Running

Activate the virtualenv first:

```bash
source .venv/bin/activate
```

Common commands:

```bash
# Fetch feeds and print unseen items
python main.py --fetch-only

# Process items but skip email sending
python main.py --no-send

# Save the rendered digest HTML to a local file
python main.py --preview out.html

# Full run: fetch, process, send email
python main.py

# Full run plus publish/update web archive
python main.py --web-dir /var/www/dd

# Use a different config file
python main.py --config custom.yaml
```

Behavior note:
- When `--web-dir` is provided, the web archive is published before email sending, so a temporary email failure does not prevent the site from updating.

## Deployment

This project currently runs on a VPS and publishes the archive at [dd.tanxy.net](https://dd.tanxy.net).

Current cron example:

```bash
30 14 * * * cd /root/my_daily_digest && .venv/bin/python main.py --web-dir /var/www/dd >> logs/cron.log 2>&1
```

Notes:
- The server shown above runs in UTC.
- `14:30 UTC` is `7:30 AM` Pacific during standard time.
- Web files are written to `/var/www/dd`.

## Project Structure

```text
my_daily_digest/
├── config.yaml
├── .env
├── main.py
├── agent/
│   ├── config_loader.py
│   ├── deliverer.py
│   ├── fetcher.py
│   ├── formatter.py
│   ├── models.py
│   ├── processor.py
│   ├── state.py
│   └── web.py
├── logs/
│   └── cron.log
├── state/
│   └── seen.json
└── requirements.txt
```

## Web Archive

When you run with `--web-dir`, the app:
- saves a dated page like `2026-03-25.html`
- regenerates `index.html` with the latest digest embedded and an archive sidebar
- regenerates `about.html` as a readable `config.yaml` viewer
- prunes old archive pages

## Delivery

Email delivery lives in [`agent/deliverer.py`](/Users/xinyutan/Documents/projects/my_daily_digest/agent/deliverer.py).

Current delivery order:
1. Prefer Resend if `RESEND_API_KEY` is set
2. Otherwise fall back to SMTP

Resend is recommended for server deployment because it uses HTTPS instead of SMTP ports.

## Adding Sources

Add more feeds in `config.yaml`:

```yaml
sources:
  blogs:
    type: rss
    feeds:
      - section: Stratechery
        url: "https://stratechery.com/feed/"
      - section: Hacker News
        url: "https://hnrss.org/frontpage"
```

## State Tracking

Delivered items are tracked in `state/seen.json`.

That means:
- already delivered links are skipped on future runs
- the digest is based on unseen content, not just the latest fetch

## Troubleshooting

- `No new items since last run`: the fetched URLs are already in `state/seen.json`
- email fails on a VPS with SMTP: use Resend instead of direct SMTP
- web archive not updating: run with `--web-dir /path/to/site`
- config placeholders not resolving: make sure the env vars exist in `.env`
