"""
Telegram collector - monitors Telegram channels for job postings using Telethon.
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from telethon import TelegramClient
    from telethon.errors import (
        FloodWaitError,
        ChannelPrivateError,
        UsernameNotOccupiedError,
    )
    from telethon.tl.types import Message
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.warning("Telethon not installed. Telegram collection disabled.")


JOB_KEYWORDS = [
    "вакансія", "вакансии", "hiring", "job opening", "шукаємо", "шукаем",
    "remote", "розробник", "developer", "engineer", "python", "javascript",
    "frontend", "backend", "fullstack", "devops", "qa", "тестувальник",
    "джуніор", "сеньор", "junior", "senior", "middle", "робота",
]


class TelegramCollector:
    """Collects job-related messages from Telegram channels using Telethon."""

    def __init__(self, config: dict):
        """
        Initialize the Telegram collector.

        Args:
            config: Source configuration with keys:
                - api_id: Telegram API ID
                - api_hash: Telegram API hash
                - channels: list of channel usernames (e.g. '@dou_ua')
                - session_file: path to store session (default 'telegram_session')
                - keywords: additional keywords to filter
                - lookback_hours: how many hours back to scan (default 24)
        """
        self.config = config
        self.api_id = config.get("api_id")
        self.api_hash = config.get("api_hash")
        self.channels = config.get("channels", [])
        self.session_file = config.get("session_file", "telegram_session")
        self.keywords = list(set(JOB_KEYWORDS + config.get("keywords", [])))
        self.lookback_hours = config.get("lookback_hours", 24)
        self.client: Optional["TelegramClient"] = None

    def _make_post_id(self, channel: str, message_id: int) -> str:
        raw = f"telegram:{channel}:{message_id}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _matches_keywords(self, text: str) -> bool:
        if not text:
            return False
        lower = text.lower()
        return any(kw.lower() in lower for kw in self.keywords)

    def _parse_message(self, message: "Message", channel: str) -> Optional[Dict]:
        """Parse a Telethon Message into a post dict."""
        try:
            if not message.text:
                return None
            if not self._matches_keywords(message.text):
                return None

            url = f"https://t.me/{channel.lstrip('@')}/{message.id}"
            date_str = message.date.isoformat() if message.date else ""

            return {
                "id": self._make_post_id(channel, message.id),
                "source": "telegram",
                "title": message.text[:100].replace("\n", " "),
                "company": "",
                "url": url,
                "date": date_str,
                "salary": "",
                "location": "",
                "skills": [],
                "description": message.text,
                "raw": message.text,
                "channel": channel,
                "message_id": message.id,
            }
        except Exception as exc:
            logger.warning("Error parsing Telegram message: %s", exc)
            return None

    async def _collect_channel(self, channel: str, lookback_dt: datetime) -> List[Dict]:
        """Collect messages from a single channel with exponential backoff."""
        posts = []
        retries = 0
        max_retries = 5

        while retries <= max_retries:
            try:
                logger.info("Collecting Telegram channel: %s", channel)
                async for message in self.client.iter_messages(
                    channel,
                    limit=200,
                    offset_date=None,
                    reverse=False,
                ):
                    if message.date and message.date.replace(tzinfo=timezone.utc) < lookback_dt:
                        break
                    post = self._parse_message(message, channel)
                    if post:
                        posts.append(post)
                logger.info("Got %d posts from %s", len(posts), channel)
                break

            except FloodWaitError as exc:
                wait = exc.seconds
                logger.warning("FloodWait on %s: sleeping %ds", channel, wait)
                await asyncio.sleep(wait)
                retries += 1

            except (ChannelPrivateError, UsernameNotOccupiedError) as exc:
                logger.error("Cannot access channel %s: %s", channel, exc)
                break

            except Exception as exc:
                wait = 2 ** retries
                logger.error("Error on channel %s (retry %d): %s", channel, retries, exc)
                await asyncio.sleep(wait)
                retries += 1

        return posts

    async def _run_async(self) -> List[Dict]:
        """Async entry point for collection."""
        if not TELETHON_AVAILABLE:
            logger.error("Telethon is not installed.")
            return []

        if not self.api_id or not self.api_hash:
            logger.error("Telegram API credentials not configured.")
            return []

        lookback_dt = datetime.now(tz=timezone.utc) - timedelta(hours=self.lookback_hours)
        all_posts = []

        async with TelegramClient(self.session_file, self.api_id, self.api_hash) as client:
            self.client = client
            for channel in self.channels:
                channel_posts = await self._collect_channel(channel, lookback_dt)
                all_posts.extend(channel_posts)
                await asyncio.sleep(2)  # polite delay between channels

        return all_posts

    def collect(self) -> List[Dict]:
        """
        Synchronously run the async Telegram collection.

        Returns:
            List of post dicts from all configured channels.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already inside an async context, schedule as coroutine
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._run_async())
                    return future.result()
            else:
                return loop.run_until_complete(self._run_async())
        except Exception as exc:
            logger.error("Telegram collection failed: %s", exc)
            return []
