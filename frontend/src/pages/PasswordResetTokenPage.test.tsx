import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { PasswordResetTokenPage } from './PasswordResetTokenPage'

function passwordResetTokenRoutes() {
  return (
    <Routes>
      <Route
        path="/password/reset/:userIdentifier/:token"
        element={<PasswordResetTokenPage />}
      />
      <Route
        path="/password/reset/confirm"
        element={<h1>Форма нового пароля</h1>}
      />
      <Route
        path="/password/reset"
        element={<h1>Запрос новой ссылки</h1>}
      />
    </Routes>
  )
}

describe('PasswordResetTokenPage', () => {
  it('exchanges the URL token and replaces it with the clean form route', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ valid: true }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(passwordResetTokenRoutes(), {
      initialRoute: '/password/reset/encoded-user/safe-token',
    })

    expect(await screen.findByRole('heading', {
      name: 'Форма нового пароля',
    })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/password/reset/token/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          userIdentifier: 'encoded-user',
          token: 'safe-token',
        }),
      }),
    )
    expect(screen.queryByText('safe-token')).not.toBeInTheDocument()
  })

  it('shows a generic error and recovery links for an invalid token', async () => {
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
    renderWithProviders(passwordResetTokenRoutes(), {
      initialRoute: '/password/reset/encoded-user/expired-token',
    })

    expect(await screen.findByRole('heading', {
      name: 'Ссылка не работает',
    })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Ссылка для восстановления недействительна или устарела.',
    )
    expect(screen.getByRole('link', { name: 'Запросить новую ссылку' }))
      .toHaveAttribute('href', '/password/reset')
    expect(screen.getByRole('link', {
      name: 'Прежняя версия восстановления',
    })).toHaveAttribute('href', '/users/password/reset/')
  })
})
