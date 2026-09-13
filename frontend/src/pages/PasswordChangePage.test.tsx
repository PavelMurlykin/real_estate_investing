import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { PasswordChangePage } from './PasswordChangePage'

const authenticatedSession: Session = {
  isAuthenticated: true,
  user: {
    id: 7,
    displayName: 'Анна Иванова',
    email: 'anna@example.com',
    agencyName: 'Север',
  },
  capabilities: {
    manageCatalogs: false,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

function passwordChangeRoutes() {
  return (
    <Routes>
      <Route path="/password/change" element={<PasswordChangePage />} />
      <Route path="/profile" element={<h1>Профиль</h1>} />
      <Route path="/login" element={<h1>Требуется вход</h1>} />
    </Routes>
  )
}

function authenticatedQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], authenticatedSession)
  return queryClient
}

async function fillPasswordFields(
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.type(screen.getByLabelText('Текущий пароль'), 'old-password')
  await user.type(screen.getByLabelText('Новый пароль'), 'new-safe-password')
  await user.type(
    screen.getByLabelText('Подтверждение нового пароля'),
    'new-safe-password',
  )
}

describe('PasswordChangePage', () => {
  it('renders accessible password fields and preserved Django fallback', () => {
    renderWithProviders(passwordChangeRoutes(), {
      initialRoute: '/password/change',
      queryClient: authenticatedQueryClient(),
    })

    expect(screen.getByRole('heading', { name: 'Смена пароля' }))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Текущий пароль')).toHaveAttribute(
      'autocomplete',
      'current-password',
    )
    expect(screen.getByLabelText('Новый пароль')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
    expect(screen.getByRole('link', {
      name: 'Прежняя версия смены пароля',
    })).toHaveAttribute('href', '/users/password/change/')
    expect(screen.getByRole('link', { name: 'Вернуться в профиль' }))
      .toHaveAttribute('href', '/profile')
  })

  it('redirects anonymous visitors to the login page', () => {
    renderWithProviders(passwordChangeRoutes(), {
      initialRoute: '/password/change',
    })

    expect(screen.getByRole('heading', { name: 'Требуется вход' }))
      .toBeInTheDocument()
    expect(screen.queryByLabelText('Текущий пароль')).not.toBeInTheDocument()
  })

  it('blocks mismatched new passwords before the API request', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(passwordChangeRoutes(), {
      initialRoute: '/password/change',
      queryClient: authenticatedQueryClient(),
    })

    await fillPasswordFields(user)
    await user.clear(screen.getByLabelText('Подтверждение нового пароля'))
    await user.type(
      screen.getByLabelText('Подтверждение нового пароля'),
      'different-password',
    )
    await user.click(screen.getByRole('button', { name: 'Изменить пароль' }))

    expect(screen.getByText('Новые пароли не совпадают.')).toBeInTheDocument()
    expect(screen.getByLabelText('Подтверждение нового пароля'))
      .toHaveAttribute('aria-invalid', 'true')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the authoritative current-password error without clearing fields', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        errors: { oldPassword: ['Ваш старый пароль введён неправильно.'] },
      }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(passwordChangeRoutes(), {
      initialRoute: '/password/change',
      queryClient: authenticatedQueryClient(),
    })

    await fillPasswordFields(user)
    await user.click(screen.getByRole('button', { name: 'Изменить пароль' }))

    await waitFor(() => expect(screen.getByText(
      'Ваш старый пароль введён неправильно.',
    )).toBeInTheDocument())
    expect(screen.getByLabelText('Текущий пароль')).toHaveValue('old-password')
    expect(screen.getByLabelText('Текущий пароль')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('changes the password, clears secrets and announces success', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ changed: true }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = authenticatedQueryClient()
    renderWithProviders(passwordChangeRoutes(), {
      initialRoute: '/password/change',
      queryClient,
    })

    await fillPasswordFields(user)
    await user.click(screen.getByRole('button', { name: 'Изменить пароль' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Пароль успешно изменён.',
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/password/change/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          oldPassword: 'old-password',
          newPassword1: 'new-safe-password',
          newPassword2: 'new-safe-password',
        }),
      }),
    )
    expect(screen.getByLabelText('Текущий пароль')).toHaveValue('')
    expect(screen.getByLabelText('Новый пароль')).toHaveValue('')
    expect(queryClient.getQueryData(['session'])).toEqual(authenticatedSession)
  })
})
