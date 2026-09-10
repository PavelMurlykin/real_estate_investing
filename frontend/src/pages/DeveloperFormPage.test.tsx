import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Developer, DeveloperOptions, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { DeveloperFormPage } from './DeveloperFormPage'

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

const options: DeveloperOptions = {
  companyGroups: [{ id: 4, name: 'Группа Север' }],
  regions: [
    { id: 8, name: 'Санкт-Петербург' },
    { id: 9, name: 'Ленинградская область' },
  ],
  truncated: {
    companyGroups: false,
    regions: false,
  },
}

const developer: Developer = {
  id: 7,
  name: 'Северный девелопер',
  companyGroup: { id: 4, name: 'Группа Север' },
  regions: [{ id: 8, name: 'Санкт-Петербург' }],
  complexCount: 3,
  isActive: true,
  description: 'Надёжный застройщик',
  legalAddress: 'Невский проспект, 1',
  actualAddress: 'Литейный проспект, 2',
  taxpayerIdentificationNumber: '7812345678',
  taxRegistrationReasonCode: '781201001',
  primaryStateRegistrationNumber: '1234567890123',
  createdAt: '2026-01-10T10:00:00Z',
  updatedAt: '2026-01-11T10:00:00Z',
  legacyEditUrl: '/property/developers/7/update/',
  legacyDeleteUrl: '/property/developers/7/delete/',
}

function createManagerQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], managerSession)
  queryClient.setQueryData(['developer-options'], options)
  return queryClient
}

function renderCreateForm() {
  return renderWithProviders(
    <Routes>
      <Route path="/developers/new" element={<DeveloperFormPage />} />
      <Route path="/developers" element={<h1>Справочник сохранён</h1>} />
    </Routes>,
    {
      initialRoute: '/developers/new',
      queryClient: createManagerQueryClient(),
    },
  )
}

describe('DeveloperFormPage', () => {
  it('does not request private detail data for anonymous visitors', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route path="/developers/new" element={<DeveloperFormPage />} />
      </Routes>,
      { initialRoute: '/developers/new' },
    )

    expect(
      screen.getByRole('heading', {
        name: 'Войдите для управления застройщиками',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/users/login/?next=%2Fapp%2Fdevelopers%2Fnew',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('creates a developer with selected regions and normalized optional data', async () => {
    const user = userEvent.setup()
    const createdDeveloper = {
      ...developer,
      id: 10,
      name: 'Новый девелопер',
      regions: options.regions,
      legalAddress: null,
      isActive: false,
    }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(createdDeveloper), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()

    await user.type(screen.getByLabelText('Название *'), '  Новый девелопер  ')
    await user.selectOptions(screen.getByLabelText('Группа компаний'), '4')
    await user.selectOptions(screen.getByLabelText('Регионы'), ['8', '9'])
    await user.type(screen.getByLabelText('ИНН'), '7812345678')
    await user.click(screen.getByRole('checkbox', {
      name: /Активный застройщик/,
    }))
    await user.click(screen.getByRole('button', {
      name: 'Создать застройщика',
    }))

    expect(
      await screen.findByRole('heading', { name: 'Справочник сохранён' }),
    ).toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/developers/')
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    expect(requestOptions.method).toBe('POST')
    expect(JSON.parse(requestOptions.body as string)).toEqual({
      name: 'Новый девелопер',
      companyGroupId: 4,
      regionIds: [8, 9],
      legalAddress: null,
      actualAddress: null,
      taxpayerIdentificationNumber: '7812345678',
      taxRegistrationReasonCode: null,
      primaryStateRegistrationNumber: null,
      description: null,
      isActive: false,
    })
  })

  it('shows the authoritative uniqueness error beside the name field', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ name: ['Застройщик с таким именем уже есть.'] }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    )
    renderCreateForm()

    await user.type(screen.getByLabelText('Название *'), developer.name)
    await user.click(screen.getByRole('button', {
      name: 'Создать застройщика',
    }))

    expect(
      await screen.findByText('Застройщик с таким именем уже есть.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /Название/ })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('prefills sensitive manager fields and updates the developer', async () => {
    const user = userEvent.setup()
    const queryClient = createManagerQueryClient()
    queryClient.setQueryData(['developer', 7], developer)
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        ...developer,
        name: 'Северо-Западный девелопер',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route
          path="/developers/:developerId/edit"
          element={<DeveloperFormPage />}
        />
        <Route path="/developers" element={<h1>Справочник сохранён</h1>} />
      </Routes>,
      {
        initialRoute: '/developers/7/edit',
        queryClient,
      },
    )

    const nameInput = await screen.findByLabelText('Название *')
    expect(nameInput).toHaveValue('Северный девелопер')
    expect(screen.getByLabelText('Юридический адрес')).toHaveValue(
      'Невский проспект, 1',
    )
    expect(screen.getByLabelText('ИНН')).toHaveValue('7812345678')
    expect(screen.getByLabelText('Регионы')).toHaveValue(['8'])
    expect(screen.getByRole('link', { name: 'Django-форма' })).toHaveAttribute(
      'href',
      '/property/developers/7/update/',
    )
    await user.clear(nameInput)
    await user.type(nameInput, 'Северо-Западный девелопер')
    await user.click(screen.getByRole('button', {
      name: 'Сохранить изменения',
    }))

    await screen.findByRole('heading', { name: 'Справочник сохранён' })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/developers/7/')
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    expect(requestOptions.method).toBe('PATCH')
  })
})
