import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { PasswordResetRequestPage } from './PasswordResetRequestPage'

function passwordResetRoutes() {
  return (
    <Routes>
      <Route path="/password/reset" element={<PasswordResetRequestPage />} />
      <Route path="/login" element={<h1>Вход</h1>} />
    </Routes>
  )
}

describe('PasswordResetRequestPage', () => {
  it('renders an accessible email form and both navigation fallbacks', () => {
    renderWithProviders(passwordResetRoutes(), {
      initialRoute: '/password/reset',
    })

    expect(screen.getByRole('heading', { name: 'Восстановление пароля' }))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute(
      'autocomplete',
      'email',
    )
    expect(screen.getByRole('link', { name: 'Вернуться ко входу' }))
      .toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', {
      name: 'Прежняя версия восстановления',
    })).toHaveAttribute('href', '/users/password/reset/')
  })

  it('requires an email before sending a request', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(passwordResetRoutes(), {
      initialRoute: '/password/reset',
    })

    await user.click(screen.getByRole('button', {
      name: 'Отправить инструкцию',
    }))

    expect(screen.getByText('Введите email.')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the same generic success state after an accepted request', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ requested: true }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(passwordResetRoutes(), {
      initialRoute: '/password/reset',
    })

    await user.type(screen.getByLabelText('Email'), 'person@example.com')
    await user.click(screen.getByRole('button', {
      name: 'Отправить инструкцию',
    }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Инструкция отправлена, если аккаунт с таким email существует.',
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/password/reset/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({ email: 'person@example.com' }),
      }),
    )
    expect(screen.getByLabelText('Email')).toHaveValue('')
  })

  it('shows authoritative email errors without clearing the value', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        errors: { email: ['Введите правильный адрес электронной почты.'] },
      }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    )))
    renderWithProviders(passwordResetRoutes(), {
      initialRoute: '/password/reset',
    })

    await user.type(screen.getByLabelText('Email'), 'invalid')
    await user.click(screen.getByRole('button', {
      name: 'Отправить инструкцию',
    }))

    await waitFor(() => expect(screen.getByText(
      'Введите правильный адрес электронной почты.',
    )).toBeInTheDocument())
    expect(screen.getByLabelText('Email')).toHaveValue('invalid')
  })
})
