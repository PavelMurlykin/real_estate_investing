from __future__ import annotations

import logging
from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from .key_rate_sync import KeyRateSyncError, sync_key_rates
from .models import KeyRate

logger = logging.getLogger(__name__)

SCHEDULE_HOUR = 15
SCHEDULE_MINUTE = 0

_scheduler_thread: Thread | None = None
_scheduler_lock = Lock()
_stop_event = Event()


def _get_timezone() -> ZoneInfo:
    return ZoneInfo(getattr(settings, 'TIME_ZONE', 'Europe/Moscow'))


def _seconds_until_next_run(now: datetime) -> float:
    next_run = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    return max((next_run - now).total_seconds(), 0.0)


def _run_sync_job() -> None:
    try:
        result = sync_key_rates()
        logger.info(
            'CBR key rate sync finished: created=%s updated=%s processed=%s',
            result['created'],
            result['updated'],
            result['processed'],
        )
    except KeyRateSyncError:
        logger.exception('CBR key rate sync failed with business error.')
    except Exception:  # pragma: no cover
        logger.exception('Unexpected error during CBR key rate sync.')


def _sync_if_empty() -> None:
    try:
        if not KeyRate.objects.exists():
            _run_sync_job()
    except (OperationalError, ProgrammingError):
        logger.debug('Skipping initial key rate sync: database table is not ready yet.')


def _scheduler_loop() -> None:
    timezone_info = _get_timezone()
    _sync_if_empty()

    while not _stop_event.is_set():
        now = datetime.now(timezone_info)
        wait_seconds = _seconds_until_next_run(now)
        if _stop_event.wait(wait_seconds):
            return
        _run_sync_job()


def start_key_rate_scheduler() -> None:
    global _scheduler_thread

    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return

        _stop_event.clear()
        _scheduler_thread = Thread(
            target=_scheduler_loop,
            name='key-rate-scheduler',
            daemon=True,
        )
        _scheduler_thread.start()
        logger.info(
            'CBR key rate scheduler started: daily at %02d:%02d (%s).',
            SCHEDULE_HOUR,
            SCHEDULE_MINUTE,
            getattr(settings, 'TIME_ZONE', 'Europe/Moscow'),
        )
