import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Session, UserProfile } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { ProfilePage } from './ProfilePage'

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

const profile: UserProfile = {
  firstName: 'Анна',
  lastName: 'Иванова',
  email: 'anna@example.com',
  phoneNumber: '+79991112233',
  isRealEstateAgent: true,
  agencyName: 'Север',
}

function profileRoutes() {
  return (
    <Routes>
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/login" element={<h1>Требуется вход</h1>} />
    </Routes>
  )
}

function authenticatedQueryClient() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['session'], authenticatedSession)
  queryClient.setQueryData(['user-profile'], profile)
  return queryClient
}

describe('ProfilePage', () => {
  it('renders current data and keeps Django account fallbacks', () => {
    renderWithProviders(profileRoutes(), {
      initialRoute: '/profile',
      queryClient: authenticatedQueryClient(),
    })

    expect(screen.getByRole('heading', { name: 'Профиль' }))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Имя')).toHaveValue('Анна')
    expect(screen.getByLabelText('Email')).toHaveValue('anna@example.com')
    expect(screen.getByLabelText('Я агент недвижимости')).toBeChecked()
    expect(screen.getByLabelText('Название агентства')).toHaveValue('Север')
    expect(screen.getByRole('link', { name: 'Сменить пароль' }))
      .toHaveAttribute('href', '/users/password/change/')
    expect(screen.getByRole('link', { name: 'Прежняя версия профиля' }))
      .toHaveAttribute('href', '/users/profile/edit/')
  })

  it('redirects anonymous visitors to login with a safe return path', () => {
    renderWithProviders(profileRoutes(), { initialRoute: '/profile' })

    expect(screen.getByRole('heading', { name: 'Требуется вход' }))
      .toBeInTheDocument()
  })

  it('updates the current profile and announces success', async () => {
    const user = userEvent.setup()
    const updatedProfile = {
      ...profile,
      email: 'new@example.com',
      agencyName: 'Новый дом',
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(updatedProfile),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = authenticatedQueryClient()
    renderWithProviders(profileRoutes(), {
      initialRoute: '/profile',
      queryClient,
    })

    await user.clear(screen.getByLabelText('Email'))
    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.clear(screen.getByLabelText('Название агентства'))
    await user.type(screen.getByLabelText('Название агентства'), 'Новый дом')
    await user.click(screen.getByRole('button', {
      name: 'Сохранить профиль',
    }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Профиль сохранён.',
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/profile/',
      expect.objectContaining({
        method: 'PATCH',
        credentials: 'same-origin',
        body: JSON.stringify({
          firstName: 'Анна',
          lastName: 'Иванова',
          email: 'new@example.com',
          phoneNumber: '+79991112233',
          isRealEstateAgent: true,
          agencyName: 'Новый дом',
        }),
      }),
    )
    expect(queryClient.getQueryData(['user-profile'])).toEqual(updatedProfile)
  })

  it('shows authoritative field errors and preserves edited values', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        errors: { email: ['Введите правильный адрес электронной почты.'] },
      }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(profileRoutes(), {
      initialRoute: '/profile',
      queryClient: authenticatedQueryClient(),
    })

    await user.clear(screen.getByLabelText('Email'))
    await user.type(screen.getByLabelText('Email'), 'invalid')
    await user.click(screen.getByRole('button', {
      name: 'Сохранить профиль',
    }))

    await waitFor(() => expect(screen.getByText(
      'Введите правильный адрес электронной почты.',
    )).toBeInTheDocument())
    expect(screen.getByLabelText('Email')).toHaveValue('invalid')
    expect(screen.getByLabelText('Email')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('requires agency name locally after enabling the agent option', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const nonAgentProfile = {
      ...profile,
      isRealEstateAgent: false,
      agencyName: '',
    }
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(['user-profile'], nonAgentProfile)
    renderWithProviders(profileRoutes(), {
      initialRoute: '/profile',
      queryClient,
    })

    await user.click(screen.getByLabelText('Я агент недвижимости'))
    await user.click(screen.getByRole('button', {
      name: 'Сохранить профиль',
    }))

    expect(screen.getByText('Укажите название агентства.'))
      .toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
