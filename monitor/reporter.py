"""
Reporter - generates daily and weekly analytical reports as plain text and HTML.
"""

import logging
import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from jinja2 import Environment, BaseLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    logger.warning("Jinja2 not installed. HTML reports will use basic formatting.")


DAILY_TEXT_TEMPLATE = """\
==================================================
DAILY JOB MONITOR REPORT - {date}
==================================================

Total new posts today: {total}

By source:
{by_source}

By company (top 10):
{by_company}

Top keywords:
{top_keywords}

New posts:
{post_list}
==================================================
Generated at {generated_at}
"""

WEEKLY_TEXT_TEMPLATE = """\
==================================================
WEEKLY JOB MONITOR REPORT - {week_start} to {week_end}
==================================================

Total posts this week: {total}
Total posts previous week: {prev_total}
Change: {change:+d} ({change_pct:+.1f}%)

By source:
{by_source}

Most active companies:
{by_company}

Top keywords:
{top_keywords}

Daily breakdown:
{daily_breakdown}
==================================================
Generated at {generated_at}
"""

DAILY_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<title>Daily Job Report - {{ date }}</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }
  h1 { color: #0088cc; }
  h2 { color: #555; border-bottom: 1px solid #eee; padding-bottom: 5px; }
  .stat-box { display: inline-block; background: #f0f8ff; border-radius: 8px; padding: 15px 25px; margin: 5px; text-align: center; }
  .stat-number { font-size: 2em; font-weight: bold; color: #0088cc; }
  .stat-label { color: #777; font-size: 0.85em; }
  .post-card { border-left: 4px solid #0088cc; padding: 10px 15px; margin: 10px 0; background: #f9f9f9; border-radius: 4px; }
  .post-title { font-weight: bold; color: #0088cc; }
  .post-meta { color: #888; font-size: 0.85em; margin-top: 4px; }
  .source-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; background: #e0e0e0; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }
  th { background: #f0f8ff; color: #0088cc; }
  .footer { color: #aaa; font-size: 0.8em; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px; }
</style>
</head>
<body>
<h1>🔔 Daily Job Report</h1>
<p>{{ date }}</p>

<div class="stat-box">
  <div class="stat-number">{{ total }}</div>
  <div class="stat-label">New Posts</div>
</div>

<h2>By Source</h2>
<table>
  <tr><th>Source</th><th>Count</th></tr>
  {% for source, count in by_source.items() %}
  <tr><td>{{ source }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>

<h2>Top Companies</h2>
<table>
  <tr><th>Company</th><th>Posts</th></tr>
  {% for company, count in by_company.items() %}
  <tr><td>{{ company }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>

<h2>Top Keywords</h2>
<table>
  <tr><th>Keyword</th><th>Occurrences</th></tr>
  {% for kw, count in top_keywords.items() %}
  <tr><td>{{ kw }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>

<h2>New Posts ({{ posts|length }})</h2>
{% for post in posts %}
<div class="post-card">
  <div class="post-title">
    {% if post.url %}<a href="{{ post.url }}">{{ post.title }}</a>{% else %}{{ post.title }}{% endif %}
    <span class="source-badge">{{ post.source }}</span>
  </div>
  <div class="post-meta">
    {% if post.company %}🏢 {{ post.company }} &nbsp;{% endif %}
    {% if post.location %}📍 {{ post.location }} &nbsp;{% endif %}
    {% if post.salary %}💰 {{ post.salary }} &nbsp;{% endif %}
    {% if post.date %}📅 {{ post.date }}{% endif %}
  </div>
</div>
{% endfor %}

<div class="footer">Generated at {{ generated_at }}</div>
</body>
</html>
"""

WEEKLY_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<title>Weekly Job Report - {{ week_start }} to {{ week_end }}</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }
  h1 { color: #0088cc; }
  h2 { color: #555; border-bottom: 1px solid #eee; padding-bottom: 5px; }
  .stat-box { display: inline-block; background: #f0f8ff; border-radius: 8px; padding: 15px 25px; margin: 5px; text-align: center; }
  .stat-number { font-size: 2em; font-weight: bold; color: #0088cc; }
  .stat-label { color: #777; font-size: 0.85em; }
  .change-positive { color: #27ae60; }
  .change-negative { color: #e74c3c; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }
  th { background: #f0f8ff; color: #0088cc; }
  .footer { color: #aaa; font-size: 0.8em; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px; }
</style>
</head>
<body>
<h1>📊 Weekly Job Report</h1>
<p>{{ week_start }} — {{ week_end }}</p>

<div class="stat-box">
  <div class="stat-number">{{ total }}</div>
  <div class="stat-label">This Week</div>
</div>
<div class="stat-box">
  <div class="stat-number">{{ prev_total }}</div>
  <div class="stat-label">Previous Week</div>
</div>
<div class="stat-box">
  <div class="stat-number {{ 'change-positive' if change >= 0 else 'change-negative' }}">{{ '%+d' % change }}</div>
  <div class="stat-label">Change ({{ '%+.1f' % change_pct }}%)</div>
</div>

<h2>By Source</h2>
<table>
  <tr><th>Source</th><th>Count</th></tr>
  {% for source, count in by_source.items() %}
  <tr><td>{{ source }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>

<h2>Most Active Companies</h2>
<table>
  <tr><th>Company</th><th>Posts</th></tr>
  {% for company, count in by_company.items() %}
  <tr><td>{{ company }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>

<h2>Top Keywords</h2>
<table>
  <tr><th>Keyword</th><th>Occurrences</th></tr>
  {% for kw, count in top_keywords.items() %}
  <tr><td>{{ kw }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>

<h2>Daily Breakdown</h2>
<table>
  <tr><th>Date</th><th>Posts</th></tr>
  {% for day, count in daily_breakdown.items() %}
  <tr><td>{{ day }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>

<div class="footer">Generated at {{ generated_at }}</div>
</body>
</html>
"""


def _extract_keywords(posts: List[Dict], top_n: int = 10) -> Dict[str, int]:
    """Extract and count significant words from post titles/descriptions."""
    STOP_WORDS = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for",
        "of", "with", "is", "are", "we", "you", "our", "і", "та", "в",
        "на", "до", "з", "за", "по", "що", "як", "це", "не", "be", "will",
    }
    word_counts: Counter = Counter()
    for post in posts:
        text = f"{post.get('title', '')} {post.get('description', '')}"
        for word in text.lower().split():
            word = word.strip(".,!?;:\"'()")
            if len(word) >= 4 and word not in STOP_WORDS:
                word_counts[word] += 1
    return dict(word_counts.most_common(top_n))


class Reporter:
    """Generates daily and weekly job monitoring reports."""

    def __init__(self, storage, config: dict):
        """
        Initialize the reporter.

        Args:
            storage: Storage instance for querying posts.
            config: Reports configuration dict.
        """
        self.storage = storage
        self.config = config
        self.output_dir = config.get("output_dir", "data/reports")
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_daily_data(self) -> Dict:
        """Collect data for daily report (last 24 hours)."""
        since = datetime.utcnow() - timedelta(hours=24)
        posts = self.storage.get_posts_since(since)

        by_source: Counter = Counter()
        by_company: Counter = Counter()
        for post in posts:
            by_source[post.get("source", "unknown")] += 1
            if post.get("company"):
                by_company[post["company"]] += 1

        return {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "total": len(posts),
            "by_source": dict(by_source.most_common()),
            "by_company": dict(by_company.most_common(10)),
            "top_keywords": _extract_keywords(posts),
            "posts": posts,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

    def _get_weekly_data(self) -> Dict:
        """Collect data for weekly report."""
        now = datetime.utcnow()
        week_start = now - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        posts = self.storage.get_posts_since(week_start)
        prev_posts = self.storage.get_posts_since(prev_week_start)
        # prev_posts includes this week; filter to only previous week
        prev_posts = [
            p for p in prev_posts
            if p.get("created_at", "") < week_start.isoformat()
        ]

        by_source: Counter = Counter()
        by_company: Counter = Counter()
        daily: Counter = Counter()

        for post in posts:
            by_source[post.get("source", "unknown")] += 1
            if post.get("company"):
                by_company[post["company"]] += 1
            day = (post.get("created_at") or "")[:10]
            if day:
                daily[day] += 1

        total = len(posts)
        prev_total = len(prev_posts)
        change = total - prev_total
        change_pct = ((change / prev_total) * 100) if prev_total else 0.0

        return {
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": now.strftime("%Y-%m-%d"),
            "total": total,
            "prev_total": prev_total,
            "change": change,
            "change_pct": change_pct,
            "by_source": dict(by_source.most_common()),
            "by_company": dict(by_company.most_common(10)),
            "top_keywords": _extract_keywords(posts),
            "daily_breakdown": dict(sorted(daily.items())),
            "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        }

    def generate_daily_report(self) -> str:
        """
        Generate a plain text daily report.

        Returns:
            Report as a plain text string.
        """
        data = self._get_daily_data()

        by_source_str = "\n".join(f"  {s}: {c}" for s, c in data["by_source"].items()) or "  (none)"
        by_company_str = "\n".join(f"  {c}: {n}" for c, n in data["by_company"].items()) or "  (none)"
        top_kw_str = "\n".join(f"  {k}: {v}" for k, v in data["top_keywords"].items()) or "  (none)"
        post_lines = []
        for post in data["posts"][:20]:
            post_lines.append(f"  [{post.get('source', '?')}] {post.get('title', '')} - {post.get('company', '')}")
            if post.get("url"):
                post_lines.append(f"       {post['url']}")
        post_list_str = "\n".join(post_lines) if post_lines else "  (none)"

        return DAILY_TEXT_TEMPLATE.format(
            date=data["date"],
            total=data["total"],
            by_source=by_source_str,
            by_company=by_company_str,
            top_keywords=top_kw_str,
            post_list=post_list_str,
            generated_at=data["generated_at"],
        )

    def generate_daily_report_html(self) -> str:
        """
        Generate an HTML daily report.

        Returns:
            Report as an HTML string.
        """
        data = self._get_daily_data()
        if JINJA2_AVAILABLE:
            env = Environment(loader=BaseLoader())
            tmpl = env.from_string(DAILY_HTML_TEMPLATE)
            return tmpl.render(**data)
        # Fallback: basic HTML
        text = self.generate_daily_report()
        return f"<pre>{text}</pre>"

    def generate_weekly_report(self) -> str:
        """
        Generate a plain text weekly report.

        Returns:
            Report as a plain text string.
        """
        data = self._get_weekly_data()

        by_source_str = "\n".join(f"  {s}: {c}" for s, c in data["by_source"].items()) or "  (none)"
        by_company_str = "\n".join(f"  {c}: {n}" for c, n in data["by_company"].items()) or "  (none)"
        top_kw_str = "\n".join(f"  {k}: {v}" for k, v in data["top_keywords"].items()) or "  (none)"
        daily_str = "\n".join(f"  {d}: {c}" for d, c in data["daily_breakdown"].items()) or "  (none)"

        return WEEKLY_TEXT_TEMPLATE.format(
            week_start=data["week_start"],
            week_end=data["week_end"],
            total=data["total"],
            prev_total=data["prev_total"],
            change=data["change"],
            change_pct=data["change_pct"],
            by_source=by_source_str,
            by_company=by_company_str,
            top_keywords=top_kw_str,
            daily_breakdown=daily_str,
            generated_at=data["generated_at"],
        )

    def generate_weekly_report_html(self) -> str:
        """
        Generate an HTML weekly report.

        Returns:
            Report as an HTML string.
        """
        data = self._get_weekly_data()
        if JINJA2_AVAILABLE:
            env = Environment(loader=BaseLoader())
            tmpl = env.from_string(WEEKLY_HTML_TEMPLATE)
            return tmpl.render(**data)
        text = self.generate_weekly_report()
        return f"<pre>{text}</pre>"

    def save_report(self, content: str, fmt: str = "html", report_type: str = "daily") -> str:
        """
        Save a report to disk.

        Args:
            content: Report content string.
            fmt: 'html' or 'text'.
            report_type: 'daily' or 'weekly'.

        Returns:
            Path to the saved file.
        """
        ext = "html" if fmt == "html" else "txt"
        filename = f"{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{ext}"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)
        logger.info("Report saved to %s", filepath)
        return filepath

    def run_daily(self) -> str:
        """Generate, save, and return the daily report."""
        text = self.generate_daily_report()
        html = self.generate_daily_report_html()
        self.save_report(text, "text", "daily")
        path = self.save_report(html, "html", "daily")
        try:
            self.storage.save_report("daily", html, "html", filepath=path)
            self.storage.save_report("daily", text, "text")
        except Exception as exc:
            logger.warning("Could not save report to DB: %s", exc)
        return text

    def run_weekly(self) -> str:
        """Generate, save, and return the weekly report."""
        text = self.generate_weekly_report()
        html = self.generate_weekly_report_html()
        self.save_report(text, "text", "weekly")
        path = self.save_report(html, "html", "weekly")
        try:
            self.storage.save_report("weekly", html, "html", filepath=path)
            self.storage.save_report("weekly", text, "text")
        except Exception as exc:
            logger.warning("Could not save report to DB: %s", exc)
        return text
