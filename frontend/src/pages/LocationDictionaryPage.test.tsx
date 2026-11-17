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

const metroEntry: LocationDictionaryEntry = {
  id: 5,
  name: 'Охотный Ряд',
  code: null,
  region: { id: 1, name: 'Москва' },
  city: { id: 2, name: 'Москва' },
  system: { id: 9, name: 'Московский метрополитен' },
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
  }, {
    id: 7,
    name: 'Арбатско-Покровская',
    color: '#0078BF',
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
  if (entry.region) {
    queryClient.setQueryData(['location-dictionary-options', 'regionId=1'], {
      ...options, metroLines: [],
    })
  }
  if (entry.city) {
    queryClient.setQueryData(['location-dictionary-options', 'regionId=1&cityId=2'], options)
  }
  queryClient.setQueryData(['location-dictionary', dictionaryKey, entry.id], entry)
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
  it('shows external import only for application administrators', () => {
    renderLocationPage('metro', metroEntry, {
      ...managerSession,
      capabilities: { ...managerSession.capabilities, syncExternalData: true },
    })
    expect(screen.getByRole('button', { name: 'Импортировать из API' })).toBeInTheDocument()
  })

  it('hides external import from catalog moderators', () => {
    renderLocationPage('metro', metroEntry, managerSession)
    expect(screen.queryByRole('button', { name: 'Импортировать из API' })).not.toBeInTheDocument()
  })
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
    expect(screen.getByRole('link', { name: '© OpenStreetMap contributors, ODbL' }))
      .toHaveAttribute('href', 'https://www.openstreetmap.org/copyright')
    expect(screen.getByRole('link', { name: 'Метро' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: 'Административные районы' })).toHaveAttribute(
      'href',
      '/locations/districts',
    )
    const table = within(screen.getByRole('table', { name: 'Метро' }))
    expect(table.getAllByRole('columnheader')).toHaveLength(4)
    expect(table.getByRole('columnheader', { name: 'Территория' })).toBeInTheDocument()
    expect(table.queryByRole('columnheader', { name: 'Регион' })).not.toBeInTheDocument()
    expect(table.queryByRole('columnheader', { name: 'Используется' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Прежняя версия' })).not.toBeInTheDocument()
    expect(screen.getAllByText('Охотный Ряд').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Сокольническая').length).toBeGreaterThan(0)
    expect(screen.getByRole('combobox', { name: 'Система метро' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Сохранить' }))
      .not.toBeInTheDocument()
  })

  it.each(['POST', 'PATCH'])('selects a station line through a searchable editor and saves with %s', async (method) => {
    const user = userEvent.setup()
    const isEditing = method === 'PATCH'
    const line = options.metroLines[1]
    const fetchMock = vi.fn<typeof fetch>(async (input, requestOptions) => {
      if (requestOptions?.method === method) {
        return Response.json({ ...metroEntry, metroLine: line, name: 'Тестовая станция' }, {
          status: isEditing ? 200 : 201,
        })
      }
      const path = String(input)
      if (path.includes('/catalog-options/')) {
        const choices = path.includes('/metro-systems/') ? [{ id: 9, name: 'Московский метрополитен' }]
          : path.includes('/regions/') ? options.regions
          : path.includes('/cities/') ? options.cities : options.metroLines
        return Response.json({ page: 1, nextPage: null, totalCount: choices.length,
          selected: [], results: choices.map((choice) => ({ id: choice.id, label: choice.name })),
        })
      }
      return Response.json(listResponse(metroEntry))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderLocationPage('metro', metroEntry, managerSession, isEditing ? '/locations/metro/5/edit' : '/locations/metro')

    const editor = within(screen.getByRole('complementary', {
      name: isEditing ? 'Редактирование записи' : 'Добавить станцию',
    }))
    const system = editor.getByRole('combobox', { name: 'Система метро *' })
    const metroLine = editor.getByRole('combobox', { name: 'Линия метро *' })
    expect(editor.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(editor.queryByRole('link', { name: 'Django-форма' })).not.toBeInTheDocument()
    if (isEditing) {
      expect(metroLine).toHaveValue('Сокольническая')
    } else {
      expect(metroLine).toBeDisabled()
    }
    if (!isEditing) {
      await user.click(system)
      await user.click(await editor.findByRole('option', { name: 'Московский метрополитен' }))
    }
    await user.click(metroLine)
    await user.type(metroLine, 'Арбат')
    await user.click(await editor.findByRole('option', { name: line.name }))
    expect(metroLine).toHaveValue(line.name)
    const name = editor.getByLabelText('Название станции *')
    await user.clear(name)
    await user.type(name, 'Тестовая станция')
    await user.click(editor.getByRole('button', { name: 'Сохранить' }))

    const path = isEditing ? '/api/v1/location-dictionaries/metro/5/' : '/api/v1/location-dictionaries/metro/'
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(path, expect.objectContaining({ method })))
    const saveCall = fetchMock.mock.calls.find((call) => call[1]?.method === method)
    expect(JSON.parse(saveCall?.[1]?.body as string)).toEqual({
      name: 'Тестовая станция', isActive: true, metroLineId: line.id,
      lineIds: [], locationId: null, locationIsInferred: true,
    })
  })

})
