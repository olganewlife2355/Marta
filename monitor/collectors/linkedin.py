"""
LinkedIn collector - scrapes public LinkedIn job listings.
"""

import hashlib
import logging
import random
import time
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlencode, quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
]

LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_JOB_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


class LinkedInCollector:
    """Scrapes public LinkedIn job pages without authentication."""

    def __init__(self, config: dict):
        """
        Initialize LinkedIn collector.

        Args:
            config: Source config with keys:
                - search_terms: list of search query strings
                - keywords: additional keywords to match in results
                - min_delay: minimum seconds between requests (default 3)
                - max_delay: maximum seconds between requests (default 6)
                - max_results_per_term: max jobs per search term (default 25)
        """
        self.config = config
        self.search_terms = config.get("search_terms", [])
        self.keywords = config.get("keywords", [])
        self.min_delay = config.get("min_delay", 3)
        self.max_delay = config.get("max_delay", 6)
        self.max_results = config.get("max_results_per_term", 25)
        self.session = requests.Session()

    def _rotate_headers(self) -> dict:
        """Return headers with a random User-Agent."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.linkedin.com/",
        }

    def _delay(self):
        """Sleep a random interval between requests."""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def _make_post_id(self, job_id: str) -> str:
        return hashlib.md5(f"linkedin:{job_id}".encode()).hexdigest()

    def _matches_keywords(self, text: str) -> bool:
        if not self.keywords:
            return True
        lower = text.lower()
        return any(kw.lower() in lower for kw in self.keywords)

    def _parse_job_card(self, card: BeautifulSoup) -> Optional[Dict]:
        """Parse a job card element from LinkedIn search results."""
        try:
            title_el = card.select_one("h3.base-search-card__title") or card.select_one("h3")
            company_el = card.select_one("h4.base-search-card__subtitle") or card.select_one("h4")
            location_el = card.select_one("span.job-search-card__location") or card.select_one(".job-search-card__location")
            date_el = card.select_one("time") or card.select_one(".job-search-card__listdate")
            link_el = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            location = location_el.get_text(strip=True) if location_el else ""
            date_str = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""
            url = link_el.get("href", "") if link_el else ""

            # Extract job ID from URL
            job_id = ""
            if url and "/jobs/view/" in url:
                parts = url.split("/jobs/view/")
                job_id = parts[1].split("/")[0].split("?")[0]

            if not title:
                return None

            combined = f"{title} {company} {location}"
            if not self._matches_keywords(combined):
                return None

            return {
                "id": self._make_post_id(job_id or url or title),
                "source": "linkedin",
                "title": title,
                "company": company,
                "url": url,
                "date": date_str,
                "salary": "",
                "location": location,
                "skills": [],
                "description": "",
                "raw": card.get_text(separator=" ", strip=True),
                "job_id": job_id,
            }
        except Exception as exc:
            logger.warning("Error parsing LinkedIn job card: %s", exc)
            return None

    def _fetch_job_detail(self, job_id: str) -> str:
        """Fetch full job description for a given job ID."""
        if not job_id:
            return ""
        url = LINKEDIN_JOB_DETAIL_URL.format(job_id=job_id)
        try:
            self._delay()
            resp = self.session.get(url, headers=self._rotate_headers(), timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            desc_el = soup.select_one(".show-more-less-html__markup") or soup.select_one(".description__text")
            if desc_el:
                return desc_el.get_text(separator="\n", strip=True)
        except Exception as exc:
            logger.warning("Error fetching LinkedIn job detail %s: %s", job_id, exc)
        return ""

    def search_jobs(self, search_term: str) -> List[Dict]:
        """
        Search LinkedIn for jobs matching a search term.

        Args:
            search_term: The search query string.

        Returns:
            List of post dicts.
        """
        posts = []
        params = {
            "keywords": search_term,
            "start": 0,
            "count": min(self.max_results, 25),
        }

        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{urlencode(params)}"
        logger.info("Searching LinkedIn: %s", search_term)

        try:
            self._delay()
            resp = self.session.get(url, headers=self._rotate_headers(), timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            cards = soup.select("li") or []
            for card in cards:
                post = self._parse_job_card(card)
                if post:
                    posts.append(post)

            logger.info("Found %d jobs for '%s'", len(posts), search_term)

        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("LinkedIn rate limited. Waiting 60s...")
                time.sleep(60)
            else:
                logger.error("LinkedIn HTTP error for '%s': %s", search_term, exc)
        except Exception as exc:
            logger.error("LinkedIn search error for '%s': %s", search_term, exc)

        return posts

    def collect(self) -> List[Dict]:
        """
        Collect jobs for all configured search terms.

        Returns:
            Deduplicated list of post dicts.
        """
        all_posts = []
        for term in self.search_terms:
            term_posts = self.search_jobs(term)
            all_posts.extend(term_posts)

        # Deduplicate by id
        seen = set()
        unique = []
        for post in all_posts:
            if post["id"] not in seen:
                seen.add(post["id"])
                unique.append(post)

        logger.info("LinkedIn total unique posts: %d", len(unique))
        return unique
