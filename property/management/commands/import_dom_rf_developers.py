"""Import developers from the DOM.RF developer registry."""

from django.core.management.base import BaseCommand, CommandError

from property.services.developer_registry_client import (
    DEFAULT_DEVELOPER_REGISTRY_REGIONS,
    DomRfDeveloperRegistryClient,
)
from property.services.developer_registry_file_client import (
    FileDeveloperRegistryClient,
)
from property.services.developer_registry_importer import (
    DeveloperRegistryImportError,
    import_dom_rf_developers,
)


class Command(BaseCommand):
    """Import developers and company groups from DOM.RF."""

    help = 'Import developers and company groups from DOM.RF registry.'

    def add_arguments(self, parser):
        """Register command line arguments."""
        parser.add_argument(
            '--region',
            action='append',
            dest='regions',
            help=(
                'Construction region code. May be passed multiple times. '
                'Defaults to 77 and 78.'
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and process records without committing changes.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of source rows to fetch.',
        )
        parser.add_argument(
            '--api-url',
            help='Override DOM.RF developer registry API URL.',
        )
        parser.add_argument(
            '--detail-api-url',
            help='Optional DOM.RF developer detail API URL.',
        )
        parser.add_argument(
            '--source-file',
            help=(
                'Read developers from a local CSV, XLSX, or JSON file instead '
                'of the DOM.RF API.'
            ),
        )

    def handle(self, *args, **options):
        """Run the developer registry import."""
        regions = options['regions'] or list(DEFAULT_DEVELOPER_REGISTRY_REGIONS)
        client = None
        source_file = options.get('source_file')
        if source_file:
            if options.get('api_url') or options.get('detail_api_url'):
                raise CommandError(
                    '--source-file cannot be used with API URL overrides.'
                )
            client = FileDeveloperRegistryClient(source_file)
        elif options.get('api_url') or options.get('detail_api_url'):
            client = DomRfDeveloperRegistryClient(
                api_url=options.get('api_url'),
                detail_api_url=options.get('detail_api_url'),
            )

        try:
            summary = import_dom_rf_developers(
                region_codes=regions,
                dry_run=options['dry_run'],
                limit=options.get('limit'),
                client=client,
            )
        except DeveloperRegistryImportError as exception:
            raise CommandError(str(exception)) from exception

        self.stdout.write(self.style.SUCCESS(summary.to_message()))
