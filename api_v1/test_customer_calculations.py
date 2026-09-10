import pytest
from django.test import Client
from django.urls import reverse

from customer.models import (
    Customer,
    CustomerCalculation,
    CustomerTrenchCalculation,
)
from mortgage.models import MortgageCalculation
from trench_mortgage.models import TrenchMortgageCalculation

from .test_customers import customer_profile, customer_users
from .test_saved_mortgage import (
    build_save_payload,
    saved_calculation_property,
)
from .test_trench_mortgage import build_saved_trench_mortgage_payload


def create_customer_calculations(
    client,
    customer,
    property_object,
):
    """Create one linked calculation of each supported program type."""
    market_response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data={
            **build_save_payload(property_object),
            'customerId': customer.pk,
        },
        content_type='application/json',
    )
    trench_response = client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data={
            **build_saved_trench_mortgage_payload(property_object),
            'customerId': customer.pk,
        },
        content_type='application/json',
    )
    assert market_response.status_code == 201
    assert trench_response.status_code == 201
    return market_response.json()['id'], trench_response.json()['id']


@pytest.mark.django_db
def test_customer_calculation_list_combines_programs_and_paginates(
    client,
    customer_users,
    customer_profile,
    saved_calculation_property,
    django_assert_num_queries,
):
    """Return a database-paginated union of linked mortgage programs."""
    owner, _other_owner = customer_users
    client.force_login(owner)
    market_identifier, trench_identifier = create_customer_calculations(
        client,
        customer_profile,
        saved_calculation_property,
    )

    with django_assert_num_queries(6):
        response = client.get(
            reverse(
                'api_v1:customer_calculation_list',
                kwargs={'pk': customer_profile.pk},
            ),
            {'q': 'Зелёный', 'pageSize': 1, 'ordering': 'annualRate'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['totalCount'] == 2
    assert payload['totalPages'] == 2
    assert len(payload['results']) == 1
    row = payload['results'][0]
    assert row['programType'] in {'market', 'trench'}
    assert row['calculationId'] in {market_identifier, trench_identifier}
    assert row['property']['realEstateComplex'] == 'Зелёный квартал'
    assert row['monthlyPayment'] is not None


@pytest.mark.django_db
def test_customer_calculation_endpoints_are_private_and_owner_scoped(
    client,
    customer_users,
    customer_profile,
):
    """Hide customer calculation data from anonymous and other users."""
    owner, other_owner = customer_users
    list_url = reverse(
        'api_v1:customer_calculation_list',
        kwargs={'pk': customer_profile.pk},
    )

    anonymous_response = client.get(list_url)
    client.force_login(other_owner)
    hidden_response = client.get(list_url)
    client.force_login(owner)
    visible_response = client.get(list_url)

    assert anonymous_response.status_code == 403
    assert hidden_response.status_code == 404
    assert visible_response.status_code == 200


@pytest.mark.django_db
def test_customer_can_attach_existing_accessible_calculations_once(
    client,
    customer_users,
    customer_profile,
    saved_calculation_property,
):
    """Bulk-link accessible calculations without duplicate relations."""
    owner, other_owner = customer_users
    client.force_login(owner)
    created_response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data=build_save_payload(saved_calculation_property),
        content_type='application/json',
    )
    calculation_identifier = created_response.json()['id']
    link_url = reverse(
        'api_v1:customer_calculation_list',
        kwargs={'pk': customer_profile.pk},
    )

    first_response = client.post(
        link_url,
        data={
            'programType': 'market',
            'calculationIds': [calculation_identifier],
        },
        content_type='application/json',
    )
    second_response = client.post(
        link_url,
        data={
            'programType': 'market',
            'calculationIds': [calculation_identifier],
        },
        content_type='application/json',
    )

    client.force_login(other_owner)
    other_owner_response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data=build_save_payload(saved_calculation_property),
        content_type='application/json',
    )
    other_owner_calculation_identifier = other_owner_response.json()['id']

    client.force_login(owner)
    inaccessible_calculation_response = client.post(
        link_url,
        data={
            'programType': 'market',
            'calculationIds': [other_owner_calculation_identifier],
        },
        content_type='application/json',
    )

    client.force_login(other_owner)
    unavailable_response = client.post(
        link_url,
        data={
            'programType': 'market',
            'calculationIds': [calculation_identifier],
        },
        content_type='application/json',
    )

    assert first_response.status_code == 201
    assert first_response.json()['createdCount'] == 1
    assert second_response.status_code == 201
    assert second_response.json()['createdCount'] == 0
    assert inaccessible_calculation_response.status_code == 400
    assert unavailable_response.status_code == 404
    assert CustomerCalculation.objects.filter(
        customer=customer_profile,
        calculation_id=calculation_identifier,
    ).count() == 1


@pytest.mark.django_db
def test_saved_calculation_histories_mark_customer_links(
    client,
    customer_users,
    customer_profile,
    saved_calculation_property,
):
    """Mark links only when a visible customer context is requested."""
    owner, _other_owner = customer_users
    client.force_login(owner)
    market_identifier, trench_identifier = create_customer_calculations(
        client,
        customer_profile,
        saved_calculation_property,
    )

    market_response = client.get(
        reverse('api_v1:saved_mortgage_calculation_list'),
        {'customerId': customer_profile.pk},
    )
    trench_response = client.get(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        {'customerId': customer_profile.pk},
    )
    ordinary_market_response = client.get(
        reverse('api_v1:saved_mortgage_calculation_list')
    )

    market_row = next(
        row for row in market_response.json()['results']
        if row['id'] == market_identifier
    )
    trench_row = next(
        row for row in trench_response.json()['results']
        if row['id'] == trench_identifier
    )
    ordinary_market_row = next(
        row for row in ordinary_market_response.json()['results']
        if row['id'] == market_identifier
    )
    assert market_row['isLinked'] is True
    assert trench_row['isLinked'] is True
    assert ordinary_market_row['isLinked'] is False


@pytest.mark.django_db
def test_new_calculation_rejects_another_owners_customer_before_saving(
    client,
    customer_users,
    customer_profile,
    saved_calculation_property,
):
    """Do not create a calculation when the requested customer is hidden."""
    owner, other_owner = customer_users
    hidden_customer = Customer.objects.create(
        user=other_owner,
        first_name='Скрытый',
    )
    client.force_login(owner)
    calculations_before_request = MortgageCalculation.objects.count()

    response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data={
            **build_save_payload(saved_calculation_property),
            'customerId': hidden_customer.pk,
        },
        content_type='application/json',
    )

    assert response.status_code == 404
    assert MortgageCalculation.objects.count() == calculations_before_request


@pytest.mark.django_db
def test_customer_calculation_unlink_preserves_saved_calculation_and_csrf(
    client,
    customer_users,
    customer_profile,
    saved_calculation_property,
):
    """Remove only the relationship and require CSRF for the mutation."""
    owner, _other_owner = customer_users
    client.force_login(owner)
    market_identifier, _trench_identifier = create_customer_calculations(
        client,
        customer_profile,
        saved_calculation_property,
    )
    link = CustomerCalculation.objects.get(
        customer=customer_profile,
        calculation_id=market_identifier,
    )
    unlink_url = reverse(
        'api_v1:customer_calculation_link_detail',
        kwargs={
            'pk': customer_profile.pk,
            'program_type': 'market',
            'link_pk': link.pk,
        },
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(owner)

    rejected_response = csrf_client.delete(unlink_url)
    response = client.delete(unlink_url)

    assert rejected_response.status_code == 403
    assert response.status_code == 204
    assert not CustomerCalculation.objects.filter(pk=link.pk).exists()
    assert MortgageCalculation.objects.filter(pk=market_identifier).exists()


@pytest.mark.django_db
def test_customer_calculation_word_export_combines_selected_programs(
    client,
    customer_users,
    customer_profile,
    saved_calculation_property,
):
    """Build one Word file from owner-scoped market and tranche links."""
    owner, other_owner = customer_users
    client.force_login(owner)
    market_identifier, trench_identifier = create_customer_calculations(
        client,
        customer_profile,
        saved_calculation_property,
    )
    market_link = CustomerCalculation.objects.get(
        customer=customer_profile,
        calculation_id=market_identifier,
    )
    trench_link = CustomerTrenchCalculation.objects.get(
        customer=customer_profile,
        calculation_id=trench_identifier,
    )
    export_url = reverse(
        'api_v1:customer_calculation_export_word',
        kwargs={'pk': customer_profile.pk},
    )
    selections = [
        {'programType': 'market', 'linkId': market_link.pk},
        {'programType': 'trench', 'linkId': trench_link.pk},
    ]

    response = client.post(
        export_url,
        data={'selections': selections},
        content_type='application/json',
    )
    client.force_login(other_owner)
    hidden_response = client.post(
        export_url,
        data={'selections': selections},
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response['Content-Type'] == (
        'application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.document'
    )
    assert response.content.startswith(b'PK')
    assert hidden_response.status_code == 404


@pytest.mark.django_db
def test_customer_delete_removes_links_but_preserves_calculations(
    client,
    customer_users,
    customer_profile,
    saved_calculation_property,
):
    """Delete an owned profile without deleting saved mortgage scenarios."""
    owner, _other_owner = customer_users
    client.force_login(owner)
    market_identifier, trench_identifier = create_customer_calculations(
        client,
        customer_profile,
        saved_calculation_property,
    )
    customer_url = reverse(
        'api_v1:customer_detail',
        kwargs={'pk': customer_profile.pk},
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(owner)

    rejected_response = csrf_client.delete(customer_url)
    response = client.delete(customer_url)

    assert rejected_response.status_code == 403
    assert response.status_code == 204
    assert not Customer.objects.filter(pk=customer_profile.pk).exists()
    assert MortgageCalculation.objects.filter(pk=market_identifier).exists()
    assert TrenchMortgageCalculation.objects.filter(
        pk=trench_identifier
    ).exists()
