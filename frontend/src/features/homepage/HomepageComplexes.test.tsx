import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { HomepageComplex } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { HomepageComplexes } from './HomepageComplexes'

vi.mock('./ComplexMap', () => ({ default: ({ city }: { city: string }) => <div role="region" aria-label={`Карта ЖК: ${city}`} /> }))

const complex: HomepageComplex = {
  id: 1, name: 'ЖК Петербург', developer: { id: 2, name: 'Застройщик', label: 'Застройщик (Группа)' },
  city: 'Санкт-Петербург', district: 'Приморский', realEstateClass: 'Комфорт', realEstateType: 'Квартира',
  description: 'Описание локации', photoUrl: '/media/complex.jpg', mapUrl: 'https://yandex.ru/maps/?ll=30.3,59.9',
  presentationUrl: null, isActive: true, buildingCount: 2,
}
const firstPage = { selectedCity: { id: 7, name: 'Санкт-Петербург' }, page: 1, pageSize: 50, totalCount: 2, totalPages: 2, results: [complex] }

function Address() { return <output aria-label="Адрес">{useLocation().search}</output> }

function renderComplexes() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['homepage-complexes', '7'], { pages: [firstPage], pageParams: [1] })
  return renderWithProviders(<><HomepageComplexes /><Address /></>, { queryClient, initialRoute: '/?city=7' })
}

describe('HomepageComplexes', () => {
  it('shows the legacy card fields and loads later city records', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...firstPage, page: 2,
      results: [{ ...complex, id: 3, name: 'Второй ЖК' }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    renderComplexes()
    expect(screen.getByRole('img', { name: 'ЖК Петербург' })).toHaveAttribute('src', '/media/complex.jpg')
    expect(screen.getByText('Приморский')).toBeInTheDocument()
    expect(screen.getByText('Описание локации')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Объекты ЖК' })).toHaveAttribute('href', '/properties?realEstateComplex=1')
    await user.click(screen.getByRole('button', { name: 'Показать ещё ЖК' }))
    expect(await screen.findByRole('heading', { name: 'Второй ЖК' })).toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toContain('page=2')
    expect(screen.queryByRole('button', { name: 'Показать ещё ЖК' })).not.toBeInTheDocument()
  })

  it('retains map mode in the URL when switching cities', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockImplementation(async (path: string) => new Response(JSON.stringify(path.includes('/catalog-options/') ? {
      results: [{ id: 8, label: 'Москва' }], selected: [{ id: 7, label: 'Санкт-Петербург' }], page: 1, nextPage: null, totalCount: 1,
    } : { ...firstPage, selectedCity: { id: 8, name: 'Москва' }, totalCount: 1, totalPages: 1,
      results: [{ ...complex, id: 8, name: 'ЖК Москва', city: 'Москва' }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    renderComplexes()
    await user.click(screen.getByRole('button', { name: 'На карте' }))
    expect(await screen.findByRole('region', { name: 'Карта ЖК: Санкт-Петербург' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Поиск: Город на главной'), 'Москва')
    await user.selectOptions(screen.getByLabelText('Город на главной'), await screen.findByRole('option', { name: 'Москва' }))
    expect(await screen.findByRole('heading', { name: 'ЖК Москва' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('region', { name: 'Карта ЖК: Москва' })).toBeInTheDocument())
    const parameters = new URLSearchParams(screen.getByLabelText('Адрес').textContent ?? '')
    expect(parameters.get('city')).toBe('8')
    expect(parameters.get('view')).toBe('map')
  })
})
