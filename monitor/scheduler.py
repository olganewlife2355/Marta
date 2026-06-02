"""
Scheduler - APScheduler-based job scheduler for periodic collection and reporting.
"""

import logging
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed. Scheduling disabled.")


class Scheduler:
    """
    Manages scheduled collection, notification, and reporting jobs.

    Jobs:
    - collect_all: every 30 minutes
    - send_notifications: every hour
    - daily_report: daily at configured time (default 09:00)
    - weekly_report: every Monday at configured time (default 09:00)
    """

    def __init__(self, config: dict, background: bool = False):
        """
        Initialize the scheduler.

        Args:
            config: Reports configuration dict (for timing settings).
            background: If True, use BackgroundScheduler (non-blocking).
                        If False, use BlockingScheduler (blocks main thread).
        """
        if not APSCHEDULER_AVAILABLE:
            raise RuntimeError("APScheduler is not installed. Run: pip install apscheduler")

        self.config = config
        self.daily_time = config.get("daily_time", "09:00")
        self.weekly_day = config.get("weekly_day", "monday")

        try:
            daily_hour, daily_minute = map(int, self.daily_time.split(":"))
        except (ValueError, AttributeError):
            daily_hour, daily_minute = 9, 0

        self._daily_hour = daily_hour
        self._daily_minute = daily_minute

        SchedulerClass = BackgroundScheduler if background else BlockingScheduler
        self.scheduler = SchedulerClass(
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
            timezone="UTC",
        )
        self._collect_fn: Optional[Callable] = None
        self._notify_fn: Optional[Callable] = None
        self._daily_fn: Optional[Callable] = None
        self._weekly_fn: Optional[Callable] = None

    def set_collect_fn(self, fn: Callable):
        """Register the collect_all function."""
        self._collect_fn = fn

    def set_notify_fn(self, fn: Callable):
        """Register the send_notifications function."""
        self._notify_fn = fn

    def set_daily_fn(self, fn: Callable):
        """Register the daily report function."""
        self._daily_fn = fn

    def set_weekly_fn(self, fn: Callable):
        """Register the weekly report function."""
        self._weekly_fn = fn

    def _safe_run(self, fn: Callable, job_name: str):
        """Wrap a job function with error handling."""
        def wrapper():
            try:
                logger.info("Running scheduled job: %s", job_name)
                fn()
                logger.info("Completed scheduled job: %s", job_name)
            except Exception as exc:
                logger.error("Error in scheduled job %s: %s", job_name, exc)
        return wrapper

    def setup_jobs(self):
        """Register all scheduled jobs."""
        if self._collect_fn:
            self.scheduler.add_job(
                self._safe_run(self._collect_fn, "collect_all"),
                trigger=IntervalTrigger(minutes=30),
                id="collect_all",
                name="Collect all sources",
                replace_existing=True,
            )
            logger.info("Scheduled: collect_all every 30 minutes")

        if self._notify_fn:
            self.scheduler.add_job(
                self._safe_run(self._notify_fn, "send_notifications"),
                trigger=IntervalTrigger(hours=1),
                id="send_notifications",
                name="Send notifications",
                replace_existing=True,
            )
            logger.info("Scheduled: send_notifications every hour")

        if self._daily_fn:
            self.scheduler.add_job(
                self._safe_run(self._daily_fn, "daily_report"),
                trigger=CronTrigger(hour=self._daily_hour, minute=self._daily_minute),
                id="daily_report",
                name="Generate daily report",
                replace_existing=True,
            )
            logger.info(
                "Scheduled: daily_report at %02d:%02d UTC", self._daily_hour, self._daily_minute
            )

        if self._weekly_fn:
            day_of_week = {
                "monday": "mon", "tuesday": "tue", "wednesday": "wed",
                "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
            }.get(self.weekly_day.lower(), "mon")

            self.scheduler.add_job(
                self._safe_run(self._weekly_fn, "weekly_report"),
                trigger=CronTrigger(
                    day_of_week=day_of_week,
                    hour=self._daily_hour,
                    minute=self._daily_minute,
                ),
                id="weekly_report",
                name="Generate weekly report",
                replace_existing=True,
            )
            logger.info(
                "Scheduled: weekly_report on %s at %02d:%02d UTC",
                day_of_week, self._daily_hour, self._daily_minute,
            )

    def start(self):
        """Start the scheduler (blocks if using BlockingScheduler)."""
        if not self.scheduler.get_jobs():
            logger.warning("No jobs registered. Call setup_jobs() first.")
        logger.info("Starting scheduler with %d jobs", len(self.scheduler.get_jobs()))
        self.scheduler.start()

    def stop(self):
        """Gracefully stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")

    def run_now(self, job_id: str):
        """Manually trigger a job by ID."""
        job = self.scheduler.get_job(job_id)
        if job:
            logger.info("Manually triggering job: %s", job_id)
            job.func()
        else:
            logger.error("Job not found: %s", job_id)

    def list_jobs(self):
        """Log all scheduled jobs and their next run times."""
        for job in self.scheduler.get_jobs():
            logger.info("Job: %s | Next: %s", job.name, job.next_run_time)
