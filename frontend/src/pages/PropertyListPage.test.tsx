import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { PropertyListResponse } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { PropertyListPage } from './PropertyListPage'

const propertyList: PropertyListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      id: 1,
      city: 'Санкт-Петербург',
      developer: 'Северный девелопер',
      realEstateComplex: 'Белые ночи',
      building: '1',
      apartmentNumber: '101',
      layout: 'Евродвушка',
      decoration: 'Чистовая',
      area: '42.50',
      floor: 10,
      propertyCost: '12500000.00',
      detailUrl: '/property/1/',
    },
  ],
}

describe('PropertyListPage', () => {
  it('renders the paginated property contract in desktop and mobile views', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['properties', ''], propertyList)

    renderWithProviders(<PropertyListPage />, { queryClient })

    expect(screen.getByRole('heading', { name: 'Объекты недвижимости' })).toBeInTheDocument()
    expect(screen.getByText('Северный девелопер')).toBeInTheDocument()
    expect(screen.getAllByText('Белые ночи')).toHaveLength(2)
    expect(
      screen.getAllByText(
        (_, element) =>
          element?.textContent?.replace(/\s/g, '') === '12500000₽',
        { selector: 'strong' },
      ),
    ).toHaveLength(2)
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'Список объектов недвижимости',
    )
    expect(
      screen.getAllByRole('link', { name: /Открыть квартиру 101/ })[0],
    ).toHaveAttribute('href', '/properties/1')
    expect(
      screen.getAllByRole('link', { name: /Рассчитать ипотеку/ })[0],
    ).toHaveAttribute(
      'href',
      '/mortgage?propertyId=1&propertyCost=12500000.00',
    )
  })

  it('shows an empty state with a reset action', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['properties', 'search=unknown'], {
      ...propertyList,
      totalCount: 0,
      totalPages: 0,
      results: [],
    })

    renderWithProviders(<PropertyListPage />, {
      initialRoute: '/?search=unknown',
      queryClient,
    })

    expect(
      screen.getByRole('heading', {
        name: 'По вашему запросу ничего не найдено',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Сбросить фильтры' })).toBeInTheDocument()
  })

  it('preserves the customer context in property and mortgage links', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['properties', ''], propertyList)

    renderWithProviders(<PropertyListPage />, {
      initialRoute: '/?customerId=12',
      queryClient,
    })

    expect(screen.getByRole('link', { name: 'К карточке клиента' }))
      .toHaveAttribute('href', '/customers/12')
    expect(
      screen.getAllByRole('link', { name: /Открыть квартиру 101/ })[0],
    ).toHaveAttribute('href', '/properties/1?customerId=12')
    expect(
      screen.getAllByRole('link', { name: /Рассчитать ипотеку/ })[0],
    ).toHaveAttribute(
      'href',
      '/mortgage?propertyId=1&propertyCost=12500000.00&customerId=12',
    )
  })
})
