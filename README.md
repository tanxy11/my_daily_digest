# Daily Digest

A personal information agent that fetches news, filters by your interests, and delivers a curated digest to your inbox every morning.

The code is the skeleton. Your `config.yaml` is what makes it yours.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your secrets
cp .env.example .env
# Edit .env with your API key and email credentials

# 3. Edit config.yaml with your interests and feeds

# 4. Test fetching (no LLM, no email — just see what comes back)
source .env
python main.py --fetch-only

# 5. Run the full pipeline, save HTML locally (no email)
python3 main.py --no-send
# Open output/digest-YYYY-MM-DD.html in your browser

# 6. Run for real
python main.py
```

## Scheduling (Cron)

```bash
# Edit crontab
crontab -e

# Add this line (8am Pacific, adjust for your server's timezone):
0 15 * * * cd /path/to/daily-digest && source .env && python main.py >> logs/cron.log 2>&1
```

Note: `0 15 * * *` is 3pm UTC = 8am Pacific (during PDT). Adjust for PST or use a timezone-aware scheduler.

## Project Structure

```
daily-digest/
├── config.yaml          ← YOUR data: interests, sources, preferences
├── .env                 ← YOUR secrets: API keys, email credentials
├── main.py              ← Orchestrator (fetch → process → deliver)
├── agent/
│   ├── config.py        ← Config loader with env var substitution
│   ├── models.py        ← Shared data types (ContentItem, DigestItem)
│   ├── fetcher.py       ← Source fetchers (RSS, future: Twitter, etc.)
│   ├── processor.py     ← LLM filtering + digest generation
│   ├── delivery.py      ← Email sender
│   └── state.py         ← Seen-article tracking (dedup across runs)
├── state/
│   └── seen.json        ← Auto-generated: tracks delivered articles
├── output/
│   └── digest-*.html    ← Saved digests (for your records)
└── requirements.txt
```

## Adding Sources

### More RSS feeds
Just add entries to `sources.nyt.feeds` in config.yaml. Works for any RSS feed, not just NYT:

```yaml
sources:
  nyt:
    feeds:
      - name: Hacker News
        url: https://hnrss.org/frontpage
      - name: Stratechery
        url: https://stratechery.com/feed/
```

### Twitter / X (future)
Requires API access ($100/mo Basic tier). The fetcher interface is ready — implement `fetch_twitter()` in `agent/fetcher.py` returning `list[ContentItem]`.

## Maintenance

```bash
# Clean up seen-articles older than 30 days
python main.py --prune
```
