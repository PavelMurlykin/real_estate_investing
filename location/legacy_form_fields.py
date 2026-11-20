"""Use compatibility identities in Django forms that still submit old IDs."""

from django import forms

from .legacy_catalog import legacy_choices


class LegacyLocationChoiceField(forms.ModelChoiceField):
    """Keep old field names and values while validating against the registry."""

    def __init__(self, model_name, **kwargs):
        """Resolve IDs in their declared namespace and display former labels."""
        super().__init__(queryset=legacy_choices(model_name), to_field_name='legacy_id', **kwargs)

    def label_from_instance(self, alias):
        """Display the label the old selector used for the same numeric ID."""
        return alias.legacy_name
