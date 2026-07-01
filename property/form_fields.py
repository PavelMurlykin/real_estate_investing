"""Shared form fields for property catalog selectors."""

from django import forms

from .models import Developer


def get_developers_with_company_groups_queryset():
    """Return developers prepared for display with company group names."""
    return Developer.objects.select_related('company_group').order_by('name')


class DeveloperModelChoiceField(forms.ModelChoiceField):
    """Model choice field displaying developer names with company groups."""

    def label_from_instance(self, obj):
        """Return the user-facing developer option label."""
        return obj.get_display_name_with_company_group()
