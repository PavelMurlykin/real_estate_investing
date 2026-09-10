import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { CustomerCalculationListResponse } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { CustomerCalculationsSection } from './CustomerCalculationsSection'

const customerCalculations: CustomerCalculationListResponse = {
  page: 1,
  pageSize: 10,
  totalCount: 1,
  totalPages: 1,
  results: [
    {
      linkId: 31,
      calculationId: 7,
      programType: 'market',
      createdAt: '2026-09-09T10:30:00+03:00',
      property: {
        id: 3,
        city: 'Казань',
        realEstateComplex: 'Зелёный квартал',
        building: '2',
        apartmentNumber: '42',
      },
      finalPropertyCost: '4500000.00',
      initialPaymentRubles: '900000.00',
      monthlyPayment: '319832.06',
      mortgageTermMonths: 12,
      annualRate: '12.00',
      trenchCount: 1,
    },
  ],
}

function renderCalculations() {
  const queryClient = createTestQueryClient()
  queryClient.setQueryData(
    ['customer-calculations', 12, 'pageSize=10'],
    customerCalculations,
  )
  return renderWithProviders(
    <CustomerCalculationsSection
      customerIdentifier={12}
      customerName="Иван Петров"
    />,
    { initialRoute: '/customers/12', queryClient },
  )
}

describe('CustomerCalculationsSection', () => {
  it('renders unified calculations and downloads selected rows as Word', async () => {
    const user = userEvent.setup()
    const clickMock = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined)
    const createObjectUrlMock = vi.fn().mockReturnValue('blob:report')
    const revokeObjectUrlMock = vi.fn()
    const OriginalUrl = URL
    class DownloadUrl extends OriginalUrl {}
    Object.assign(DownloadUrl, {
      createObjectURL: createObjectUrlMock,
      revokeObjectURL: revokeObjectUrlMock,
    })
    vi.stubGlobal('URL', DownloadUrl)
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('report', {
        status: 200,
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'Content-Disposition': 'attachment; filename="customer.docx"',
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCalculations()

    expect(
      screen.getByRole('table', { name: 'Связанные расчёты клиента' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Новый расчёт' })).toHaveAttribute(
      'href',
      '/properties?customerId=12',
    )

    await user.click(screen.getByRole('checkbox', {
      name: /Выбрать расчёт от 09\.09\.2026/,
    }))
    await user.click(screen.getByRole('button', { name: 'Скачать Word' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/customers/12/calculations/export/word/',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      selections: [{ programType: 'market', linkId: 31 }],
    })
    expect(createObjectUrlMock).toHaveBeenCalled()
    expect(clickMock).toHaveBeenCalled()
    expect(revokeObjectUrlMock).toHaveBeenCalledWith('blob:report')
  })

  it('confirms unlinking while preserving the saved calculation', async () => {
    const user = userEvent.setup()
    const emptyResponse: CustomerCalculationListResponse = {
      ...customerCalculations,
      totalCount: 0,
      results: [],
    }
    const fetchMock = vi.fn().mockImplementation(
      (_path: RequestInfo | URL, options?: RequestInit) => {
        if (options?.method === 'DELETE') {
          return Promise.resolve(new Response(null, { status: 204 }))
        }
        return Promise.resolve(new Response(JSON.stringify(emptyResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }))
      },
    )
    vi.stubGlobal('fetch', fetchMock)
    renderCalculations()

    await user.click(screen.getByRole('button', {
      name: /Отвязать расчёт от 09\.09\.2026/,
    }))
    expect(screen.getByRole('alertdialog')).toHaveAccessibleName(
      'Отвязать расчёт от клиента?',
    )
    const confirmButton = screen.getByRole('button', {
      name: 'Отвязать расчёт',
    })
    expect(confirmButton).toHaveFocus()

    await user.click(confirmButton)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/customers/12/calculations/market/31/',
      expect.objectContaining({ method: 'DELETE' }),
    ))
    expect(
      await screen.findByRole('heading', { name: 'Связанных расчётов пока нет' }),
    ).toBeInTheDocument()
  })
})
