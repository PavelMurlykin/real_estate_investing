import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type {
  RealEstateComplexListResponse,
  RealEstateComplexOptions,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { RealEstateComplexListPage } from './RealEstateComplexListPage'

const directory: RealEstateComplexListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [{
    id: 7,
    name: 'Белые ночи',
    developer: {
      id: 4,
      name: 'Северный девелопер',
      label: 'Северный девелопер (Группа Север)',
    },
    city: 'Санкт-Петербург',
    realEstateClass: 'Бизнес',
    realEstateType: 'Квартира',
    buildingCount: 3,
    isActive: true,
  }],
}

const options: RealEstateComplexOptions = {
  regions: [{ id: 1, name: 'Ленинградская область' }],
  cities: [{ id: 2, name: 'Санкт-Петербург' }],
  districts: [],
  developers: [{ id: 4, label: 'Северный девелопер (Группа Север)' }],
  realEstateClasses: [{ id: 5, name: 'Бизнес' }],
  realEstateTypes: [{ id: 6, name: 'Квартира' }],
  transportAccessibilityTypes: [{ id: 8, name: 'Пешком' }],
  metroStations: [],
  quarters: [
    { value: 1, label: 'I кв.' },
    { value: 2, label: 'II кв.' },
    { value: 3, label: 'III кв.' },
    { value: 4, label: 'IV кв.' },
  ],
  truncated: {
    regions: false,
    cities: false,
    districts: false,
    developers: false,
    realEstateClasses: false,
    realEstateTypes: false,
    transportAccessibilityTypes: false,
    metroStations: false,
  },
}

const managerSession: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Модератор',
    email: 'moderator@example.com',
    agencyName: '',
  },
  capabilities: {
    manageCatalogs: true,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

function createDirectoryQueryClient(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['real-estate-complexes', ''], directory)
  queryClient.setQueryData(['real-estate-complex-options', ''], options)
  if (session) queryClient.setQueryData(['session'], session)
  return queryClient
}

describe('RealEstateComplexListPage', () => {
  it('renders a public responsive directory with a React detail route', () => {
    renderWithProviders(<RealEstateComplexListPage />, {
      queryClient: createDirectoryQueryClient(),
    })

    expect(screen.getByRole('heading', { name: 'Жилые комплексы' }))
      .toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'Список жилых комплексов',
    )
    expect(screen.getAllByRole('link', { name: 'Белые ночи' })[0])
      .toHaveAttribute('href', '/complexes/7')
    expect(screen.queryByRole('link', { name: 'Добавить ЖК' }))
      .not.toBeInTheDocument()
  })

  it('keeps filters in URL state and requests the selected city', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(directory), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RealEstateComplexListPage />, {
      queryClient: createDirectoryQueryClient(),
    })

    await user.selectOptions(screen.getByLabelText('Город'), '2')

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/complexes/?cityId=2',
      expect.objectContaining({ credentials: 'same-origin' }),
    ))
  })

  it('allows managers to delete only after explicit confirmation', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn<typeof fetch>((_input, requestOptions) => {
      if (requestOptions?.method === 'DELETE') {
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      return Promise.resolve(new Response(JSON.stringify({
        ...directory,
        totalCount: 0,
        totalPages: 0,
        results: [],
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<RealEstateComplexListPage />, {
      queryClient: createDirectoryQueryClient(managerSession),
    })

    await user.click(screen.getByRole('button', { name: 'Удалить: Белые ночи' }))
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('Удалить жилой комплекс?')
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog'))
      .not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/complexes/7/',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})
