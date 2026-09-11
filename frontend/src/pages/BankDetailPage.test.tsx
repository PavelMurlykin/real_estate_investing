import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { BankDetail, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { BankDetailPage } from './BankDetailPage'

const bank: BankDetail = {
  id: 7,
  name: 'Северный банк',
  logoUrl: '',
  isActive: true,
  createdAt: '2026-01-10T10:00:00Z',
  updatedAt: '2026-01-11T10:00:00Z',
  programs: [
    {
      id: 12,
      mortgageProgramId: 3,
      mortgageProgramName: 'Семейная ипотека',
      interestRate: '5.90',
      minimumInitialPaymentPercent: '20.10',
      maximumLoanTermYears: 30,
    },
  ],
  legacyDetailUrl: '/bank/banks/7/',
  legacyEditUrl: '/bank/banks/7/edit/',
  legacyCatalogUrl: '/bank/?model=bank',
}

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

function renderDetail(session?: Session) {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['bank', 7], bank)
  if (session) queryClient.setQueryData(['session'], session)
  return renderWithProviders(
    <Routes>
      <Route path="/banks/:bankId" element={<BankDetailPage />} />
    </Routes>,
    { initialRoute: '/banks/7', queryClient },
  )
}

describe('BankDetailPage', () => {
  it('renders the public bank card and complete program terms', () => {
    renderDetail()

    expect(screen.getByRole('heading', { name: 'Северный банк', level: 1 }))
      .toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'Ипотечные программы банка Северный банк',
    )
    expect(screen.getAllByText('Семейная ипотека')).toHaveLength(2)
    expect(screen.getAllByText('5,9%')).toHaveLength(2)
    expect(screen.getByRole('link', { name: 'Открыть Django-версию' }))
      .toHaveAttribute('href', '/bank/banks/7/')
    expect(screen.queryByRole('link', { name: 'Редактировать' }))
      .not.toBeInTheDocument()
  })

  it('shows management actions only to catalog managers', () => {
    renderDetail(managerSession)

    expect(screen.getByRole('link', { name: 'Редактировать' }))
      .toHaveAttribute('href', '/banks/7/edit')
    expect(screen.getByRole('button', { name: 'Удалить' })).toBeEnabled()
  })
})
