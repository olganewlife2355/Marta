"""
Notifier - sends Telegram bot and email notifications for new job postings.
"""

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import telegram
    from telegram import Bot
    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram notifications disabled.")


SOURCE_EMOJI = {
    "dou": "🟠",
    "telegram": "✈️",
    "linkedin": "💼",
    "instagram": "📸",
    "threads": "🧵",
}


def _format_post_telegram(post: Dict) -> str:
    """Format a single post as a Telegram markdown message."""
    source = post.get("source", "")
    emoji = SOURCE_EMOJI.get(source, "📌")
    title = post.get("title", "No title")
    company = post.get("company", "")
    url = post.get("url", "")
    location = post.get("location", "")
    salary = post.get("salary", "")
    date = post.get("date", "")

    lines = [f"{emoji} *{title}*"]
    if company:
        lines.append(f"🏢 {company}")
    if location:
        lines.append(f"📍 {location}")
    if salary:
        lines.append(f"💰 {salary}")
    if date:
        lines.append(f"📅 {date}")
    if url:
        lines.append(f"🔗 [Переглянути]({url})")

    return "\n".join(lines)


def _format_post_html(post: Dict) -> str:
    """Format a single post as an HTML snippet for email."""
    source = post.get("source", "")
    emoji = SOURCE_EMOJI.get(source, "📌")
    title = post.get("title", "No title")
    company = post.get("company", "")
    url = post.get("url", "")
    location = post.get("location", "")
    salary = post.get("salary", "")
    date = post.get("date", "")

    parts = [f'<div style="border-left:3px solid #0088cc;padding:8px;margin:8px 0;">']
    title_str = f'<a href="{url}">{title}</a>' if url else title
    parts.append(f'<h3 style="margin:0">{emoji} {title_str}</h3>')
    if company:
        parts.append(f'<p style="margin:2px 0">🏢 <strong>{company}</strong></p>')
    if location:
        parts.append(f'<p style="margin:2px 0">📍 {location}</p>')
    if salary:
        parts.append(f'<p style="margin:2px 0">💰 {salary}</p>')
    if date:
        parts.append(f'<p style="margin:2px 0;color:#888">📅 {date}</p>')
    parts.append("</div>")
    return "\n".join(parts)


class Notifier:
    """Sends job post notifications via Telegram and/or email."""

    def __init__(self, config: dict):
        """
        Initialize the notifier.

        Args:
            config: Notifications configuration dict with 'telegram' and 'email' sub-dicts.
        """
        self.config = config
        self.tg_config = config.get("telegram", {})
        self.email_config = config.get("email", {})

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    async def _send_telegram_async(self, posts: List[Dict]):
        """Send batched Telegram notifications (async)."""
        bot_token = self.tg_config.get("bot_token")
        chat_id = self.tg_config.get("chat_id")
        batch_size = self.tg_config.get("batch_size", 10)

        if not bot_token or not chat_id:
            logger.error("Telegram bot_token or chat_id not configured.")
            return

        bot = Bot(token=bot_token)

        # Send header
        if posts:
            header = f"🔔 *Нові вакансії* ({len(posts)} знайдено)\n" + "─" * 30
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=header,
                    parse_mode="Markdown",
                )
            except Exception as exc:
                logger.warning("Failed to send Telegram header: %s", exc)

        # Send in batches
        for i in range(0, len(posts), batch_size):
            batch = posts[i:i + batch_size]
            for post in batch:
                try:
                    text = _format_post_telegram(post)
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                    )
                    time.sleep(0.5)  # Avoid Telegram rate limits
                except Exception as exc:
                    logger.error("Failed to send Telegram post %s: %s", post.get("id"), exc)

            # Pause between batches
            if i + batch_size < len(posts):
                time.sleep(2)

    def send_telegram(self, posts: List[Dict]):
        """
        Send Telegram notifications for a list of posts.

        Args:
            posts: List of post dicts to notify about.
        """
        if not TELEGRAM_BOT_AVAILABLE:
            logger.error("python-telegram-bot is not installed.")
            return
        if not self.tg_config.get("enabled", False):
            logger.info("Telegram notifications disabled.")
            return
        if not posts:
            logger.info("No posts to notify via Telegram.")
            return

        import asyncio
        try:
            asyncio.run(self._send_telegram_async(posts))
            logger.info("Sent Telegram notifications for %d posts", len(posts))
        except Exception as exc:
            logger.error("Telegram notification error: %s", exc)

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    def send_email(self, subject: str, html_body: str, text_body: Optional[str] = None):
        """
        Send an email notification.

        Args:
            subject: Email subject line.
            html_body: HTML content of the email.
            text_body: Optional plain text fallback.
        """
        if not self.email_config.get("enabled", False):
            logger.info("Email notifications disabled.")
            return

        smtp_host = self.email_config.get("smtp_host", "smtp.gmail.com")
        smtp_port = self.email_config.get("smtp_port", 587)
        username = self.email_config.get("username")
        password = self.email_config.get("password")
        recipients = self.email_config.get("recipients", [])

        if not username or not password or not recipients:
            logger.error("Email credentials or recipients not configured.")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = username
        msg["To"] = ", ".join(recipients)

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(username, password)
                server.sendmail(username, recipients, msg.as_string())
            logger.info("Email sent to %s: %s", recipients, subject)
        except smtplib.SMTPException as exc:
            logger.error("SMTP error: %s", exc)
        except Exception as exc:
            logger.error("Email send error: %s", exc)

    def notify_posts(self, posts: List[Dict]):
        """
        Send all enabled notifications for new posts.

        Args:
            posts: List of new post dicts.
        """
        if not posts:
            return

        self.send_telegram(posts)

        if self.email_config.get("enabled", False):
            html_parts = [
                "<html><body>",
                f"<h2>🔔 Нові вакансії ({len(posts)})</h2>",
            ]
            for post in posts:
                html_parts.append(_format_post_html(post))
            html_parts.append("</body></html>")
            html_body = "\n".join(html_parts)

            text_lines = [f"Нові вакансії ({len(posts)}):", ""]
            for post in posts:
                text_lines.append(f"- {post.get('title', '')} @ {post.get('company', '')}")
                if post.get("url"):
                    text_lines.append(f"  {post['url']}")
                text_lines.append("")
            text_body = "\n".join(text_lines)

            self.send_email(
                subject=f"[Job Monitor] {len(posts)} нових вакансій",
                html_body=html_body,
                text_body=text_body,
            )
