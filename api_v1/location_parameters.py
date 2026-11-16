"""Declare canonical scope identifiers separately from financial legacy IDs."""

from rest_framework import serializers


class LocationScopeQuerySerializer(serializers.Serializer):
    """Accept bounded canonical IDs while retaining older query parameters."""

    regionLocationId = serializers.IntegerField(required=False, min_value=1)
    districtLocationId = serializers.IntegerField(required=False, min_value=1)
    localityId = serializers.IntegerField(required=False, min_value=1)
    locationId = serializers.IntegerField(required=False, min_value=1)
