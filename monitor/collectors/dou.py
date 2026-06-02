"""
DOU.ua collector - parses RSS feeds and company profile pages from jobs.dou.ua.
"""

import logging
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlencode

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DOUCollector:
    """Collects job postings from DOU.ua via RSS feeds and HTML scraping."""

    BASE_RSS_URL = "https://jobs.dou.ua/vacancies/feeds/"
    BASE_VACANCIES_URL = "https://jobs.dou.ua/vacancies/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    }

    def __init__(self, config: dict):
        """
        Initialize the DOU collector.

        Args:
            config: Source configuration dict with keys:
                - categories: list of job categories to filter
                - keywords: list of keywords to match
                - rss_base: optional override for RSS base URL
        """
        self.config = config
        self.categories = config.get("categories", [])
        self.keywords = config.get("keywords", [])
        self.rss_base = config.get("rss_base", self.BASE_RSS_URL)
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _make_post_id(self, url: str, title: str) -> str:
        """Generate a stable MD5 hash ID for deduplication."""
        raw = f"{url}:{title}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _matches_keywords(self, text: str) -> bool:
        """Return True if any keyword appears in text (case-insensitive)."""
        if not self.keywords:
            return True
        lower = text.lower()
        return any(kw.lower() in lower for kw in self.keywords)

    def _parse_rss_entry(self, entry) -> Optional[Dict]:
        """Parse a single feedparser entry into a post dict."""
        try:
            title = entry.get("title", "")
            url = entry.get("link", "")
            summary = entry.get("summary", "")
            published = entry.get("published", "")

            # Try to parse published date
            pub_date = None
            if entry.get("published_parsed"):
                pub_date = datetime(*entry.published_parsed[:6]).isoformat()
            elif published:
                pub_date = published

            # Extract company from title (DOU format: "Job Title @ Company")
            company = ""
            if " @ " in title:
                parts = title.split(" @ ", 1)
                title = parts[0].strip()
                company = parts[1].strip()

            # Try extracting salary and location from summary
            salary = ""
            location = ""
            skills = []
            if summary:
                soup = BeautifulSoup(summary, "lxml")
                text = soup.get_text(separator=" ")
                # Rough heuristic: look for salary patterns
                for line in text.split("\n"):
                    if "$" in line or "грн" in line.lower() or "usd" in line.lower():
                        salary = line.strip()
                    if any(city in line for city in ["Київ", "Львів", "Харків", "Одеса", "Remote", "Дистанційно"]):
                        location = line.strip()

            combined_text = f"{title} {company} {summary}"
            if not self._matches_keywords(combined_text):
                return None

            return {
                "id": self._make_post_id(url, title),
                "source": "dou",
                "title": title,
                "company": company,
                "url": url,
                "date": pub_date,
                "salary": salary,
                "location": location,
                "skills": skills,
                "description": summary,
                "raw": summary,
            }
        except Exception as exc:
            logger.warning("Failed to parse RSS entry: %s", exc)
            return None

    def collect_rss(self) -> List[Dict]:
        """
        Collect job postings from DOU RSS feeds.

        Returns:
            List of post dicts.
        """
        posts = []
        categories = self.categories if self.categories else [""]

        for category in categories:
            url = self.rss_base
            if category:
                url = f"{self.rss_base}?{urlencode({'category': category})}"
            logger.info("Fetching DOU RSS: %s", url)
            try:
                feed = feedparser.parse(url)
                if feed.bozo and feed.bozo_exception:
                    logger.warning("RSS parse warning for %s: %s", url, feed.bozo_exception)
                for entry in feed.entries:
                    post = self._parse_rss_entry(entry)
                    if post:
                        post["category"] = category
                        posts.append(post)
                logger.info("Collected %d posts from DOU RSS category '%s'", len(feed.entries), category)
            except Exception as exc:
                logger.error("Error fetching DOU RSS %s: %s", url, exc)
            time.sleep(1)

        return posts

    def scrape_company_page(self, company_url: str) -> List[Dict]:
        """
        Scrape job listings from a DOU company profile page.

        Args:
            company_url: Full URL to the company's DOU page.

        Returns:
            List of post dicts.
        """
        posts = []
        logger.info("Scraping DOU company page: %s", company_url)
        try:
            resp = self.session.get(company_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # DOU company vacancy list items
            vacancy_items = soup.select("li.l-vacancy") or soup.select("div.vacancy")
            for item in vacancy_items:
                try:
                    link_el = item.select_one("a.vt") or item.select_one("a")
                    if not link_el:
                        continue
                    title = link_el.get_text(strip=True)
                    url = link_el.get("href", "")
                    if url and not url.startswith("http"):
                        url = "https://jobs.dou.ua" + url

                    company_el = item.select_one("a.company") or item.select_one(".company")
                    company = company_el.get_text(strip=True) if company_el else ""

                    date_el = item.select_one(".date") or item.select_one("date")
                    date_str = date_el.get_text(strip=True) if date_el else ""

                    salary_el = item.select_one(".salary")
                    salary = salary_el.get_text(strip=True) if salary_el else ""

                    loc_el = item.select_one(".cities") or item.select_one(".location")
                    location = loc_el.get_text(strip=True) if loc_el else ""

                    combined = f"{title} {company}"
                    if not self._matches_keywords(combined):
                        continue

                    posts.append({
                        "id": self._make_post_id(url, title),
                        "source": "dou",
                        "title": title,
                        "company": company,
                        "url": url,
                        "date": date_str,
                        "salary": salary,
                        "location": location,
                        "skills": [],
                        "description": "",
                        "raw": item.get_text(separator=" ", strip=True),
                    })
                except Exception as exc:
                    logger.warning("Error parsing DOU vacancy item: %s", exc)
        except Exception as exc:
            logger.error("Error scraping DOU company page %s: %s", company_url, exc)

        return posts

    def collect(self, companies: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Run full DOU collection: RSS feeds + optional company pages.

        Args:
            companies: Optional list of company config dicts (must have 'dou' key).

        Returns:
            Deduplicated list of post dicts.
        """
        all_posts = self.collect_rss()

        if companies:
            for company in companies:
                dou_url = company.get("dou")
                if dou_url:
                    company_posts = self.scrape_company_page(dou_url)
                    all_posts.extend(company_posts)
                    time.sleep(2)

        # Deduplicate by id
        seen = set()
        unique = []
        for post in all_posts:
            if post["id"] not in seen:
                seen.add(post["id"])
                unique.append(post)

        logger.info("DOU total unique posts: %d", len(unique))
        return unique
