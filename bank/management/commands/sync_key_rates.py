from django.core.management.base import BaseCommand, CommandError

from bank.key_rate_sync import KeyRateSyncError, sync_key_rates


class Command(BaseCommand):
    help = 'Загружает и обновляет ключевую ставку ЦБ РФ.'

    def handle(self, *args, **options):
        try:
            result = sync_key_rates()
        except KeyRateSyncError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Синхронизация завершена: создано={result['created']}, "
                f"обновлено={result['updated']}, обработано={result['processed']}.",
            ),
        )
