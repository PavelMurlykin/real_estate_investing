import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { CompanyGroup, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { CompanyGroupFormPage } from './CompanyGroupFormPage'

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

const companyGroup: CompanyGroup = {
  id: 7,
  name: 'Группа Север',
  developerCount: 3,
  legacyEditUrl: '/property/company-groups/7/update/',
  legacyDeleteUrl: '/property/company-groups/7/delete/',
}

function createManagerQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], managerSession)
  return queryClient
}

function renderCreateForm() {
  return renderWithProviders(
    <Routes>
      <Route path="/company-groups/new" element={<CompanyGroupFormPage />} />
      <Route path="/company-groups" element={<h1>Справочник сохранён</h1>} />
    </Routes>,
    {
      initialRoute: '/company-groups/new',
      queryClient: createManagerQueryClient(),
    },
  )
}

describe('CompanyGroupFormPage', () => {
  it('prompts anonymous visitors to sign in', () => {
    renderWithProviders(
      <Routes>
        <Route path="/company-groups/new" element={<CompanyGroupFormPage />} />
      </Routes>,
      { initialRoute: '/company-groups/new' },
    )

    expect(
      screen.getByRole('heading', {
        name: 'Войдите для управления справочником',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/app/login?next=%2Fapp%2Fcompany-groups%2Fnew',
    )
  })

  it('creates a group and returns to the React directory', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        ...companyGroup,
        id: 8,
        name: 'ГК Новая',
        developerCount: 0,
      }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCreateForm()

    await user.type(screen.getByLabelText('Название *'), '  ГК Новая  ')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    expect(
      await screen.findByRole('heading', { name: 'Справочник сохранён' }),
    ).toBeInTheDocument()
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/company-groups/')
    expect(requestOptions.method).toBe('POST')
    expect(JSON.parse(requestOptions.body as string)).toEqual({
      name: 'ГК Новая',
    })
  })

  it('shows the authoritative uniqueness error beside the name field', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ name: ['Группа компаний с таким именем уже есть.'] }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    )
    renderCreateForm()

    await user.type(screen.getByLabelText('Название *'), 'Группа Север')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    expect(
      await screen.findByText('Группа компаний с таким именем уже есть.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /Название/ })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('prefills and updates an existing group', async () => {
    const user = userEvent.setup()
    const queryClient = createManagerQueryClient()
    queryClient.setQueryData(['company-group', 7], companyGroup)
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        ...companyGroup,
        name: 'Группа Северо-Запад',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route
          path="/company-groups/:companyGroupId/edit"
          element={<CompanyGroupFormPage />}
        />
        <Route path="/company-groups" element={<h1>Справочник сохранён</h1>} />
      </Routes>,
      {
        initialRoute: '/company-groups/7/edit',
        queryClient,
      },
    )

    const nameInput = await screen.findByLabelText('Название *')
    expect(nameInput).toHaveValue('Группа Север')
    expect(screen.getByRole('link', { name: 'Django-форма' })).toHaveAttribute(
      'href',
      '/property/company-groups/7/update/',
    )
    await user.clear(nameInput)
    await user.type(nameInput, 'Группа Северо-Запад')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    await screen.findByRole('heading', { name: 'Справочник сохранён' })
    const requestOptions = fetchMock.mock.calls[0][1] as RequestInit
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/company-groups/7/')
    expect(requestOptions.method).toBe('PATCH')
  })
})
