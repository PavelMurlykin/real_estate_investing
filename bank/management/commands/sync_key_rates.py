from django.core.management.base import BaseCommand, CommandError

from bank.key_rate_sync import KeyRateSyncError, sync_key_rates


class Command(BaseCommand):
    """Описание класса Command.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    help = 'Загружает и обновляет ключевую ставку ЦБ РФ.'

    def handle(self, *args, **options):
        """Описание метода handle.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            *args: Входной параметр, влияющий на работу метода.
            **options: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        try:
            result = sync_key_rates()
            created_count = result['created']
            updated_count = result['updated']
            processed_count = result['processed']
        except KeyRateSyncError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                f'Синхронизация завершена: создано={created_count}, '
                'обновлено='
                f'{updated_count}, '
                'обработано='
                f'{processed_count}.',
            ),
        )
