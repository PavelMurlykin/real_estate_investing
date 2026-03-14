import os
import sys

from django.apps import AppConfig


class BankConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bank'

    def ready(self):
        if os.environ.get('DISABLE_KEY_RATE_SCHEDULER') == '1':
            return

        disabled_commands = {
            'makemigrations',
            'migrate',
            'collectstatic',
            'check',
            'test',
            'shell',
            'dbshell',
            'showmigrations',
            'createsuperuser',
        }
        if any(command in sys.argv for command in disabled_commands):
            return

        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return

        from .scheduler import start_key_rate_scheduler

        start_key_rate_scheduler()
