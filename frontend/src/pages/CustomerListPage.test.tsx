import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CustomerListResponse, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { CustomerListPage } from './CustomerListPage'

const authenticatedSession: Session = {
  isAuthenticated: true,
  user: {
    id: 1,
    displayName: 'Анна Агент',
    email: 'agent@example.com',
    agencyName: 'Север',
  },
  capabilities: {
    manageCatalogs: false,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

const customerDirectory: CustomerListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      id: 12,
      fullName: 'Иван Петров',
      phone: '+79995554433',
      email: 'ivan@example.com',
      residenceCity: 'Химки',
      createdAt: '2026-09-09T10:30:00+03:00',
      isActive: true,
      legacyDetailUrl: '/customers/12/',
    },
  ],
}

describe('CustomerListPage', () => {
  it('does not request private data and prompts anonymous visitors to sign in', () => {
    renderWithProviders(<CustomerListPage />)

    expect(
      screen.getByRole('heading', {
        name: 'Войдите, чтобы открыть список клиентов',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
      'href',
      '/users/login/?next=%2Fapp%2Fcustomers',
    )
  })

  it('renders the owner customer directory in desktop and mobile layouts', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(['session'], authenticatedSession)
    queryClient.setQueryData(['customers', ''], customerDirectory)

    renderWithProviders(<CustomerListPage />, { queryClient })

    expect(
      screen.getByRole('heading', { name: 'Клиенты' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName('Список клиентов')
    expect(screen.getAllByText('Иван Петров')).toHaveLength(2)
    expect(
      screen.getByRole('link', { name: 'Открыть карточку: Иван Петров' }),
    ).toHaveAttribute('href', '/customers/12')
    expect(
      screen.getByRole('link', { name: 'Добавить клиента' }),
    ).toHaveAttribute('href', '/customers/new')
  })
})
