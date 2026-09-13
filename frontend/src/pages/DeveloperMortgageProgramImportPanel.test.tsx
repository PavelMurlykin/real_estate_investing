import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { DeveloperMortgageProgramImportPanel } from './DeveloperMortgageProgramImportPanel'

const successfulImport = {
  totalRows: 12,
  parsedRows: 11,
  created: 3,
  updated: 2,
  unchanged: 4,
  skipped: 3,
  duplicateRows: 1,
  sourceWarningRows: 2,
  inactiveRows: 1,
  issueMessages: ['Строка 7: жилой комплекс не найден.'],
}

describe('DeveloperMortgageProgramImportPanel', () => {
  it('explains the workbook requirements', () => {
    renderWithProviders(<DeveloperMortgageProgramImportPanel />)

    expect(screen.getByRole('heading', { name: 'Импорт из XLSX' }))
      .toBeInTheDocument()
    expect(screen.getByText(/листом/)).toHaveTextContent('db_import')
    expect(screen.getByText('До 15 МБ · до 20 000 строк'))
      .toBeInTheDocument()
    expect(screen.getByLabelText('Файл XLSX')).toHaveAttribute(
      'accept',
      expect.stringContaining('.xlsx'),
    )
  })

  it('requires a selected file before sending a request', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperMortgageProgramImportPanel />)

    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Выберите XLSX-файл для импорта.',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects an unsupported file before sending a request', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperMortgageProgramImportPanel />)

    await user.upload(
      screen.getByLabelText('Файл XLSX'),
      new File(['data'], 'programs.csv', { type: 'text/csv' }),
    )
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Поддерживаются только файлы XLSX.',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects a workbook larger than 15 MB', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const workbook = new File(['data'], 'programs.xlsx')
    Object.defineProperty(workbook, 'size', {
      value: 15 * 1024 * 1024 + 1,
    })
    renderWithProviders(<DeveloperMortgageProgramImportPanel />)

    await user.upload(screen.getByLabelText('Файл XLSX'), workbook)
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Размер файла не должен превышать 15 МБ.',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('uploads multipart data and displays the complete import summary', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(successfulImport),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperMortgageProgramImportPanel />)
    const workbook = new File(
      ['xlsx'],
      'programs.xlsx',
      {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      },
    )

    await user.upload(screen.getByLabelText('Файл XLSX'), workbook)
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    const result = await screen.findByRole('status')
    expect(within(result).getByRole('heading', { name: 'Файл обработан' }))
      .toBeInTheDocument()
    expect(within(result).getByText('12 строк')).toBeInTheDocument()
    expect(within(result).getByText('Строка 7: жилой комплекс не найден.'))
      .toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [path, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/api/v1/developer-mortgage-programs/import/')
    expect(request).toEqual(expect.objectContaining({
      method: 'POST',
      credentials: 'same-origin',
    }))
    expect(request.body).toBeInstanceOf(FormData)
    expect((request.body as FormData).get('workbook_file')).toEqual(workbook)
  })

  it('shows a controlled backend workbook error', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'В файле отсутствует лист db_import.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperMortgageProgramImportPanel />)

    await user.upload(
      screen.getByLabelText('Файл XLSX'),
      new File(['xlsx'], 'programs.xlsx'),
    )
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(
      'В файле отсутствует лист db_import.',
    ))
  })
})
