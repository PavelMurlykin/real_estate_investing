import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type {
  LocationDictionaryEntry,
  LocationDictionaryListResponse,
  LocationDictionaryOptions,
  LocationDictionaryKey,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { LocationDictionaryPage } from './LocationDictionaryPage'

const regionEntry: LocationDictionaryEntry = {
  id: 1,
  name: 'Москва',
  code: '77',
  region: null,
  city: null,
  metroLine: null,
  usageCount: 4,
  isActive: true,
  createdAt: '2026-09-10T10:00:00+03:00',
  updatedAt: '2026-09-11T10:00:00+03:00',
  legacyEditUrl: '/locations/?model=region&edit=1',
}

const districtEntry: LocationDictionaryEntry = {
  id: 4,
  name: 'Центральный',
  code: null,
  region: { id: 1, name: 'Москва' },
  city: { id: 2, name: 'Москва' },
  metroLine: null,
  usageCount: 1,
  isActive: true,
  createdAt: '2026-09-10T10:00:00+03:00',
  updatedAt: '2026-09-11T10:00:00+03:00',
  legacyEditUrl: '/locations/?model=district&edit=4',
}

const metroEntry: LocationDictionaryEntry = {
  id: 5,
  name: 'Охотный Ряд',
  code: null,
  region: { id: 1, name: 'Москва' },
  city: { id: 2, name: 'Москва' },
  metroLine: {
    id: 3,
    name: 'Сокольническая',
    color: '#D92B2B',
  },
  usageCount: 2,
  isActive: true,
  createdAt: '2026-09-10T10:00:00+03:00',
  updatedAt: '2026-09-11T10:00:00+03:00',
  legacyEditUrl: '/locations/?model=metro&edit=5',
}

const options: LocationDictionaryOptions = {
  regions: [{ id: 1, name: 'Москва' }],
  cities: [{ id: 2, name: 'Москва', regionId: 1 }],
  metroLines: [{
    id: 3,
    name: 'Сокольническая',
    color: '#D92B2B',
    cityId: 2,
  }],
  truncated: {
    regions: false,
    cities: false,
    metroLines: false,
  },
}

const rootOptions: LocationDictionaryOptions = {
  ...options,
  cities: [],
  metroLines: [],
}

const anonymousSession: Session = {
  isAuthenticated: false,
  user: null,
  capabilities: {
    manageCatalogs: false,
    syncExternalData: false,
    viewPrivateRecords: false,
    viewAllPrivateRecords: false,
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

function listResponse(
  entry: LocationDictionaryEntry,
): LocationDictionaryListResponse {
  return {
    page: 1,
    pageSize: 20,
    totalCount: 1,
    totalPages: 1,
    results: [entry],
  }
}

function renderLocationPage(
  dictionaryKey: LocationDictionaryKey,
  entry: LocationDictionaryEntry,
  session: Session = anonymousSession,
  initialRoute = `/locations/${dictionaryKey}`,
) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], session)
  queryClient.setQueryData(
    ['location-dictionaries', dictionaryKey, ''],
    listResponse(entry),
  )
  queryClient.setQueryData(['location-dictionary-options', ''], rootOptions)
  return renderWithProviders(
    <Routes>
      <Route
        path="/locations/:dictionaryKey"
        element={<LocationDictionaryPage />}
      />
      <Route
        path="/locations/:dictionaryKey/:entryId/edit"
        element={<LocationDictionaryPage />}
      />
    </Routes>,
    { initialRoute, queryClient },
  )
}

describe('LocationDictionaryPage', () => {
  it('renders the public metro hierarchy and all location tabs', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], anonymousSession)
    queryClient.setQueryData(
      [
        'location-dictionaries',
        'metro',
        'regionId=1&cityId=2&metroLineId=3',
      ],
      listResponse(metroEntry),
    )
    queryClient.setQueryData(
      ['location-dictionary-options', 'regionId=1&cityId=2'],
      options,
    )
    renderWithProviders(
      <Routes>
        <Route
          path="/locations/:dictionaryKey"
          element={<LocationDictionaryPage />}
        />
      </Routes>,
      {
        initialRoute: '/locations/metro?regionId=1&cityId=2&metroLineId=3',
        queryClient,
      },
    )

    expect(screen.getByRole('heading', { name: 'Локации' }))
      .toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Метро' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: 'Районы' })).toHaveAttribute(
      'href',
      '/locations/districts',
    )
    expect(screen.getByRole('table')).toHaveAccessibleName('Метро')
    expect(screen.getAllByText('Охотный Ряд').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Сокольническая').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Регион')).toHaveValue('1')
    expect(screen.getByLabelText('Город')).toHaveValue('2')
    expect(screen.getByLabelText('Линия метро')).toHaveValue('3')
    expect(screen.queryByRole('button', { name: 'Сохранить' }))
      .not.toBeInTheDocument()
  })

  it('creates a normalized region through the authoritative API', async () => {
    const user = userEvent.setup()
    const createdEntry = {
      ...regionEntry,
      id: 6,
      name: 'Тверская область',
      code: 'TV',
      usageCount: 0,
    }
    const fetchMock = vi.fn<typeof fetch>((_input, requestOptions) => {
      if (requestOptions?.method === 'POST') {
        return Promise.resolve(new Response(JSON.stringify(createdEntry), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.resolve(new Response(JSON.stringify(
        listResponse(regionEntry),
      ), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderLocationPage('regions', regionEntry, managerSession)

    await user.type(
      screen.getByLabelText('Название региона *'),
      '  Тверская область  ',
    )
    await user.type(screen.getByLabelText('Код региона *'), ' tv ')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(
      screen.getByLabelText('Название региона *'),
    ).toHaveValue(''))
    const postCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === 'POST',
    )
    expect(postCall?.[0]).toBe(
      '/api/v1/location-dictionaries/regions/',
    )
    expect(JSON.parse(postCall?.[1]?.body as string)).toEqual({
      name: 'Тверская область',
      code: 'tv',
      isActive: true,
    })
  })

  it('prefills and updates a nested district with the Django fallback', async () => {
    const user = userEvent.setup()
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], managerSession)
    queryClient.setQueryData(
      ['location-dictionaries', 'districts', ''],
      listResponse(districtEntry),
    )
    queryClient.setQueryData(['location-dictionary-options', ''], rootOptions)
    queryClient.setQueryData(
      ['location-dictionary-options', 'regionId=1&cityId=2'],
      options,
    )
    queryClient.setQueryData(
      ['location-dictionary', 'districts', 4],
      districtEntry,
    )
    const fetchMock = vi.fn<typeof fetch>((_input, requestOptions) => {
      if (requestOptions?.method === 'PATCH') {
        return Promise.resolve(new Response(JSON.stringify({
          ...districtEntry,
          name: 'Центральный округ',
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.resolve(new Response(JSON.stringify(
        listResponse(districtEntry),
      ), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route
          path="/locations/:dictionaryKey"
          element={<LocationDictionaryPage />}
        />
        <Route
          path="/locations/:dictionaryKey/:entryId/edit"
          element={<LocationDictionaryPage />}
        />
      </Routes>,
      {
        initialRoute: '/locations/districts/4/edit',
        queryClient,
      },
    )

    const nameInput = await screen.findByLabelText('Название района *')
    expect(nameInput).toHaveValue('Центральный')
    expect(screen.getByLabelText('Регион *')).toHaveValue('1')
    expect(screen.getByLabelText('Город *')).toHaveValue('2')
    expect(screen.getByRole('link', { name: 'Django-форма' }))
      .toHaveAttribute('href', districtEntry.legacyEditUrl)
    await user.clear(nameInput)
    await user.type(nameInput, 'Центральный округ')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/location-dictionaries/districts/4/',
      expect.objectContaining({ method: 'PATCH' }),
    ))
    const patchCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === 'PATCH',
    )
    expect(JSON.parse(patchCall?.[1]?.body as string)).toMatchObject({
      name: 'Центральный округ',
      cityId: 2,
    })
  })

  it('keeps a protected location after an accessible delete conflict', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Локация используется.' }),
      {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      },
    )))
    renderLocationPage('regions', regionEntry, managerSession)

    const deleteButtons = screen.getAllByRole('button', {
      name: 'Удалить: Москва',
    })
    expect(deleteButtons).toHaveLength(2)
    await user.click(deleteButtons[0])
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('Удалить локацию?')
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Локация используется в других разделах',
    )
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  })
})
