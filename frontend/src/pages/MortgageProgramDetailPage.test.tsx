import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { MortgageProgramDetail, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { MortgageProgramDetailPage } from './MortgageProgramDetailPage'

const program: MortgageProgramDetail = {
  id: 5,
  name: 'Семейная ипотека',
  condition: 'Для семей с детьми',
  isPreferential: true,
  creditLimit: '12000000.00',
  bankCount: 2,
  developerProgramCount: 1,
  isActive: true,
  createdAt: '2026-01-10T10:00:00Z',
  updatedAt: '2026-01-11T10:00:00Z',
  regionalCreditLimits: [{
    id: 7,
    regionId: 77,
    regionName: 'Москва',
    creditLimit: '15000000.00',
    isActive: true,
  }],
  aliases: [{
    id: 8,
    sourceName: 'Семейная программа',
    normalizedName: 'семейная программа',
    source: 'Домклик',
    isActive: true,
  }],
  legacyEditUrl: '/bank/?model=mortgage_program&edit=5',
  legacyCatalogUrl: '/bank/?model=mortgage_program',
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
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(['mortgage-program', 5], program)
  if (session) queryClient.setQueryData(['session'], session)
  return renderWithProviders(
    <Routes>
      <Route path="/mortgage-programs/:mortgageProgramId" element={<MortgageProgramDetailPage />} />
    </Routes>,
    { initialRoute: '/mortgage-programs/5', queryClient },
  )
}

describe('MortgageProgramDetailPage', () => {
  it('renders regional limits, aliases and the preserved Django link', () => {
    renderDetail()

    expect(screen.getAllByText('Семейная ипотека').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Москва').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Семейная программа').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Домклик').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Открыть Django-форму' }))
      .toHaveAttribute('href', '/bank/?model=mortgage_program&edit=5')
    expect(screen.queryByRole('link', { name: 'Редактировать' }))
      .not.toBeInTheDocument()
  })

  it('offers React editing to a catalog manager', () => {
    renderDetail(manager)

    expect(screen.getByRole('link', { name: 'Редактировать' }))
      .toHaveAttribute('href', '/mortgage-programs/5/edit')
    expect(screen.getByRole('button', { name: 'Удалить' })).toBeInTheDocument()
  })
})
