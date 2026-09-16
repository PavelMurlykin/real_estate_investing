import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type {
  PropertyDictionaryEntry,
  PropertyDictionaryListResponse,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { PropertyDictionaryPage } from './PropertyDictionaryPage'

const classEntry: PropertyDictionaryEntry = {
  id: 7,
  name: 'Бизнес',
  description: 'Повышенный комфорт',
  weight: '1.20',
  usageCount: 3,
  isActive: true,
  createdAt: '2026-09-10T10:00:00+03:00',
  updatedAt: '2026-09-11T10:00:00+03:00',
  legacyEditUrl: '/property/dictionaries/?model=real_estate_class&edit=7',
}

const directory: PropertyDictionaryListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [classEntry],
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

function createDictionaryQueryClient(session: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], session)
  queryClient.setQueryData(
    ['property-dictionaries', 'real-estate-classes', ''],
    directory,
  )
  return queryClient
}

function renderDictionaryPage(
  initialRoute: string,
  session: Session = anonymousSession,
) {
  const queryClient = createDictionaryQueryClient(session)
  return renderWithProviders(
    <Routes>
      <Route
        path="/dictionaries/:dictionaryKey"
        element={<PropertyDictionaryPage />}
      />
      <Route
        path="/dictionaries/:dictionaryKey/:entryId/edit"
        element={<PropertyDictionaryPage />}
      />
    </Routes>,
    { initialRoute, queryClient },
  )
}

describe('PropertyDictionaryPage', () => {
  it('renders all tabs and a public responsive directory', () => {
    renderDictionaryPage('/dictionaries/real-estate-classes')

    expect(screen.getByRole('heading', { name: 'Справочники объектов' }))
      .toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Классы ЖК' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: 'Планировки' })).toHaveAttribute(
      'href',
      '/dictionaries/apartment-layouts',
    )
    expect(screen.getByRole('table')).toHaveAccessibleName('Классы ЖК')
    expect(screen.getAllByText('Бизнес').length).toBeGreaterThan(0)
    expect(screen.getAllByText('1.20').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Сохранить' }))
      .not.toBeInTheDocument()
  })

  it('creates a class through the authoritative API and resets the form', async () => {
    const user = userEvent.setup()
    const createdEntry = {
      ...classEntry,
      id: 8,
      name: 'Премиум',
      weight: '1.45',
      usageCount: 0,
    }
    const fetchMock = vi.fn<typeof fetch>((_input, requestOptions) => {
      if (requestOptions?.method === 'POST') {
        return Promise.resolve(new Response(JSON.stringify(createdEntry), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.resolve(new Response(JSON.stringify(directory), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderDictionaryPage(
      '/dictionaries/real-estate-classes',
      managerSession,
    )

    await user.type(screen.getByLabelText('Название *'), '  Премиум  ')
    await user.type(screen.getByLabelText('Коэффициент *'), '1,45')
    await user.type(screen.getByLabelText('Описание'), 'Высокий класс')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(screen.getByLabelText('Название *')).toHaveValue(''))
    const postCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === 'POST',
    )
    expect(postCall?.[0]).toBe(
      '/api/v1/property-dictionaries/real-estate-classes/',
    )
    expect(JSON.parse(postCall?.[1]?.body as string)).toEqual({
      name: 'Премиум',
      description: 'Высокий класс',
      weight: '1.45',
      isActive: true,
    })
  })

  it('prefills and updates an entry while retaining the Django fallback', async () => {
    const user = userEvent.setup()
    const queryClient = createDictionaryQueryClient(managerSession)
    queryClient.setQueryData(
      ['property-dictionary', 'real-estate-classes', 7],
      classEntry,
    )
    const fetchMock = vi.fn<typeof fetch>((_input, requestOptions) => {
      if (requestOptions?.method === 'PATCH') {
        return Promise.resolve(new Response(JSON.stringify({
          ...classEntry,
          description: 'Обновлённое описание',
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.resolve(new Response(JSON.stringify(directory), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route
          path="/dictionaries/:dictionaryKey"
          element={<PropertyDictionaryPage />}
        />
        <Route
          path="/dictionaries/:dictionaryKey/:entryId/edit"
          element={<PropertyDictionaryPage />}
        />
      </Routes>,
      {
        initialRoute: '/dictionaries/real-estate-classes/7/edit',
        queryClient,
      },
    )

    expect(await screen.findByLabelText('Название *')).toHaveValue('Бизнес')
    expect(screen.getByRole('link', { name: 'Django-форма' })).toHaveAttribute(
      'href',
      classEntry.legacyEditUrl,
    )
    const description = screen.getByLabelText('Описание')
    await user.clear(description)
    await user.type(description, 'Обновлённое описание')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/property-dictionaries/real-estate-classes/7/',
      expect.objectContaining({ method: 'PATCH' }),
    ))
  })

  it('keeps a protected entry after an accessible delete conflict', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Запись используется.' }),
      {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      },
    )))
    renderDictionaryPage(
      '/dictionaries/real-estate-classes',
      managerSession,
    )

    const deleteButtons = screen.getAllByRole('button', {
      name: 'Удалить: Бизнес',
    })
    expect(deleteButtons).toHaveLength(2)
    await user.click(deleteButtons[0])
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('Удалить запись?')
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Запись используется в других разделах',
    )
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  })
})
