import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { MortgageProgramDetail, MortgageProgramOptions, Session } from '@/api/schemas'
import { createTestQueryClient, renderWithProviders } from '@/test/render'

import { MortgageProgramFormPage } from './MortgageProgramFormPage'

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
const options: MortgageProgramOptions = {
  regions: [{ id: 77, name: 'Москва' }, { id: 78, name: 'Санкт-Петербург' }],
  truncated: false,
}
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

function managerClient() {
  const client = createTestQueryClient()
  client.setQueryData(['session'], manager)
  client.setQueryData(['mortgage-program-options'], options)
  return client
}

function renderCreate() {
  return renderWithProviders(
    <Routes>
      <Route path="/mortgage-programs/new" element={<MortgageProgramFormPage />} />
      <Route path="/mortgage-programs/:mortgageProgramId" element={<h1>Программа сохранена</h1>} />
    </Routes>,
    { initialRoute: '/mortgage-programs/new', queryClient: managerClient() },
  )
}

describe('MortgageProgramFormPage', () => {
  it('does not request protected form data for an anonymous visitor', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route path="/mortgage-programs/new" element={<MortgageProgramFormPage />} />
      </Routes>,
      { initialRoute: '/mortgage-programs/new' },
    )

    expect(screen.getByRole('heading', {
      name: 'Войдите для управления программами',
    })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('creates a program with a regional limit and import alias', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(program),
      { status: 201, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderCreate()

    await user.type(screen.getByLabelText('Название *'), ' Семейная ипотека ')
    await user.type(screen.getByLabelText('Условия *'), ' Для семей с детьми ')
    await user.type(screen.getByLabelText(/^Федеральный лимит, ₽/), '12000000')
    await user.click(screen.getByLabelText(/^Льготная программа/))
    await user.click(screen.getByRole('button', { name: 'Добавить регион' }))
    await user.selectOptions(screen.getByLabelText('Регион *'), '77')
    await user.type(screen.getByLabelText('Лимит, ₽ *'), '15000000')
    await user.click(screen.getByRole('button', { name: 'Добавить алиас' }))
    const nameInputs = screen.getAllByLabelText('Название *')
    await user.type(nameInputs[1], 'Семейная программа')
    await user.type(screen.getByLabelText('Источник'), 'Домклик')
    await user.click(screen.getByRole('button', { name: 'Создать программу' }))

    expect(await screen.findByRole('heading', { name: 'Программа сохранена' }))
      .toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/mortgage-programs/')
    const request = fetchMock.mock.calls[0][1] as RequestInit
    expect(request.method).toBe('POST')
    expect(JSON.parse(request.body as string)).toEqual({
      name: 'Семейная ипотека',
      condition: 'Для семей с детьми',
      creditLimit: '12000000',
      isPreferential: true,
      isActive: true,
      regionalCreditLimits: [{
        regionId: 77,
        creditLimit: '15000000',
        isActive: true,
      }],
      aliases: [{ sourceName: 'Семейная программа', source: 'Домклик', isActive: true }],
    })
  })

  it('prefills the complete card and uses the React update endpoint', async () => {
    const user = userEvent.setup()
    const client = managerClient()
    client.setQueryData(['mortgage-program', 5], program)
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ ...program, condition: 'Обновлённые условия' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    renderWithProviders(
      <Routes>
        <Route path="/mortgage-programs/:mortgageProgramId/edit" element={<MortgageProgramFormPage />} />
        <Route path="/mortgage-programs/:mortgageProgramId" element={<h1>Программа сохранена</h1>} />
      </Routes>,
      { initialRoute: '/mortgage-programs/5/edit', queryClient: client },
    )

    expect(await screen.findByLabelText('Условия *')).toHaveValue('Для семей с детьми')
    expect(screen.getByLabelText('Регион *')).toHaveValue('77')
    expect(screen.getAllByLabelText('Название *')[1]).toHaveValue('Семейная программа')
    expect(screen.getByRole('link', { name: 'Django-справочник' }))
      .toHaveAttribute('href', '/bank/?model=mortgage_program&edit=5')
    await user.clear(screen.getByLabelText('Условия *'))
    await user.type(screen.getByLabelText('Условия *'), 'Обновлённые условия')
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }))

    expect(await screen.findByRole('heading', { name: 'Программа сохранена' }))
      .toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/mortgage-programs/5/')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('PATCH')
  })
})
