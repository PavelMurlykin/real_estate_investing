from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from bank.models import (
    Bank,
    BankProgram,
    MortgageProgram,
    MortgageProgramAlias,
    MortgageProgramRegionalCreditLimit,
)
from location.models import Region
from users.roles import MODERATOR_GROUP_NAME


@pytest.fixture
def mortgage_program_catalog():
    """Create canonical programs and their representative relations."""
    moscow = Region.objects.create(name='Москва', code='MOW')
    saint_petersburg = Region.objects.create(
        name='Санкт-Петербург',
        code='SPE',
    )
    family_program = MortgageProgram.objects.create(
        name='Семейная ипотека',
        condition='Для семей с детьми',
        is_preferential=True,
        credit_limit=Decimal('12000000.00'),
    )
    market_program = MortgageProgram.objects.create(
        name='Рыночная ипотека',
        condition='Стандартные условия',
        is_active=False,
    )
    bank = Bank.objects.create(name='Тест Банк')
    BankProgram.objects.create(
        bank=bank,
        mortgage_program=family_program,
        interest_rate=Decimal('6.00'),
        minimum_initial_payment_percent=Decimal('20.00'),
    )
    regional_limit = MortgageProgramRegionalCreditLimit.objects.create(
        mortgage_program=family_program,
        region=moscow,
        credit_limit=Decimal('15000000.00'),
    )
    alias = MortgageProgramAlias.objects.create(
        mortgage_program=family_program,
        source_name='Family mortgage special',
        source='Тестовый источник',
    )
    return {
        'alias': alias,
        'bank': bank,
        'family_program': family_program,
        'market_program': market_program,
        'moscow': moscow,
        'regional_limit': regional_limit,
        'saint_petersburg': saint_petersburg,
    }


def create_catalog_manager():
    """Create a user allowed to mutate canonical mortgage programs."""
    user = get_user_model().objects.create_user(
        email='mortgage-program-moderator@example.com',
        password='safe-test-password',
        phone_number='+79990000211',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


@pytest.mark.django_db
def test_mortgage_program_list_is_public_filtered_and_query_efficient(
    client,
    mortgage_program_catalog,
    django_assert_num_queries,
):
    """Search aliases and return aggregate usage with two queries."""
    with django_assert_num_queries(2):
        response = client.get(
            reverse('api_v1:mortgage_program_list'),
            {
                'q': 'Family',
                'programType': 'preferential',
                'status': 'active',
                'ordering': '-creditLimit',
            },
        )

    assert response.status_code == 200
    assert response.json()['totalCount'] == 1
    assert response.json()['results'] == [
        {
            'id': mortgage_program_catalog['family_program'].pk,
            'name': 'Семейная ипотека',
            'condition': 'Для семей с детьми',
            'isPreferential': True,
            'creditLimit': '12000000.00',
            'bankCount': 1,
            'developerProgramCount': 0,
            'regionalLimitCount': 1,
            'aliasCount': 1,
            'isActive': True,
            'updatedAt': response.json()['results'][0]['updatedAt'],
            'detailUrl': (
                '/mortgage-programs/'
                f"{mortgage_program_catalog['family_program'].pk}"
            ),
            'legacyEditUrl': (
                '/bank/?model=mortgage_program&edit='
                f"{mortgage_program_catalog['family_program'].pk}"
            ),
        }
    ]


@pytest.mark.django_db
def test_mortgage_program_list_can_select_inactive_market_programs(
    client,
    mortgage_program_catalog,
):
    """Support explicit program-type and inactive status filters."""
    response = client.get(
        reverse('api_v1:mortgage_program_list'),
        {'programType': 'market', 'status': 'inactive'},
    )

    assert response.status_code == 200
    assert [row['id'] for row in response.json()['results']] == [
        mortgage_program_catalog['market_program'].pk
    ]


@pytest.mark.django_db
def test_mortgage_program_detail_is_complete_and_query_efficient(
    client,
    mortgage_program_catalog,
    django_assert_num_queries,
):
    """Return canonical data, limits, aliases, and usage in three queries."""
    with django_assert_num_queries(3):
        response = client.get(
            reverse(
                'api_v1:mortgage_program_detail',
                kwargs={
                    'pk': mortgage_program_catalog['family_program'].pk,
                },
            )
        )

    assert response.status_code == 200
    assert response.json()['bankCount'] == 1
    assert response.json()['regionalCreditLimits'] == [
        {
            'id': mortgage_program_catalog['regional_limit'].pk,
            'regionId': mortgage_program_catalog['moscow'].pk,
            'regionName': 'Москва',
            'creditLimit': '15000000.00',
            'isActive': True,
        }
    ]
    assert response.json()['aliases'] == [
        {
            'id': mortgage_program_catalog['alias'].pk,
            'sourceName': 'Family mortgage special',
            'normalizedName': 'familymortgagespecial',
            'source': 'Тестовый источник',
            'isActive': True,
        }
    ]
    assert response.json()['legacyCatalogUrl'] == (
        '/bank/?model=mortgage_program'
    )


@pytest.mark.django_db
def test_mortgage_program_options_are_public_and_bounded(
    client,
    mortgage_program_catalog,
    settings,
):
    """Expose bounded public region choices with truncation metadata."""
    settings.PUBLIC_CATALOG_API_MAX_RESULTS = 1

    response = client.get(reverse('api_v1:mortgage_program_options'))

    assert response.status_code == 200
    assert len(response.json()['regions']) == 1
    assert response.json()['truncated'] is True
    assert set(response.json()['regions'][0]) == {'id', 'name'}


@pytest.mark.django_db
def test_mortgage_program_mutations_require_catalog_permission(
    client,
    mortgage_program_catalog,
):
    """Reject canonical program writes from a regular authenticated user."""
    regular_user = get_user_model().objects.create_user(
        email='mortgage-program-regular@example.com',
        password='safe-test-password',
        phone_number='+79990000212',
    )
    client.force_login(regular_user)

    response = client.post(
        reverse('api_v1:mortgage_program_list'),
        data={
            'name': 'Новая программа',
            'condition': 'Новые условия',
        },
        content_type='application/json',
    )

    assert response.status_code == 403
    assert not MortgageProgram.objects.filter(name='Новая программа').exists()


@pytest.mark.django_db
def test_catalog_manager_can_create_complete_mortgage_program(
    client,
    mortgage_program_catalog,
):
    """Create a normalized program with regional limits and aliases."""
    client.force_login(create_catalog_manager())

    response = client.post(
        reverse('api_v1:mortgage_program_list'),
        data={
            'name': '  Новая   льготная программа  ',
            'condition': '  Для покупателей новостроек  ',
            'isPreferential': True,
            'creditLimit': '9000000.00',
            'isActive': True,
            'regionalCreditLimits': [
                {
                    'regionId': (
                        mortgage_program_catalog['saint_petersburg'].pk
                    ),
                    'creditLimit': '11000000.00',
                    'isActive': True,
                }
            ],
            'aliases': [
                {
                    'sourceName': 'New build special',
                    'source': 'Партнёрский файл',
                    'isActive': True,
                }
            ],
        },
        content_type='application/json',
    )

    assert response.status_code == 201, response.json()
    mortgage_program = MortgageProgram.objects.get(
        name='Новая льготная программа'
    )
    assert mortgage_program.condition == 'Для покупателей новостроек'
    assert response.json()['id'] == mortgage_program.pk
    assert len(response.json()['regionalCreditLimits']) == 1
    assert len(response.json()['aliases']) == 1
    assert MortgageProgramAlias.objects.get(
        mortgage_program=mortgage_program
    ).normalized_name == 'newbuildspecial'


@pytest.mark.django_db
def test_catalog_manager_patch_replaces_limits_and_aliases(
    client,
    mortgage_program_catalog,
):
    """Replace both submitted nested collections in one transaction."""
    client.force_login(create_catalog_manager())
    response = client.patch(
        reverse(
            'api_v1:mortgage_program_detail',
            kwargs={'pk': mortgage_program_catalog['family_program'].pk},
        ),
        data={
            'name': 'Семейная ипотека обновлённая',
            'regionalCreditLimits': [
                {
                    'regionId': (
                        mortgage_program_catalog['saint_petersburg'].pk
                    ),
                    'creditLimit': '18000000.00',
                    'isActive': False,
                }
            ],
            'aliases': [
                {
                    'sourceName': 'Updated family offer',
                    'source': '',
                    'isActive': True,
                }
            ],
        },
        content_type='application/json',
    )

    assert response.status_code == 200, response.json()
    mortgage_program_catalog['family_program'].refresh_from_db()
    assert mortgage_program_catalog['family_program'].name == (
        'Семейная ипотека обновлённая'
    )
    regional_limits = MortgageProgramRegionalCreditLimit.objects.filter(
        mortgage_program=mortgage_program_catalog['family_program']
    )
    assert regional_limits.count() == 1
    assert regional_limits.get().region == (
        mortgage_program_catalog['saint_petersburg']
    )
    aliases = MortgageProgramAlias.objects.filter(
        mortgage_program=mortgage_program_catalog['family_program']
    )
    assert aliases.count() == 1
    assert aliases.get().normalized_name == 'updatedfamilyoffer'


@pytest.mark.django_db
def test_mortgage_program_api_validates_nested_duplicates_and_values(
    client,
    mortgage_program_catalog,
):
    """Reject duplicate names, repeated relations, and invalid values."""
    client.force_login(create_catalog_manager())
    list_url = reverse('api_v1:mortgage_program_list')

    duplicate_name_response = client.post(
        list_url,
        data={
            'name': '  семейная ипотека ',
            'condition': 'Условия',
        },
        content_type='application/json',
    )
    duplicate_relations_response = client.post(
        list_url,
        data={
            'name': 'Программа с дублями',
            'condition': 'Условия',
            'regionalCreditLimits': [
                {
                    'regionId': mortgage_program_catalog['moscow'].pk,
                    'creditLimit': '100.00',
                },
                {
                    'regionId': mortgage_program_catalog['moscow'].pk,
                    'creditLimit': '200.00',
                },
            ],
            'aliases': [
                {'sourceName': 'Unique source offer'},
                {'sourceName': 'Unique source offer'},
            ],
        },
        content_type='application/json',
    )
    invalid_values_response = client.post(
        list_url,
        data={
            'name': 'Программа с ошибками',
            'condition': '',
            'creditLimit': '-1.00',
            'regionalCreditLimits': [
                {
                    'regionId': mortgage_program_catalog['moscow'].pk,
                    'creditLimit': '-2.00',
                }
            ],
            'aliases': [{'sourceName': 'Ипотека'}],
        },
        content_type='application/json',
    )

    assert duplicate_name_response.status_code == 400
    assert 'name' in duplicate_name_response.json()
    assert duplicate_relations_response.status_code == 400
    assert 'regionalCreditLimits' in duplicate_relations_response.json()
    assert 'aliases' in duplicate_relations_response.json()
    assert invalid_values_response.status_code == 400
    assert 'condition' in invalid_values_response.json()
    assert 'creditLimit' in invalid_values_response.json()
    assert 'regionalCreditLimits' in invalid_values_response.json()
    assert 'aliases' in invalid_values_response.json()
    assert not MortgageProgram.objects.filter(
        name='Программа с ошибками'
    ).exists()


@pytest.mark.django_db
def test_mortgage_program_api_rejects_alias_owned_by_another_program(
    client,
    mortgage_program_catalog,
):
    """Keep globally unique normalized alias ownership authoritative."""
    client.force_login(create_catalog_manager())

    response = client.post(
        reverse('api_v1:mortgage_program_list'),
        data={
            'name': 'Конфликтующая программа',
            'condition': 'Условия',
            'aliases': [{'sourceName': 'Family mortgage special'}],
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'aliases' in response.json()
    assert not MortgageProgram.objects.filter(
        name='Конфликтующая программа'
    ).exists()


@pytest.mark.django_db
def test_mortgage_program_delete_reports_dependencies_and_cascades_nested_rows(
    client,
    mortgage_program_catalog,
):
    """Block used programs and cascade nested rows for unused programs."""
    client.force_login(create_catalog_manager())
    unused_program = mortgage_program_catalog['market_program']
    unused_alias = MortgageProgramAlias.objects.create(
        mortgage_program=unused_program,
        source_name='Unused market offer',
    )
    unused_limit = MortgageProgramRegionalCreditLimit.objects.create(
        mortgage_program=unused_program,
        region=mortgage_program_catalog['saint_petersburg'],
        credit_limit=Decimal('8000000.00'),
    )

    conflict_response = client.delete(
        reverse(
            'api_v1:mortgage_program_detail',
            kwargs={'pk': mortgage_program_catalog['family_program'].pk},
        )
    )
    delete_response = client.delete(
        reverse(
            'api_v1:mortgage_program_detail',
            kwargs={'pk': unused_program.pk},
        )
    )

    assert conflict_response.status_code == 409
    assert MortgageProgram.objects.filter(
        pk=mortgage_program_catalog['family_program'].pk
    ).exists()
    assert delete_response.status_code == 204
    assert not MortgageProgram.objects.filter(pk=unused_program.pk).exists()
    assert not MortgageProgramAlias.objects.filter(pk=unused_alias.pk).exists()
    assert not MortgageProgramRegionalCreditLimit.objects.filter(
        pk=unused_limit.pk
    ).exists()
