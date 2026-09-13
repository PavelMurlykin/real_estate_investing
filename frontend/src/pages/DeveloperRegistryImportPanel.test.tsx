import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/render'

import { DeveloperRegistryImportPanel } from './DeveloperRegistryImportPanel'

const successfulImport = {
  sourceRecords: 14,
  normalizedRecords: 12,
  createdDevelopers: 3,
  updatedDevelopers: 4,
  unchangedDevelopers: 5,
  createdCompanyGroups: 2,
  createdDeveloperRegionLinks: 7,
  skippedRecords: 2,
  errors: ['Строка 9: не указано название застройщика.'],
  dryRun: false,
}

describe('DeveloperRegistryImportPanel', () => {
  it('explains supported formats and idempotent behavior', () => {
    renderWithProviders(<DeveloperRegistryImportPanel />)

    expect(screen.getByRole('heading', { name: 'Импорт реестра ЕРЗ' }))
      .toBeInTheDocument()
    expect(screen.getByText(/Повторная загрузка/)).toHaveTextContent(
      'без создания дубликатов',
    )
    expect(screen.getByText('До 20 МБ')).toBeInTheDocument()
    expect(screen.getByLabelText('Файл ЕРЗ')).toHaveAttribute(
      'accept',
      expect.stringContaining('.csv,.json,.xlsx'),
    )
  })

  it('requires a selected source file', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperRegistryImportPanel />)

    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Выберите файл реестра ЕРЗ.',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects an unsupported source file before the request', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperRegistryImportPanel />)

    await user.upload(
      screen.getByLabelText('Файл ЕРЗ'),
      new File(['data'], 'developers.txt', { type: 'text/plain' }),
    )
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Поддерживаются файлы CSV, JSON и XLSX.',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects a source file larger than 20 MB', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const sourceFile = new File(['data'], 'developers.csv')
    Object.defineProperty(sourceFile, 'size', {
      value: 20 * 1024 * 1024 + 1,
    })
    renderWithProviders(<DeveloperRegistryImportPanel />)

    await user.upload(screen.getByLabelText('Файл ЕРЗ'), sourceFile)
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Размер файла не должен превышать 20 МБ.',
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
    renderWithProviders(<DeveloperRegistryImportPanel />)
    const sourceFile = new File(
      ['Застройщик;ИНН'],
      'developers.csv',
      { type: 'text/csv' },
    )

    await user.upload(screen.getByLabelText('Файл ЕРЗ'), sourceFile)
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    const result = await screen.findByRole('status')
    expect(within(result).getByRole('heading', { name: 'Реестр обработан' }))
      .toBeInTheDocument()
    expect(within(result).getByText('14 записей')).toBeInTheDocument()
    expect(
      within(result).getByText(
        'Строка 9: не указано название застройщика.',
      ),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [path, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/api/v1/developers/import-registry/')
    expect(request).toEqual(expect.objectContaining({
      method: 'POST',
      credentials: 'same-origin',
    }))
    expect(request.body).toBeInstanceOf(FormData)
    expect((request.body as FormData).get('source_file')).toEqual(sourceFile)
  })

  it('shows a controlled backend source error', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Файл реестра повреждён.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(<DeveloperRegistryImportPanel />)

    await user.upload(
      screen.getByLabelText('Файл ЕРЗ'),
      new File(['data'], 'developers.json', { type: 'application/json' }),
    )
    await user.click(screen.getByRole('button', { name: 'Импортировать' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(
      'Файл реестра повреждён.',
    ))
  })
})
