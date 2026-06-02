"""
Social Media Job Monitor - main entry point.

Usage:
    python main.py                  # Start scheduler (runs indefinitely)
    python main.py --collect        # Run one-shot collection
    python main.py --report daily   # Generate daily report
    python main.py --report weekly  # Generate weekly report
    python main.py --notify         # Send pending notifications
    python main.py --config PATH    # Use a specific config file
"""

import argparse
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Social Media Job Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml)",
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="Run a one-shot collection from all enabled sources and exit",
    )
    parser.add_argument(
        "--report",
        choices=["daily", "weekly"],
        help="Generate a report and exit",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send notifications for pending (unnotified) posts and exit",
    )
    parser.add_argument(
        "--list-jobs",
        action="store_true",
        help="List all scheduled jobs and exit",
    )
    return parser


def create_app(config_path: str):
    """
    Initialize all application components.

    Returns:
        Tuple of (config, storage, collector_map, notifier, reporter, scheduler).
    """
    from monitor.config import Config
    from monitor.storage import Storage
    from monitor.notifier import Notifier
    from monitor.reporter import Reporter
    from monitor.scheduler import Scheduler

    cfg = Config(config_path)
    storage = Storage(cfg.db_path)
    notifier = Notifier(cfg.notifications)
    reporter = Reporter(storage, cfg.reports)

    # Sync companies to DB
    for company in cfg.companies:
        try:
            storage.upsert_company(company)
        except Exception as exc:
            logger.warning("Failed to upsert company %s: %s", company.get("name"), exc)

    return cfg, storage, notifier, reporter


def collect_all(cfg, storage):
    """Run collection from all enabled sources and save to storage."""
    from monitor.collectors.dou import DOUCollector
    from monitor.collectors.telegram_collector import TelegramCollector
    from monitor.collectors.linkedin import LinkedInCollector
    from monitor.collectors.instagram import InstagramCollector
    from monitor.collectors.threads import ThreadsCollector

    collectors = {
        "dou": DOUCollector,
        "telegram": TelegramCollector,
        "linkedin": LinkedInCollector,
        "instagram": InstagramCollector,
        "threads": ThreadsCollector,
    }

    total_new = 0
    for source, CollectorClass in collectors.items():
        if not cfg.is_source_enabled(source):
            logger.info("Source disabled: %s", source)
            continue

        source_cfg = cfg.get_source_config(source)
        logger.info("Starting collection from: %s", source)
        try:
            collector = CollectorClass(source_cfg)
            if source == "dou":
                posts = collector.collect(companies=cfg.companies)
            else:
                posts = collector.collect()

            new, dup = storage.save_posts(posts)
            total_new += new
            logger.info("%s: %d new, %d duplicates", source, new, dup)
        except Exception as exc:
            logger.error("Collection failed for %s: %s", source, exc)

    logger.info("Collection complete. Total new posts: %d", total_new)
    return total_new


def send_notifications(cfg, storage, notifier):
    """Fetch unnotified posts and send notifications."""
    batch_size = cfg.notifications.get("telegram", {}).get("batch_size", 10)
    new_posts = storage.get_new_posts(limit=batch_size)

    if not new_posts:
        logger.info("No new posts to notify.")
        return

    logger.info("Sending notifications for %d posts", len(new_posts))
    notifier.notify_posts(new_posts)
    storage.mark_notified([p["id"] for p in new_posts])


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    logger.info("Social Media Job Monitor starting...")
    cfg, storage, notifier, reporter = create_app(args.config)

    # -----------------------------------------------------------------------
    # One-shot modes
    # -----------------------------------------------------------------------
    if args.collect:
        logger.info("Mode: one-shot collection")
        collect_all(cfg, storage)
        return

    if args.report:
        logger.info("Mode: generate %s report", args.report)
        if args.report == "daily":
            text = reporter.run_daily()
        else:
            text = reporter.run_weekly()
        print(text)
        return

    if args.notify:
        logger.info("Mode: send notifications")
        send_notifications(cfg, storage, notifier)
        return

    # -----------------------------------------------------------------------
    # Scheduler mode (default)
    # -----------------------------------------------------------------------
    logger.info("Mode: scheduler")
    try:
        from monitor.scheduler import Scheduler
    except ImportError as exc:
        logger.error("Cannot start scheduler: %s", exc)
        sys.exit(1)

    scheduler = Scheduler(cfg.reports, background=False)

    scheduler.set_collect_fn(lambda: collect_all(cfg, storage))
    scheduler.set_notify_fn(lambda: send_notifications(cfg, storage, notifier))
    scheduler.set_daily_fn(lambda: reporter.run_daily())
    scheduler.set_weekly_fn(lambda: reporter.run_weekly())

    scheduler.setup_jobs()

    if args.list_jobs:
        scheduler.list_jobs()
        return

    # Run an initial collection immediately on startup
    logger.info("Running initial collection on startup...")
    try:
        collect_all(cfg, storage)
    except Exception as exc:
        logger.error("Initial collection failed: %s", exc)

    try:
        logger.info("Scheduler started. Press Ctrl+C to stop.")
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()


if __name__ == "__main__":
    main()
