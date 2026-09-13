import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { PasswordResetConfirmPage } from './PasswordResetConfirmPage'

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

function passwordResetConfirmRoutes() {
  return (
    <Routes>
      <Route
        path="/password/reset/confirm"
        element={<PasswordResetConfirmPage />}
      />
      <Route path="/login" element={<h1>Вход с новым паролем</h1>} />
    </Routes>
  )
}

async function fillNewPasswordFields(
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.type(
    screen.getByLabelText('Новый пароль', { selector: 'input' }),
    'new-safe-password',
  )
  await user.type(
    screen.getByLabelText('Подтверждение нового пароля'),
    'new-safe-password',
  )
}

describe('PasswordResetConfirmPage', () => {
  it('renders accessible new-password fields and the Django fallback', () => {
    renderWithProviders(passwordResetConfirmRoutes(), {
      initialRoute: '/password/reset/confirm',
    })

    expect(screen.getByRole('heading', { name: 'Новый пароль' }))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Новый пароль', { selector: 'input' })).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
    expect(screen.getByRole('link', { name: 'Запросить новую ссылку' }))
      .toHaveAttribute('href', '/password/reset')
    expect(screen.getByRole('link', {
      name: 'Прежняя версия восстановления',
    })).toHaveAttribute('href', '/users/password/reset/')
  })

  it('blocks mismatched passwords before sending a request', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(passwordResetConfirmRoutes(), {
      initialRoute: '/password/reset/confirm',
    })

    await fillNewPasswordFields(user)
    await user.clear(screen.getByLabelText('Подтверждение нового пароля'))
    await user.type(
      screen.getByLabelText('Подтверждение нового пароля'),
      'different-password',
    )
    await user.click(screen.getByRole('button', {
      name: 'Сохранить новый пароль',
    }))

    expect(screen.getByText('Новые пароли не совпадают.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows password validation errors without clearing entered values', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        errors: { newPassword1: ['Введённый пароль слишком короткий.'] },
      }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(passwordResetConfirmRoutes(), {
      initialRoute: '/password/reset/confirm',
    })

    await fillNewPasswordFields(user)
    await user.click(screen.getByRole('button', {
      name: 'Сохранить новый пароль',
    }))

    await waitFor(() => expect(screen.getByText(
      'Введённый пароль слишком короткий.',
    )).toBeInTheDocument())
    expect(screen.getByLabelText('Новый пароль', { selector: 'input' }))
      .toHaveValue('new-safe-password')
  })

  it('shows an expired-session error and offers a new link', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        errors: {
          token: [
            'Ссылка для восстановления недействительна или устарела.',
          ],
        },
      }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(passwordResetConfirmRoutes(), {
      initialRoute: '/password/reset/confirm',
    })

    await fillNewPasswordFields(user)
    await user.click(screen.getByRole('button', {
      name: 'Сохранить новый пароль',
    }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ссылка для восстановления недействительна или устарела.',
    )
  })

  it('sets the anonymous session and opens login after success', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ changed: true, session: anonymousSession }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = createTestQueryClient()
    renderWithProviders(passwordResetConfirmRoutes(), {
      initialRoute: '/password/reset/confirm',
      queryClient,
    })

    await fillNewPasswordFields(user)
    await user.click(screen.getByRole('button', {
      name: 'Сохранить новый пароль',
    }))

    expect(await screen.findByRole('heading', {
      name: 'Вход с новым паролем',
    })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/password/reset/confirm/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          newPassword1: 'new-safe-password',
          newPassword2: 'new-safe-password',
        }),
      }),
    )
    expect(queryClient.getQueryData(['session'])).toEqual(anonymousSession)
  })
})
