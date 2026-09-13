import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { RegistrationPage } from './RegistrationPage'

const authenticatedSession: Session = {
  isAuthenticated: true,
  user: {
    id: 5,
    displayName: 'Анна Иванова',
    email: 'anna@example.com',
    agencyName: '',
  },
  capabilities: {
    manageCatalogs: false,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

function registrationRoutes() {
  return (
    <Routes>
      <Route path="/register" element={<RegistrationPage />} />
      <Route path="/login" element={<h1>Вход после регистрации</h1>} />
      <Route path="/" element={<h1>Главная</h1>} />
    </Routes>
  )
}

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Имя'), 'Анна')
  await user.type(screen.getByLabelText('Фамилия'), 'Иванова')
  await user.type(screen.getByLabelText('Email'), 'anna@example.com')
  await user.type(screen.getByLabelText('Телефон'), '+79991112233')
  await user.type(screen.getByLabelText('Пароль'), 'safe-password')
  await user.type(screen.getByLabelText('Подтверждение пароля'), 'safe-password')
}

describe('RegistrationPage', () => {
  it('renders accessible account fields and preserves the Django fallback', () => {
    renderWithProviders(registrationRoutes(), { initialRoute: '/register' })

    expect(screen.getByRole('heading', { name: 'Регистрация' }))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute(
      'autocomplete',
      'email',
    )
    expect(screen.getByLabelText('Пароль')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
    expect(screen.getByRole('link', { name: 'Прежняя версия регистрации' }))
      .toHaveAttribute('href', '/users/register/')
    expect(screen.getByRole('link', { name: 'Войти' }))
      .toHaveAttribute('href', '/login')
  })

  it('shows a field error when password confirmation does not match', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(registrationRoutes(), { initialRoute: '/register' })

    await fillRequiredFields(user)
    await user.clear(screen.getByLabelText('Подтверждение пароля'))
    await user.type(screen.getByLabelText('Подтверждение пароля'), 'different')
    await user.click(screen.getByRole('button', {
      name: 'Зарегистрироваться',
    }))

    expect(screen.getByText('Пароли не совпадают.')).toBeInTheDocument()
    expect(screen.getByLabelText('Подтверждение пароля'))
      .toHaveAttribute('aria-invalid', 'true')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('requires an agency name when the agent option is selected', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(registrationRoutes(), { initialRoute: '/register' })

    await fillRequiredFields(user)
    await user.click(screen.getByLabelText('Я агент недвижимости'))
    await user.click(screen.getByRole('button', {
      name: 'Зарегистрироваться',
    }))

    expect(screen.getByText('Укажите название агентства.'))
      .toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('creates an account and opens the React login page', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ registered: true }),
      { status: 201, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(registrationRoutes(), { initialRoute: '/register' })

    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', {
      name: 'Зарегистрироваться',
    }))

    expect(await screen.findByRole('heading', {
      name: 'Вход после регистрации',
    })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/register/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          firstName: 'Анна',
          lastName: 'Иванова',
          email: 'anna@example.com',
          phoneNumber: '+79991112233',
          isRealEstateAgent: false,
          agencyName: '',
          password1: 'safe-password',
          password2: 'safe-password',
        }),
      }),
    )
  })

  it('shows server field errors without clearing entered data', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        errors: { email: ['Пользователь с таким email уже существует.'] },
      }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(registrationRoutes(), { initialRoute: '/register' })

    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', {
      name: 'Зарегистрироваться',
    }))

    await waitFor(() => expect(screen.getByText(
      'Пользователь с таким email уже существует.',
    )).toBeInTheDocument())
    expect(screen.getByLabelText('Email')).toHaveValue('anna@example.com')
  })

  it('redirects authenticated users to the application home page', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)

    renderWithProviders(registrationRoutes(), {
      initialRoute: '/register',
      queryClient,
    })

    expect(screen.getByRole('heading', { name: 'Главная' }))
      .toBeInTheDocument()
    expect(screen.queryByLabelText('Пароль')).not.toBeInTheDocument()
  })
})
