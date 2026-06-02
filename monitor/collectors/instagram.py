"""
Instagram collector - fetches posts from company profiles using Instaloader.
"""

import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False
    logger.warning("Instaloader not installed. Instagram collection disabled.")


class InstagramCollector:
    """Collects job-related posts from Instagram company profiles using Instaloader."""

    def __init__(self, config: dict):
        """
        Initialize the Instagram collector.

        Args:
            config: Source configuration with keys:
                - profiles: list of Instagram profile handles (without @)
                - hashtags: list of hashtags to filter posts
                - keywords: list of keywords to match in captions
                - max_posts: maximum posts to fetch per profile (default 20)
                - username: optional Instagram username for authenticated access
                - password: optional Instagram password
        """
        self.config = config
        self.profiles = config.get("profiles", [])
        self.hashtags = [t.lstrip("#").lower() for t in config.get("hashtags", [])]
        self.keywords = config.get("keywords", [])
        self.max_posts = config.get("max_posts", 20)
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self._loader: Optional["instaloader.Instaloader"] = None

    def _get_loader(self) -> "instaloader.Instaloader":
        """Return a configured Instaloader instance."""
        if self._loader is None:
            self._loader = instaloader.Instaloader(
                download_pictures=False,
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                quiet=True,
            )
            if self.username and self.password:
                try:
                    self._loader.login(self.username, self.password)
                    logger.info("Logged in to Instagram as %s", self.username)
                except Exception as exc:
                    logger.warning("Instagram login failed: %s", exc)
        return self._loader

    def _make_post_id(self, shortcode: str) -> str:
        return hashlib.md5(f"instagram:{shortcode}".encode()).hexdigest()

    def _matches_filters(self, caption: str) -> bool:
        """Return True if caption matches keywords or hashtags."""
        lower = caption.lower()
        if self.keywords and any(kw.lower() in lower for kw in self.keywords):
            return True
        if self.hashtags and any(f"#{tag}" in lower for tag in self.hashtags):
            return True
        # If no filters defined, accept all
        if not self.keywords and not self.hashtags:
            return True
        return False

    def _parse_post(self, post: "instaloader.Post", profile_handle: str) -> Optional[Dict]:
        """Parse an Instaloader Post object into a post dict."""
        try:
            caption = post.caption or ""
            if not self._matches_filters(caption):
                return None

            date_str = post.date_utc.isoformat() if post.date_utc else ""
            url = f"https://www.instagram.com/p/{post.shortcode}/"

            return {
                "id": self._make_post_id(post.shortcode),
                "source": "instagram",
                "title": caption[:100].replace("\n", " "),
                "company": profile_handle,
                "url": url,
                "date": date_str,
                "salary": "",
                "location": post.location.name if post.location else "",
                "skills": [],
                "description": caption,
                "raw": caption,
                "shortcode": post.shortcode,
                "likes": post.likes,
            }
        except Exception as exc:
            logger.warning("Error parsing Instagram post: %s", exc)
            return None

    def collect_profile(self, handle: str) -> List[Dict]:
        """
        Collect posts from a single Instagram profile.

        Args:
            handle: Instagram username (without @).

        Returns:
            List of post dicts.
        """
        if not INSTALOADER_AVAILABLE:
            logger.error("Instaloader is not installed.")
            return []

        posts = []
        loader = self._get_loader()

        try:
            profile = instaloader.Profile.from_username(loader.context, handle)
            logger.info("Collecting Instagram profile: @%s (%d posts)", handle, profile.mediacount)

            count = 0
            for post in profile.get_posts():
                if count >= self.max_posts:
                    break
                parsed = self._parse_post(post, handle)
                if parsed:
                    posts.append(parsed)
                count += 1

            logger.info("Got %d matching posts from @%s", len(posts), handle)

        except Exception as exc:
            logger.error("Error collecting Instagram profile @%s: %s", handle, exc)

        return posts

    def collect(self) -> List[Dict]:
        """
        Collect posts from all configured Instagram profiles.

        Returns:
            Deduplicated list of post dicts.
        """
        if not INSTALOADER_AVAILABLE:
            logger.error("Instaloader is not installed. Skipping Instagram collection.")
            return []

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

        logger.info("Instagram total unique posts: %d", len(unique))
        return unique
