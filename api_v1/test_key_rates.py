from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from bank import key_rate_sync
from bank.key_rate_sync import KeyRateSyncError
from bank.models import KeyRate


@pytest.fixture
def key_rate_history(db):
    """Create chronological key rates including one inactive newest row."""
    oldest_rate = KeyRate.objects.create(
        meeting_date=date(2026, 1, 1),
        key_rate=Decimal('10.00'),
    )
    current_rate = KeyRate.objects.create(
        meeting_date=date(2026, 2, 1),
        key_rate=Decimal('12.00'),
    )
    inactive_rate = KeyRate.objects.create(
        meeting_date=date(2026, 3, 1),
        key_rate=Decimal('11.00'),
        is_active=False,
    )
    return {
        'oldest': oldest_rate,
        'current': current_rate,
        'inactive': inactive_rate,
    }


def create_administrator():
    """Create a user allowed to synchronize external source data."""
    return get_user_model().objects.create_superuser(
        email='key-rate-admin@example.com',
        password='safe-test-password',
        phone_number='+79990000231',
    )


@pytest.mark.django_db
def test_key_rate_list_is_public_paginated_and_query_efficient(
    client,
    key_rate_history,
    django_assert_num_queries,
):
    """Return rate deltas and current-rate metadata in four queries."""
    with django_assert_num_queries(4):
        response = client.get(
            reverse('api_v1:key_rate_list'),
            {'pageSize': 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['page'] == 1
    assert payload['pageSize'] == 2
    assert payload['totalCount'] == 3
    assert payload['totalPages'] == 2
    assert payload['currentRate'] == {
        'meetingDate': '2026-02-01',
        'keyRate': '12.00',
    }
    assert payload['lastSyncedAt'] is not None
    assert payload['legacyUrl'] == '/bank/key-rate/'
    assert payload['results'][0] == {
        'id': key_rate_history['inactive'].pk,
        'meetingDate': '2026-03-01',
        'keyRate': '11.00',
        'rateChange': '-1.00',
        'isActive': False,
        'updatedAt': payload['results'][0]['updatedAt'],
    }
    assert payload['results'][1]['id'] == key_rate_history['current'].pk
    assert payload['results'][1]['rateChange'] == '2.00'


@pytest.mark.django_db
def test_key_rate_list_validates_page_size(client):
    """Reject an unbounded key-rate page request."""
    response = client.get(
        reverse('api_v1:key_rate_list'),
        {'pageSize': 101},
    )

    assert response.status_code == 400
    assert 'pageSize' in response.json()


@pytest.mark.django_db
def test_key_rate_sync_requires_administrator(client, key_rate_history):
    """Reject external synchronization from a regular authenticated user."""
    regular_user = get_user_model().objects.create_user(
        email='key-rate-user@example.com',
        password='safe-test-password',
        phone_number='+79990000232',
    )
    client.force_login(regular_user)

    with patch('api_v1.views.sync_key_rates') as sync_mock:
        response = client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 403
    sync_mock.assert_not_called()


@pytest.mark.django_db
def test_administrator_can_synchronize_key_rates(client, key_rate_history):
    """Return synchronization counts and the active current rate."""
    client.force_login(create_administrator())

    with patch(
        'api_v1.views.sync_key_rates',
        return_value={'created': 2, 'updated': 1, 'processed': 8},
    ) as sync_mock:
        response = client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 200
    assert response.json()['created'] == 2
    assert response.json()['updated'] == 1
    assert response.json()['processed'] == 8
    assert response.json()['currentRate']['keyRate'] == '12.00'
    assert response.json()['synchronizedAt']
    sync_mock.assert_called_once_with()


@pytest.mark.django_db
def test_key_rate_sync_returns_source_failure(client):
    """Represent a controlled source error without changing Django pages."""
    client.force_login(create_administrator())

    with patch(
        'api_v1.views.sync_key_rates',
        side_effect=KeyRateSyncError('Сервис недоступен'),
    ):
        response = client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 502
    assert response.json() == {
        'detail': (
            'Не удалось обновить данные ключевой ставки: Сервис недоступен'
        )
    }


@pytest.mark.django_db
def test_key_rate_sync_preserves_csrf_protection():
    """Reject an administrator POST without a CSRF token when checks apply."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(create_administrator())

    response = csrf_client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 403


@pytest.mark.django_db
def test_key_rate_chart_returns_the_full_chronological_series(
    client, key_rate_history, django_assert_num_queries,
):
    """Load chart points in one query, independent of the table page."""
    with django_assert_num_queries(1):
        response = client.get(reverse('api_v1:key_rate_chart'), {'page': 2})

    assert response.status_code == 200
    assert response.json() == [
        {'meetingDate': '2026-01-01', 'keyRate': '10.00'},
        {'meetingDate': '2026-02-01', 'keyRate': '12.00'},
        {'meetingDate': '2026-03-01', 'keyRate': '11.00'},
    ]


def test_archive_reads_an_older_decision_from_the_release_body(monkeypatch):
    """Read retention from the article when its title is generic."""
    archive_html = '''
        <div id="tab_content_t1">
          <div class="previews_item-title">
            <a href="/press/pr/?file=131213_133004stavka_table.htm">
              О&#160;ключевой ставке Банка России</a>
          </div>
        </div>
    '''
    release_html = '''
        <p>Совет директоров Банка России принял решение сохранить
          <u>ключевую ставку</u> на&nbsp;уровне 5,50% годовых.</p>
    '''
    source_pages = {
        key_rate_sync.CBR_DECISIONS_URL: archive_html,
        f'{key_rate_sync.CBR_ORIGIN}/press/pr/?file=131213_133004stavka_table.htm':
            release_html,
    }
    monkeypatch.setattr(key_rate_sync, '_download_cbr_html', source_pages.__getitem__)

    assert key_rate_sync._download_unchanged_decisions(
        date(2013, 9, 17), date(2013, 12, 31),
    ) == {date(2013, 12, 13): Decimal('5.50')}


@pytest.mark.django_db
def test_sync_adds_confirmed_unchanged_decisions_without_duplicates(
    client, monkeypatch,
):
    """Import retained rates through the same POST used by the button."""
    KeyRate.objects.create(
        meeting_date=date(2026, 7, 27), key_rate=Decimal('14.00'),
    )
    client.force_login(create_administrator())
    monkeypatch.setattr(
        key_rate_sync.timezone, 'localdate', lambda: date(2026, 11, 5),
    )
    daily_html = """
        <tr><td>05.11.2026</td><td>14,00</td></tr>
        <tr><td>23.10.2026</td><td>14,00</td></tr>
        <tr><td>11.09.2026</td><td>14,00</td></tr>
        <tr><td>27.07.2026</td><td>14,00</td></tr>
        <tr><td>24.07.2026</td><td>14,25</td></tr>
        <tr><td>22.06.2026</td><td>14,25</td></tr>
    """
    archive_html = """
        <div role="tabpanel" id="tab_content_t1">
          <div class="previews_item-title">
            <a href="/press/pr/?file=23102026_133000key.htm">
              Банк России принял решение сохранить ключевую ставку
              на&#160;уровне 14,00% годовых</a>
          </div>
          <button data-cross-ajax-url="/Crosscut/NewsList/LoadMore/84035?intOffset=0&amp;extOffset=10">
          </button>
        </div>
        <div role="tabpanel" id="tab_content_t3"></div>
    """
    archive_page_html = """
        <div class="previews_item-title">
          <a href="/press/pr/?file=11092026_133000key.htm">
            Банк России принял решение сохранить ключевую ставку
            на&nbsp;уровне 14,00% годовых</a>
        </div>
        <div class="previews_item-title">
          <a href="/press/pr/?file=24072026_133000key.htm">
            Банк России принял решение снизить ключевую ставку до 14,00% годовых
          </a>
        </div>
    """
    archive_page_url = (
        f'{key_rate_sync.CBR_ORIGIN}/Crosscut/NewsList/LoadMore/84035'
        '?intOffset=0&extOffset=10'
    )

    def download_source(url):
        """Serve the daily table and both archive pages by URL."""
        if url.startswith(f'{key_rate_sync.CBR_KEY_RATE_URL}?'):
            return daily_html
        return {
            key_rate_sync.CBR_DECISIONS_URL: archive_html,
            archive_page_url: archive_page_html,
        }[url]

    monkeypatch.setattr(key_rate_sync, '_download_cbr_html', download_source)
    sync_url = reverse('api_v1:key_rate_sync')
    first_response = client.post(sync_url)
    second_response = client.post(sync_url)
    history_response = client.get(reverse('api_v1:key_rate_list'))

    assert first_response.status_code == second_response.status_code == 200
    assert first_response.json()['created'] == 3
    assert second_response.json()['created'] == 0
    assert second_response.json()['updated'] == 0
    assert [
        (row['meetingDate'], row['keyRate'], row['rateChange'])
        for row in history_response.json()['results']
    ] == [
        ('2026-10-23', '14.00', '0.00'),
        ('2026-09-11', '14.00', '0.00'),
        ('2026-07-27', '14.00', '-0.25'),
        ('2026-06-22', '14.25', None),
    ]
