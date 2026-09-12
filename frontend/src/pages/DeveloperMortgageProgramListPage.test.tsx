import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type {
  DeveloperMortgageProgramListResponse,
  DeveloperMortgageProgramOptions,
  Session,
} from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { DeveloperMortgageProgramListPage } from './DeveloperMortgageProgramListPage'

const program = {
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
} as const
const directory: DeveloperMortgageProgramListResponse = {
  page: 1,
  pageSize: 20,
  totalCount: 1,
  totalPages: 1,
  results: [program],
}
const options: DeveloperMortgageProgramOptions = {
  companyGroups: [{ id: 4, name: 'Группа Север' }],
  realEstateComplexes: [],
  banks: [{ id: 2, name: 'Тест Банк' }],
  mortgagePrograms: [{ id: 5, name: 'Семейная ипотека' }],
  truncated: {
    companyGroups: false,
    realEstateComplexes: false,
    banks: false,
    mortgagePrograms: false,
  },
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

function queryClient(session?: Session) {
  const client = createTestQueryClient()
  client.setQueryData(['developer-mortgage-programs', ''], directory)
  client.setQueryData(['developer-mortgage-program-options', null], options)
  if (session) client.setQueryData(['session'], session)
  return client
}

describe('DeveloperMortgageProgramListPage', () => {
  it('renders public conditions with React detail links', () => {
    renderWithProviders(<DeveloperMortgageProgramListPage />, {
      queryClient: queryClient(),
    })

    expect(screen.getByRole('heading', { name: 'Программы застройщиков' }))
      .toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveAccessibleName(
      'Список программ застройщиков',
    )
    expect(screen.getAllByRole('link', { name: 'Группа Север' })[0])
      .toHaveAttribute('href', '/developer-programs/9')
    expect(screen.getAllByText('4,3%').length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: 'Добавить программу' }))
      .not.toBeInTheDocument()
  })

  it('stores filters in the URL and requests filtered rows', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(directory),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperMortgageProgramListPage />, {
      queryClient: queryClient(),
    })

    await user.selectOptions(screen.getByLabelText('Статус'), 'inactive')

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/developer-mortgage-programs/?status=inactive',
      expect.objectContaining({ credentials: 'same-origin' }),
    ))
  })

  it('offers manager actions and confirms deletion', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperMortgageProgramListPage />, {
      queryClient: queryClient(manager),
    })

    expect(screen.getByRole('link', { name: 'Добавить программу' }))
      .toHaveAttribute('href', '/developer-programs/new')
    await user.click(screen.getByRole('button', {
      name: 'Удалить: Группа Север, Семейная ипотека',
    }))
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('Удалить программу?')
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/developer-mortgage-programs/9/',
      expect.objectContaining({ method: 'DELETE' }),
    ))
  })
})
