"""
Background Job Scheduler.

WHAT: Configures and manages APScheduler for background tasks.

WHY: Background jobs enable:
1. Periodic SLA breach checks without user requests
2. Scheduled tasks (email digests, data cleanup)
3. Deferred processing (webhooks, notifications)

HOW: Uses APScheduler with AsyncIOScheduler for async job support.
Redis job store can be enabled for persistence across restarts.

Example:
    # In main.py startup:
    from app.services.scheduler import start_scheduler, shutdown_scheduler

    @app.on_event("startup")
    async def startup():
        await start_scheduler()

    @app.on_event("shutdown")
    async def shutdown():
        await shutdown_scheduler()
"""

import logging
import asyncio
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.services.sla_background_service import (
    get_sla_service,
    SLA_CHECK_INTERVAL_SECONDS,
)


logger = logging.getLogger(__name__)


# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the global scheduler instance."""
    return _scheduler


async def start_scheduler() -> None:
    """
    Start the background job scheduler.

    WHAT: Initializes APScheduler with configured jobs.

    WHY: Enables background processing for:
    - SLA breach monitoring (every 5 minutes)
    - Future: email digests, cleanup tasks

    HOW:
    1. Creates AsyncIOScheduler with memory job store
    2. Registers SLA check job
    3. Starts the scheduler

    Note: Call this from FastAPI startup event.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running")
        return

    # Configure job stores
    jobstores = {
        "default": MemoryJobStore()
    }

    # Configure executors
    executors = {
        "default": AsyncIOExecutor()
    }

    # Job defaults
    job_defaults = {
        "coalesce": True,  # Combine multiple missed runs into one
        "max_instances": 1,  # Only one instance of each job at a time
        "misfire_grace_time": 60,  # Allow 60s late execution
    }

    # Create scheduler
    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone="UTC",
    )

    # Register SLA check job
    _register_sla_check_job()

    # Start scheduler
    _scheduler.start()
    logger.info(
        f"Scheduler started with SLA check every {SLA_CHECK_INTERVAL_SECONDS} seconds"
    )


def _register_sla_check_job() -> None:
    """
    Register the SLA breach check job.

    WHAT: Schedules periodic SLA status checks.

    WHY: Proactive SLA monitoring catches breaches before customers notice.

    HOW: Runs check_all_sla_breaches every 5 minutes (configurable).
    """
    global _scheduler

    if _scheduler is None:
        logger.error("Cannot register job: scheduler not initialized")
        return

    sla_service = get_sla_service()

    _scheduler.add_job(
        func=sla_service.check_all_sla_breaches,
        trigger=IntervalTrigger(seconds=SLA_CHECK_INTERVAL_SECONDS),
        id="sla_breach_check",
        name="SLA Breach Check",
        replace_existing=True,
    )

    logger.info(
        f"Registered SLA breach check job (interval: {SLA_CHECK_INTERVAL_SECONDS}s)"
    )


async def shutdown_scheduler() -> None:
    """
    Shut down the background job scheduler.

    WHAT: Gracefully stops the scheduler.

    WHY: Ensures running jobs complete and resources are released.

    HOW: Calls scheduler.shutdown() and waits for jobs to finish.

    Note: Call this from FastAPI shutdown event.
    """
    global _scheduler

    if _scheduler is None:
        logger.info("Scheduler not running")
        return

    if not _scheduler.running:
        logger.info("Scheduler already stopped")
        return

    logger.info("Shutting down scheduler...")
    _scheduler.shutdown(wait=True)
    _scheduler = None
    logger.info("Scheduler shut down successfully")


async def run_sla_check_now() -> dict:
    """
    Run SLA breach check immediately.

    WHAT: Triggers an immediate SLA check outside the schedule.

    WHY: Useful for:
    - Manual testing
    - Admin-triggered checks
    - After bulk ticket imports

    Returns:
        Dict with check results (counts of warnings/breaches)
    """
    sla_service = get_sla_service()
    return await sla_service.check_all_sla_breaches()


def get_scheduler_status() -> dict:
    """
    Get scheduler status information.

    WHAT: Returns scheduler state and job info.

    WHY: Enables health checks and monitoring.

    Returns:
        Dict with scheduler status and job details
    """
    global _scheduler

    if _scheduler is None:
        return {
            "running": False,
            "jobs": [],
            "message": "Scheduler not initialized",
        }

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": _scheduler.running,
        "jobs": jobs,
        "message": "Scheduler is running" if _scheduler.running else "Scheduler is paused",
    }
