from django.core.management.base import BaseCommand, CommandError

from bank.mortgage_offer_sync import (
    BankMortgageSyncError,
    sync_bank_mortgage_offers,
)


class Command(BaseCommand):
    """Synchronize bank mortgage offers from an external source."""

    help = 'Загружает банки из ЦБ РФ и ипотечные программы с Banki.ru.'

    def add_arguments(self, parser):
        """Add optional source URL argument."""
        parser.add_argument(
            '--source-url',
            default=None,
            help='URL страницы с ипотечными предложениями.',
        )
        parser.add_argument(
            '--cbr-source-url',
            default=None,
            help='URL списка кредитных организаций Банка России.',
        )

    def handle(self, *args, **options):
        """Run bank mortgage offer synchronization."""
        try:
            result = sync_bank_mortgage_offers(
                source_url=options.get('source_url'),
                cbr_source_url=options.get('cbr_source_url'),
            )
        except BankMortgageSyncError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                'Синхронизация завершена: '
                f'создано={result["created"]}, '
                f'обновлено={result["updated"]}, '
                f'обработано={result["processed"]}.',
            )
        )
