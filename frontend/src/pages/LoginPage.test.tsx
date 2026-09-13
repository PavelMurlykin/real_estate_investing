import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { LoginPage } from './LoginPage'

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

function loginRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<h1>Главная после входа</h1>} />
      <Route path="/customers" element={<h1>Клиенты после входа</h1>} />
    </Routes>
  )
}

describe('LoginPage', () => {
  it('renders an accessible form and preserves Django fallbacks', () => {
    renderWithProviders(loginRoutes(), { initialRoute: '/login' })

    expect(screen.getByRole('heading', { name: 'Вход' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email или телефон')).toHaveAttribute(
      'autocomplete',
      'username',
    )
    expect(screen.getByLabelText('Пароль')).toHaveAttribute(
      'autocomplete',
      'current-password',
    )
    expect(screen.getByRole('link', { name: 'Зарегистрироваться' }))
      .toHaveAttribute('href', '/users/register/')
    expect(screen.getByRole('link', { name: 'Забыли пароль?' }))
      .toHaveAttribute('href', '/users/password/reset/')
    expect(screen.getByRole('link', { name: 'Прежняя версия входа' }))
      .toHaveAttribute('href', '/users/login/?next=%2Fapp%2F')
  })

  it('shows a local error instead of submitting empty credentials', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(loginRoutes(), { initialRoute: '/login' })

    await user.click(screen.getByRole('button', { name: 'Войти' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Введите email или телефон и пароль.',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('creates a session and opens a safe requested React page', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(authenticatedSession),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], {
      isAuthenticated: false,
      user: null,
      capabilities: {
        manageCatalogs: false,
        syncExternalData: false,
        viewPrivateRecords: false,
        viewAllPrivateRecords: false,
      },
    })
    renderWithProviders(loginRoutes(), {
      initialRoute: '/login?next=%2Fapp%2Fcustomers',
      queryClient,
    })

    await user.type(screen.getByLabelText('Email или телефон'), 'anna@example.com')
    await user.type(screen.getByLabelText('Пароль'), 'safe-password')
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByRole('heading', {
      name: 'Клиенты после входа',
    })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/login/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          identifier: 'anna@example.com',
          password: 'safe-password',
        }),
      }),
    )
    expect(queryClient.getQueryData(['session'])).toEqual(authenticatedSession)
  })

  it('shows authoritative credential errors without clearing the form', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        errors: {
          nonFieldErrors: ['Введите правильные email или телефон и пароль.'],
        },
      }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(loginRoutes(), { initialRoute: '/login' })
    const identifierInput = screen.getByLabelText('Email или телефон')

    await user.type(identifierInput, 'unknown@example.com')
    await user.type(screen.getByLabelText('Пароль'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(
      'Введите правильные email или телефон и пароль.',
    ))
    expect(identifierInput).toHaveValue('unknown@example.com')
  })

  it('rejects an external next URL and returns to the React home page', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify(authenticatedSession),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(loginRoutes(), {
      initialRoute: '/login?next=https%3A%2F%2Fevil.example%2Fsteal',
    })

    await user.type(screen.getByLabelText('Email или телефон'), 'anna@example.com')
    await user.type(screen.getByLabelText('Пароль'), 'safe-password')
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByRole('heading', {
      name: 'Главная после входа',
    })).toBeInTheDocument()
  })

  it('redirects an already authenticated user without showing the form', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)

    renderWithProviders(loginRoutes(), {
      initialRoute: '/login?next=%2Fapp%2Fcustomers',
      queryClient,
    })

    expect(screen.getByRole('heading', { name: 'Клиенты после входа' }))
      .toBeInTheDocument()
    expect(screen.queryByLabelText('Пароль')).not.toBeInTheDocument()
  })
})
