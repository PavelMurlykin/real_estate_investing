"""Keep the saved-calculation filter form compatible with shared location controls."""

from location.filter_forms import LocationFilterForm


class CalculationLocationForm(LocationFilterForm):
    """Use the same bounded geography fields in calculation and property catalogs."""
