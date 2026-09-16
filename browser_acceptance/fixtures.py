"""Seed synthetic data only in the explicitly isolated PostgreSQL stack."""

import json
import os
from decimal import Decimal

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction

DATABASE_NAME = 'react_browser_acceptance'


def ensure_isolated_database():
    """Refuse fixture writes unless all isolated-stand guards are satisfied."""
    if os.environ.get('BROWSER_ACCEPTANCE_ISOLATED') != '1':
        raise RuntimeError('Acceptance fixture writes require isolation marker')
    if settings.DATABASES['default']['NAME'] != DATABASE_NAME:
        raise RuntimeError('Acceptance fixtures require their dedicated database')
    if connection.vendor != 'postgresql':
        raise RuntimeError('Acceptance fixtures require PostgreSQL')


def create_property_fixture():
    """Create an idempotent synthetic property graph for saved calculations."""
    from location.models import City, District, Region
    from property.models import (
        ApartmentDecoration,
        ApartmentLayout,
        Developer,
        Property,
        RealEstateClass,
        RealEstateComplex,
        RealEstateComplexBuilding,
        RealEstateType,
    )

    region, _ = Region.objects.get_or_create(
        code='E2E', defaults={'name': 'E2E регион'},
    )
    city, _ = City.objects.get_or_create(name='E2E город', region=region)
    district, _ = District.objects.get_or_create(name='E2E район', city=city)
    developer, _ = Developer.objects.get_or_create(name='E2E застройщик')
    real_estate_type, _ = RealEstateType.objects.get_or_create(name='E2E квартира')
    real_estate_class, _ = RealEstateClass.objects.get_or_create(
        name='E2E комфорт', defaults={'weight': Decimal('1.00')},
    )
    real_estate_complex, _ = RealEstateComplex.objects.get_or_create(
        name='E2E квартал',
        developer=developer,
        defaults={
            'district': district,
            'real_estate_class': real_estate_class,
            'real_estate_type': real_estate_type,
        },
    )
    building, _ = RealEstateComplexBuilding.objects.get_or_create(
        number='1', real_estate_complex=real_estate_complex,
    )
    layout, _ = ApartmentLayout.objects.get_or_create(name='E2E планировка')
    decoration, _ = ApartmentDecoration.objects.get_or_create(name='E2E отделка')
    property_object, _ = Property.objects.get_or_create(
        apartment_number='1',
        building=building,
        defaults={
            'decoration': decoration,
            'layout': layout,
            'area': Decimal('52.40'),
            'floor': 8,
            'property_cost': Decimal('5000000.00'),
        },
    )
    return property_object


def seed_acceptance_fixtures():
    """Seed test accounts and records without exposing generated passwords."""
    ensure_isolated_database()
    password = os.environ.get('BROWSER_TEST_ACCOUNT_PASSWORD', '')
    if len(password) < 24:
        raise RuntimeError('Generate an acceptance account password of 24+ characters')

    from django.contrib.auth.models import Group

    from bank.models import Bank, MortgageProgram
    from customer.models import Customer
    from location.models import MetroLine
    from property.models import CompanyGroup, Developer
    from users.roles import MODERATOR_GROUP_NAME

    with transaction.atomic():
        user_model = get_user_model()
        moderator_group, _ = Group.objects.get_or_create(name=MODERATOR_GROUP_NAME)
        accounts = {}
        for account_index, role in enumerate(('moderator', 'owner', 'other'), start=1):
            user, _ = user_model.objects.get_or_create(
                email=f'{role}@react-browser.invalid',
                defaults={
                    'phone_number': f'+7999000800{account_index}',
                    'first_name': 'E2E',
                    'last_name': role,
                },
            )
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            user.set_password(password)
            user.save()
            user.groups.set([moderator_group] if role == 'moderator' else [])
            accounts[role] = {'id': user.pk, 'email': user.email}

        other_customer, _ = Customer.objects.get_or_create(
            user_id=accounts['other']['id'],
            first_name='E2E закрытый клиент',
            defaults={'comment': 'Synthetic private acceptance record'},
        )
        property_object = create_property_fixture()
        mortgage_program, _ = MortgageProgram.objects.get_or_create(
            name='E2E ипотечная программа',
            defaults={'condition': 'Synthetic browser acceptance conditions'},
        )
        MortgageProgram.objects.get_or_create(
            name='Рыночная ипотека',
            defaults={'condition': 'Synthetic market import conditions'},
        )
        company_group, _ = CompanyGroup.objects.get_or_create(name='E2E группа')
        real_estate_complex = property_object.building.real_estate_complex
        Developer.objects.filter(pk=real_estate_complex.developer_id).update(
            company_group=company_group,
        )
        bank, _ = Bank.objects.get_or_create(name='E2E банк')
        metro_line, _ = MetroLine.objects.get_or_create(
            line='E2E линия',
            city=real_estate_complex.district.city,
            defaults={'line_color': '#336699'},
        )
        return {
            'databaseName': DATABASE_NAME,
            'isolated': True,
            'accounts': accounts,
            'otherCustomerId': other_customer.pk,
            'propertyId': property_object.pk,
            'mortgageProgramId': mortgage_program.pk,
            'companyGroupId': company_group.pk,
            'bankId': bank.pk,
            'complexId': real_estate_complex.pk,
            'metroLineId': metro_line.pk,
        }


def main():
    """Initialize Django and print the non-secret fixture manifest."""
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE', 'real_estate_investing.settings',
    )
    django.setup()
    print(json.dumps(seed_acceptance_fixtures()))


if __name__ == '__main__':
    main()
