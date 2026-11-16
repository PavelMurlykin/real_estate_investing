"""Process national location imports outside HTTP worker time limits."""

import logging
import tempfile
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from location.jobs import process_next_import

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Poll the durable queue and recover interrupted jobs on restart."""

    help = 'Run the persistent Russian location import worker.'

    def add_arguments(self, parser):
        """Support a single poll for integration checks and local operation."""
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        """Keep heartbeats fresh and leave failed processes recoverable."""
        heartbeat_file = Path(tempfile.gettempdir()) / 'location-import-worker-heartbeat'
        while True:
            close_old_connections()
            heartbeat_file.touch()
            try:
                job = process_next_import(heartbeat_file.touch)
            except Exception:
                logger.exception('Location import worker interrupted; checkpoint retained.')
                if options['once']:
                    raise
            if options['once']:
                if job and job.status == 'failed':
                    raise CommandError(job.error_message)
                return
            time.sleep(2)
