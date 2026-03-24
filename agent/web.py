"""Web publishing utilities — save dated digest pages and maintain the archive index."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


_SOURCE_DISPLAY_NAMES = {
    "nyt": "New York Times",
    "hn": "Hacker News",
    "reddit": "Reddit",
}

_NAV_BAR = (
    '<div style="background:#1a1a1a;padding:12px 28px;display:flex;gap:20px;">'
    '<a href="/" style="color:#aaa;text-decoration:none;font-size:14px;">&larr; Archive</a>'
    '<a href="/about.html" style="color:#aaa;text-decoration:none;font-size:14px;">About</a>'
    '</div>\n'
)


def save_web_digest(html: str, web_dir: Path, config: dict[str, Any],
                    config_path: Path | None = None) -> None:
    """Save today's digest, regenerate index + about pages, prune files older than 90 days."""
    web_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    page_html = _inject_nav(html)
    (web_dir / f"{today}.html").write_text(page_html, encoding="utf-8")

    _regenerate_index(web_dir, html)
    _generate_about_page(web_dir, config_path)
    _cleanup_old(web_dir)


# ── Nav injection ─────────────────────────────────────────────────────────────

def _inject_nav(html: str) -> str:
    return re.sub(r'(<body[^>]*>)', r'\1' + _NAV_BAR, html, count=1)


# ── Index page ────────────────────────────────────────────────────────────────

def _regenerate_index(web_dir: Path, latest_html: str) -> None:
    files = sorted(
        web_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html"),
        reverse=True,
    )

    archive_items = ""
    for i, f in enumerate(files):
        date_str = f.stem
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            label = d.strftime("%a, %b %-d")
        except ValueError:
            continue
        active = ' style="font-weight:700;color:#fff;"' if i == 0 else ""
        archive_items += (
            f'<li style="margin-bottom:8px;">'
            f'<a href="{date_str}.html"{active} '
            f'style="color:#aaa;text-decoration:none;font-size:14px;">{label}</a></li>\n'
        )

    body_match = re.search(r"<body[^>]*>(.*?)</body>", latest_html, re.DOTALL)
    body_content = body_match.group(1) if body_match else latest_html

    index_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Morning Digest</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5; display: flex; min-height: 100vh; }}
    .sidebar {{ width: 180px; background: #1a1a1a; padding: 24px 16px;
                flex-shrink: 0; position: sticky; top: 0; height: 100vh; overflow-y: auto; }}
    .sidebar h2 {{ color: #fff; font-size: 15px; font-weight: 700; margin-bottom: 16px; }}
    .sidebar ul {{ list-style: none; }}
    .sidebar a:hover {{ color: #fff !important; }}
    .sidebar-footer {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #333; }}
    .main {{ flex: 1; overflow: auto; }}
  </style>
</head>
<body>
  <div class="sidebar">
    <h2>Archive</h2>
    <ul>{archive_items}</ul>
    <div class="sidebar-footer">
      <a href="/about.html" style="color:#aaa;text-decoration:none;font-size:14px;">About</a>
    </div>
  </div>
  <div class="main">{body_content}</div>
</body>
</html>"""

    (web_dir / "index.html").write_text(index_html, encoding="utf-8")


# ── About page (config viewer) ────────────────────────────────────────────────

def _generate_about_page(web_dir: Path, config_path: Path | None) -> None:
    if config_path is None or not config_path.exists():
        return

    raw = config_path.read_text(encoding="utf-8")
    lines = raw.rstrip("\n").split("\n")
    code_rows = _build_code_rows(lines)

    about_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>config.yaml — Morning Digest</title>
</head>
<body style="margin:0;padding:0;background:#f6f8fa;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">

  <div style="background:#1a1a1a;padding:12px 28px;display:flex;gap:20px;">
    <a href="/" style="color:#aaa;text-decoration:none;font-size:14px;">&larr; Archive</a>
  </div>

  <div style="max-width:900px;margin:32px auto;padding:0 20px 64px;">

    <div style="margin-bottom:20px;">
      <div style="font-family:'SF Mono','Fira Code','JetBrains Mono',monospace;
                  font-size:22px;font-weight:700;color:#1a1a1a;margin-bottom:6px;">
        config.yaml
      </div>
      <div style="font-size:14px;color:#666;">
        The file that powers this digest — interests, sources, and LLM settings.
      </div>
    </div>

    <div style="border:1px solid #d0d7de;border-radius:6px;overflow:hidden;">

      <!-- file header -->
      <div style="background:#f6f8fa;border-bottom:1px solid #d0d7de;
                  padding:10px 16px;display:flex;align-items:center;gap:8px;">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="#57606a">
          <path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688l-.011-.013-2.914-2.914-.013-.011Z"/>
        </svg>
        <span style="font-family:'SF Mono','Fira Code',monospace;font-size:13px;
                     color:#1a1a1a;font-weight:600;">config.yaml</span>
        <span style="margin-left:auto;font-size:12px;color:#666;">{len(lines)} lines</span>
      </div>

      <!-- code body -->
      <div style="background:#0d1117;overflow-x:auto;">
        <table style="border-collapse:collapse;width:100%;
                      font-family:'SF Mono','Fira Code','JetBrains Mono',monospace;
                      font-size:13px;line-height:1.6;tab-size:2;">
          <tbody>
            {code_rows}
          </tbody>
        </table>
      </div>

    </div>
  </div>

</body>
</html>"""

    (web_dir / "about.html").write_text(about_html, encoding="utf-8")


# ── YAML syntax highlighter ───────────────────────────────────────────────────

def _build_code_rows(lines: list[str]) -> str:
    in_block = False
    block_indent = 0
    rows = []

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        indent = len(line) - len(stripped) if stripped else 0

        # End block scalar when we return to same/lower indent level
        if in_block:
            if stripped and indent <= block_indent:
                in_block = False
            else:
                rows.append(_row(lineno, _span(_esc(line), "#a5d6ff")))
                continue

        esc = _esc(line)
        s = esc.strip()

        if not s:
            rows.append(_row(lineno, ""))
        elif s.startswith("#"):
            rows.append(_row(lineno, _span(esc, "#8b949e", italic=True)))
        elif s.startswith("- "):
            rows.append(_row(lineno, _highlight_list_item(esc)))
        else:
            m = re.match(r"^(\s*)([\w_-]+)(\s*:\s?)(.*)$", esc)
            if m:
                ws, key, sep, val = m.groups()
                key_html = _span(key, "#79c0ff")
                val_s = val.strip()
                if val_s in (">", "|", ">-", "|-"):
                    val_html = _span(val, "#f2cc60")
                    in_block = True
                    block_indent = indent
                else:
                    val_html = _highlight_value(val)
                rows.append(_row(lineno, f"{ws}{key_html}{sep}{val_html}"))
            else:
                rows.append(_row(lineno, _span(esc, "#e6edf3")))

    return "\n".join(rows)


def _highlight_list_item(esc: str) -> str:
    m = re.match(r"^(\s*)(-\s+)(.*)$", esc)
    if not m:
        return _span(esc, "#e6edf3")
    ws, dash, rest = m.groups()
    dash_html = _span("-", "#ff7b72") + " "
    # check if rest is key: value
    km = re.match(r"^([\w_-]+)(\s*:\s?)(.*)$", rest)
    if km:
        k, sep, v = km.groups()
        rest_html = _span(k, "#79c0ff") + sep + _highlight_value(v)
    else:
        rest_html = _highlight_value(rest)
    return f"{ws}{dash_html}{rest_html}"


def _highlight_value(val: str) -> str:
    if not val:
        return ""
    parts = re.split(r"(\$\{[^}]+\})", val)
    out = ""
    for part in parts:
        if part.startswith("${"):
            out += _span(part, "#d2a8ff")
        elif part:
            out += _span(part, "#a5d6ff")
    return out


def _span(text: str, color: str, italic: bool = False) -> str:
    style = f"color:{color};"
    if italic:
        style += "font-style:italic;"
    return f'<span style="{style}">{text}</span>'


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _row(lineno: int, content: str) -> str:
    return (
        f'<tr style="line-height:1.6;">'
        f'<td style="width:50px;min-width:50px;padding:0 16px;text-align:right;'
        f'color:#484f58;user-select:none;border-right:1px solid #21262d;'
        f'font-size:12px;vertical-align:top;">{lineno}</td>'
        f'<td style="padding:0 16px;white-space:pre;color:#e6edf3;">{content}</td>'
        f'</tr>'
    )


# ── Cleanup ───────────────────────────────────────────────────────────────────

def _cleanup_old(web_dir: Path) -> None:
    cutoff = datetime.now() - timedelta(days=90)
    for f in web_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html"):
        try:
            d = datetime.strptime(f.stem, "%Y-%m-%d")
            if d < cutoff:
                f.unlink()
        except ValueError:
            pass
