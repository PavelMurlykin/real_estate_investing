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

const cityEntry: LocationDictionaryEntry = {
  ...regionEntry,
  id: 2,
  code: null,
  region: { id: 1, name: 'Москва' },
  legacyEditUrl: '/locations/?model=city&edit=2',
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
    const table = within(screen.getByRole('table', { name: 'Метро' }))
    expect(table.getAllByRole('columnheader')).toHaveLength(3)
    expect(table.getByRole('columnheader', { name: 'Город' })).toBeInTheDocument()
    expect(table.queryByRole('columnheader', { name: 'Регион' })).not.toBeInTheDocument()
    expect(table.queryByRole('columnheader', { name: 'Используется' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Прежняя версия' })).not.toBeInTheDocument()
    expect(screen.getAllByText('Охотный Ряд').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Сокольническая').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Регион')).toHaveValue('Москва')
    expect(screen.getByLabelText('Город')).toHaveValue('Москва')
    expect(screen.getByLabelText('Линия метро')).toHaveValue('Сокольническая')
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
        const choices = path.includes('/regions/') ? options.regions
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
    const region = editor.getByRole('combobox', { name: 'Регион *' })
    const city = editor.getByRole('combobox', { name: 'Город *' })
    const metroLine = editor.getByRole('combobox', { name: 'Линия метро *' })
    expect(editor.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(editor.queryByRole('link', { name: 'Django-форма' })).not.toBeInTheDocument()
    if (isEditing) {
      expect(metroLine).toHaveValue('Сокольническая')
    } else {
      expect(city).toBeDisabled()
      expect(metroLine).toBeDisabled()
    }
    await user.click(region)
    await user.click(editor.getByRole('option', { name: 'Москва' }))
    await user.click(city)
    await user.click(editor.getByRole('option', { name: 'Москва' }))
    if (isEditing) expect(metroLine).toHaveValue('Сокольническая')
    await user.click(metroLine)
    await user.type(metroLine, 'Арбат')
    expect(editor.queryByRole('option', { name: 'Сокольническая' })).not.toBeInTheDocument()
    await user.keyboard('{Enter}')
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
    })
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

    expect(screen.queryByText('Используется', { exact: true })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Прежняя версия' })).not.toBeInTheDocument()
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

  it.each([
    { dictionaryKey: 'cities', entry: cityEntry, nameLabel: 'Название города *', parent: { regionId: 1 } },
    { dictionaryKey: 'districts', entry: districtEntry, nameLabel: 'Название района *', parent: { cityId: 2 } },
  ] as const)('prefills and updates $dictionaryKey through searchable fields', async ({
    dictionaryKey, entry, nameLabel, parent,
  }) => {
    const user = userEvent.setup()
    const updatedName = `${entry.name} тест`
    const fetchMock = vi.fn<typeof fetch>(async (input, requestOptions) => {
      if (requestOptions?.method === 'PATCH') {
        return Response.json({ ...entry, name: updatedName })
      }
      const path = String(input)
      if (path.includes('/catalog-options/')) {
        const choices = path.includes('/regions/') ? options.regions : options.cities
        return Response.json({ page: 1, nextPage: null, totalCount: choices.length,
          selected: [], results: choices.map(({ id, name }) => ({ id, label: name })),
        })
      }
      return Response.json(listResponse(entry))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderLocationPage(dictionaryKey, entry, managerSession, `/locations/${dictionaryKey}/${entry.id}/edit`)

    const editor = within(screen.getByRole('complementary', { name: 'Редактирование записи' }))
    const region = editor.getByRole('combobox', { name: 'Регион *' })
    expect(region).toHaveValue('Москва')
    expect(editor.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Прежняя версия' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Django-форма' })).not.toBeInTheDocument()
    expect(screen.queryByText('Используется', { exact: true })).not.toBeInTheDocument()
    await user.click(region)
    await user.clear(region)
    await user.type(region, 'Моск')
    await user.click(editor.getByRole('option', { name: 'Москва' }))
    if (dictionaryKey === 'districts') {
      expect(editor.getByRole('combobox', { name: 'Город *' })).toHaveValue('Москва')
    }
    const nameInput = editor.getByLabelText(nameLabel)
    expect(nameInput).toHaveValue(entry.name)
    await user.clear(nameInput)
    await user.type(nameInput, updatedName)
    await user.click(editor.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/location-dictionaries/${dictionaryKey}/${entry.id}/`,
      expect.objectContaining({ method: 'PATCH' }),
    ))
    const patchCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === 'PATCH',
    )
    expect(JSON.parse(patchCall?.[1]?.body as string)).toMatchObject({
      name: updatedName,
      ...parent,
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
