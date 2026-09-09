import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Overview } from '@/api/schemas'
import { renderWithProviders, createTestQueryClient } from '@/test/render'

import { HomePage } from './HomePage'

const overview: Overview = {
  statistics: [
    { key: 'properties', label: 'Объекты', value: 24 },
    { key: 'complexes', label: 'Жилые комплексы', value: 7 },
  ],
  recentProperties: [
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

describe('HomePage', () => {
  it('renders summary data and recent property actions', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['overview'], overview)

    renderWithProviders(<HomePage />, { queryClient })

    expect(
      screen.getByRole('heading', {
        name: 'Инвестиции в недвижимость — в единой системе',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('24')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Белые ночи' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть объект' })).toHaveAttribute(
      'href',
      '/property/1/',
    )
  })

  it('renders a deliberate empty state', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['overview'], {
      ...overview,
      recentProperties: [],
    })

    renderWithProviders(<HomePage />, { queryClient })

    expect(screen.getByRole('heading', { name: 'Объектов пока нет' })).toBeInTheDocument()
  })
})
