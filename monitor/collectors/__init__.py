"""Collectors package - scrapers for each social media source."""

from .dou import DOUCollector
from .telegram_collector import TelegramCollector
from .linkedin import LinkedInCollector
from .instagram import InstagramCollector
from .threads import ThreadsCollector

__all__ = [
    "DOUCollector",
    "TelegramCollector",
    "LinkedInCollector",
    "InstagramCollector",
    "ThreadsCollector",
]
