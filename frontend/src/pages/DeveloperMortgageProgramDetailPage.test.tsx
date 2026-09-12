import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { DeveloperMortgageProgram, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { DeveloperMortgageProgramDetailPage } from './DeveloperMortgageProgramDetailPage'

const program: DeveloperMortgageProgram = {
  id: 9,
  companyGroupId: 4,
  companyGroupName: 'Группа Север',
  realEstateComplexId: 7,
  realEstateComplexName: 'ЖК Речной',
  complexDeveloperName: 'Север Девелопмент',
  bankId: 2,
  bankName: 'Тест Банк',
  mortgageProgramId: 5,
  mortgageProgramName: 'Семейная ипотека',
  priceIncreasePercent: '-1.25',
  gracePeriodMonths: 24,
  gracePeriodInterestRate: '0.10',
  minimumInitialPaymentPercent: '20.10',
  interestRate: '4.30',
  maximumLoanTermYears: 30,
  maximumLoanAmount: '12000000.00',
  rateDiscountPercent: '0.50',
  isActive: true,
  createdAt: '2026-01-10T10:00:00Z',
  updatedAt: '2026-01-11T10:00:00Z',
  detailUrl: '/developer-programs/9',
  legacyEditUrl: '/bank/developer-programs/9/edit/',
  legacyCatalogUrl: '/bank/developer-programs/',
}
const manager: Session = {
  isAuthenticated: true,
  user: { id: 1, displayName: 'Модератор', email: 'manager@example.com', agencyName: '' },
  capabilities: {
    manageCatalogs: true,
    syncExternalData: false,
    viewPrivateRecords: true,
    viewAllPrivateRecords: false,
  },
}

function renderDetail(session?: Session) {
  const client = createTestQueryClient()
  client.setQueryData(['developer-mortgage-program', 9], program)
  if (session) client.setQueryData(['session'], session)
  return renderWithProviders(
    <Routes>
      <Route path="/developer-programs/:developerProgramId" element={<DeveloperMortgageProgramDetailPage />} />
    </Routes>,
    { initialRoute: '/developer-programs/9', queryClient: client },
  )
}

describe('DeveloperMortgageProgramDetailPage', () => {
  it('renders the public scope, conditions and preserved Django link', () => {
    renderDetail()

    expect(screen.getAllByText('Группа Север').length).toBeGreaterThan(0)
    expect(screen.getByText('ЖК Речной · Север Девелопмент')).toBeInTheDocument()
    expect(screen.getAllByText('4,3%').length).toBeGreaterThan(0)
    expect(screen.getByText('12 000 000 ₽')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Django-интерфейсе' }))
      .toHaveAttribute('href', '/bank/developer-programs/9/edit/')
    expect(screen.queryByRole('link', { name: 'Редактировать' }))
      .not.toBeInTheDocument()
  })

  it('shows React edit and delete controls to a catalog manager', () => {
    renderDetail(manager)

    expect(screen.getByRole('link', { name: 'Редактировать' }))
      .toHaveAttribute('href', '/developer-programs/9/edit')
    expect(screen.getByRole('button', { name: 'Удалить' })).toBeInTheDocument()
  })
})
