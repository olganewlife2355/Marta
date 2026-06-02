"""
Configuration management - loads settings from config.yaml.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "database": {
        "path": "data/jobs.db",
    },
    "keywords": [],
    "companies": [],
    "sources": {
        "dou": {"enabled": True, "categories": [], "rss_base": "https://jobs.dou.ua/vacancies/feeds/"},
        "telegram": {"enabled": False, "channels": []},
        "linkedin": {"enabled": True, "search_terms": []},
        "instagram": {"enabled": False, "profiles": []},
        "threads": {"enabled": False, "profiles": []},
    },
    "notifications": {
        "telegram": {"enabled": False, "batch_size": 10},
        "email": {"enabled": False, "smtp_host": "smtp.gmail.com", "smtp_port": 587},
    },
    "reports": {
        "output_dir": "data/reports",
        "daily": True,
        "weekly": True,
        "daily_time": "09:00",
        "weekly_day": "monday",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Manages application configuration loaded from a YAML file."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration.

        Args:
            config_path: Path to the YAML config file.
        """
        self.config_path = config_path
        self._data: Dict[str, Any] = _deep_merge(DEFAULT_CONFIG, {})
        self._load()

    def _load(self):
        """Load and merge config from YAML file if it exists."""
        if not os.path.exists(self.config_path):
            logger.warning(
                "Config file '%s' not found. Using defaults. "
                "Copy config.example.yaml to config.yaml and fill in your credentials.",
                self.config_path,
            )
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                user_config = yaml.safe_load(fh) or {}
            self._data = _deep_merge(DEFAULT_CONFIG, user_config)
            logger.info("Configuration loaded from %s", self.config_path)
        except yaml.YAMLError as exc:
            logger.error("Failed to parse config file %s: %s", self.config_path, exc)
        except Exception as exc:
            logger.error("Failed to load config file %s: %s", self.config_path, exc)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level config value."""
        return self._data.get(key, default)

    @property
    def db_path(self) -> str:
        return self._data["database"]["path"]

    @property
    def keywords(self) -> List[str]:
        return self._data.get("keywords", [])

    @property
    def companies(self) -> List[Dict]:
        return self._data.get("companies", [])

    @property
    def sources(self) -> Dict[str, Any]:
        return self._data.get("sources", {})

    @property
    def notifications(self) -> Dict[str, Any]:
        return self._data.get("notifications", {})

    @property
    def reports(self) -> Dict[str, Any]:
        return self._data.get("reports", {})

    def get_source_config(self, source: str) -> Dict:
        """
        Get merged config for a specific source, including global keywords.

        Args:
            source: Source name (dou, telegram, linkedin, instagram, threads).

        Returns:
            Config dict for the source.
        """
        source_cfg = self.sources.get(source, {}).copy()
        # Inject global keywords if the source doesn't have its own
        if "keywords" not in source_cfg:
            source_cfg["keywords"] = self.keywords
        else:
            # Merge global keywords with source-specific ones
            all_kw = list(set(self.keywords + source_cfg["keywords"]))
            source_cfg["keywords"] = all_kw
        return source_cfg

    def is_source_enabled(self, source: str) -> bool:
        """Return True if the given source is enabled in config."""
        return bool(self.sources.get(source, {}).get("enabled", False))

    def reload(self):
        """Reload configuration from file."""
        self._load()

    def __repr__(self) -> str:
        return f"Config(path={self.config_path!r}, sources={list(self.sources.keys())})"
