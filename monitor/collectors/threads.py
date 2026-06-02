"""
Threads collector - scrapes public Threads profiles via web.

Threads does not have an official public API. This collector attempts to
scrape public profile pages via HTTP requests + BeautifulSoup. Because
Threads heavily relies on client-side rendering, results may be limited.
"""

import hashlib
import logging
import random
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

THREADS_PROFILE_URL = "https://www.threads.net/@{handle}"


class ThreadsCollector:
    """
    Collects posts from Threads public profiles.

    NOTE: Threads does not provide a public API. This collector uses
    best-effort HTML scraping which may break if Threads changes its markup.
    As a fallback, it returns empty results gracefully.
    """

    def __init__(self, config: dict):
        """
        Initialize the Threads collector.

        Args:
            config: Source configuration with keys:
                - profiles: list of Threads handles (with or without @)
                - keywords: list of keywords to filter post text
                - min_delay: minimum seconds between requests (default 2)
                - max_delay: maximum seconds between requests (default 5)
        """
        self.config = config
        self.profiles = config.get("profiles", [])
        self.keywords = config.get("keywords", [])
        self.min_delay = config.get("min_delay", 2)
        self.max_delay = config.get("max_delay", 5)
        self.session = requests.Session()

    def _rotate_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def _delay(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _make_post_id(self, handle: str, post_id: str) -> str:
        return hashlib.md5(f"threads:{handle}:{post_id}".encode()).hexdigest()

    def _matches_keywords(self, text: str) -> bool:
        if not self.keywords:
            return True
        lower = text.lower()
        return any(kw.lower() in lower for kw in self.keywords)

    def _parse_html_posts(self, html: str, handle: str) -> List[Dict]:
        """
        Attempt to extract posts from Threads HTML.

        Threads uses client-side rendering (React), so static HTML often
        contains only minimal data. This method extracts whatever is available.
        """
        posts = []
        soup = BeautifulSoup(html, "lxml")

        # Try to find post content in script tags (JSON data)
        import json
        import re

        # Look for __NEXT_DATA__ or similar embedded JSON
        script_tags = soup.find_all("script", type="application/json")
        script_tags += soup.find_all("script", id="__NEXT_DATA__")

        for script in script_tags:
            try:
                data = json.loads(script.string or "")
                # Recursively search for thread/post text fields
                texts = self._extract_texts_from_json(data)
                for idx, text in enumerate(texts):
                    if self._matches_keywords(text):
                        posts.append({
                            "id": self._make_post_id(handle, f"json_{idx}"),
                            "source": "threads",
                            "title": text[:100].replace("\n", " "),
                            "company": handle,
                            "url": THREADS_PROFILE_URL.format(handle=handle),
                            "date": "",
                            "salary": "",
                            "location": "",
                            "skills": [],
                            "description": text,
                            "raw": text,
                        })
            except (json.JSONDecodeError, Exception):
                pass

        # Fallback: look for visible text blocks
        if not posts:
            for tag in soup.find_all(["p", "span", "div"], class_=re.compile(r"(post|thread|content|text)", re.I)):
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 30 and self._matches_keywords(text):
                    post_id = hashlib.md5(text[:50].encode()).hexdigest()[:8]
                    posts.append({
                        "id": self._make_post_id(handle, post_id),
                        "source": "threads",
                        "title": text[:100].replace("\n", " "),
                        "company": handle,
                        "url": THREADS_PROFILE_URL.format(handle=handle),
                        "date": "",
                        "salary": "",
                        "location": "",
                        "skills": [],
                        "description": text,
                        "raw": text,
                    })

        return posts

    def _extract_texts_from_json(self, obj, depth: int = 0) -> List[str]:
        """Recursively extract string values from nested JSON that look like post text."""
        if depth > 10:
            return []
        texts = []
        if isinstance(obj, str) and len(obj) > 30:
            texts.append(obj)
        elif isinstance(obj, dict):
            for val in obj.values():
                texts.extend(self._extract_texts_from_json(val, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                texts.extend(self._extract_texts_from_json(item, depth + 1))
        return texts

    def collect_profile(self, handle: str) -> List[Dict]:
        """
        Attempt to scrape posts from a single Threads profile.

        Args:
            handle: Threads profile handle (without @).

        Returns:
            List of post dicts (may be empty if scraping fails).
        """
        url = THREADS_PROFILE_URL.format(handle=handle)
        logger.info("Scraping Threads profile: @%s", handle)
        posts = []

        try:
            self._delay()
            resp = self.session.get(url, headers=self._rotate_headers(), timeout=20)
            resp.raise_for_status()
            posts = self._parse_html_posts(resp.text, handle)
            logger.info("Got %d matching posts from Threads @%s", len(posts), handle)

        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("Threads rate limited for @%s. Skipping.", handle)
            else:
                logger.error("Threads HTTP error for @%s: %s", handle, exc)
        except Exception as exc:
            logger.error("Threads scrape error for @%s: %s", handle, exc)

        return posts

    def collect(self) -> List[Dict]:
        """
        Collect posts from all configured Threads profiles.

        Returns:
            Deduplicated list of post dicts.
        """
        all_posts = []
        for handle in self.profiles:
            handle = handle.lstrip("@")
            profile_posts = self.collect_profile(handle)
            all_posts.extend(profile_posts)

        # Deduplicate by id
        seen = set()
        unique = []
        for post in all_posts:
            if post["id"] not in seen:
                seen.add(post["id"])
                unique.append(post)

        logger.info("Threads total unique posts: %d", len(unique))
        return unique
