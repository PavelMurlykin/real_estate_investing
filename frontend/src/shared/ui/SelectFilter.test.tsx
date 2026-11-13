import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { SelectFilter } from './SelectFilter'

function Filters({ namespaced = false }: { namespaced?: boolean }) {
  const location = useLocation()
  return <><SelectFilter label="Статус" parameter={namespaced ? 'calculationProgram' : 'status'}
    pageParameter={namespaced ? 'calculationPage' : 'page'} options={[
      { value: 'active', label: 'Активные' }, { value: 'inactive', label: 'Неактивные' },
    ]} /><output aria-label="Адрес">{location.search}</output></>
}

describe('SelectFilter', () => {
  it.each([false, true])('searches in one field and resets only its own pagination (namespace %s)', async (namespaced) => {
    const user = userEvent.setup()
    renderWithProviders(<Filters namespaced={namespaced} />, { initialRoute: '/?page=4&calculationPage=3&customerId=12&q=Москва' })
    const input = screen.getByRole('combobox', { name: 'Статус' })
    const original = screen.getByLabelText('Адрес').textContent
    await user.click(input)
    await user.type(input, 'НЕАКТ')
    expect(screen.queryByRole('option', { name: 'Активные' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Адрес')).toHaveTextContent(original ?? '')
    await user.keyboard('{Enter}')
    expect(input).toHaveValue('Неактивные')
    const parameters = new URLSearchParams(screen.getByLabelText('Адрес').textContent ?? '')
    expect(parameters.get(namespaced ? 'calculationProgram' : 'status')).toBe('inactive')
    expect(parameters.has(namespaced ? 'calculationPage' : 'page')).toBe(false)
    expect(parameters.get(namespaced ? 'page' : 'calculationPage')).toBe(namespaced ? '4' : '3')
    expect(parameters.get('customerId')).toBe('12')
    expect(parameters.get('q')).toBe('Москва')
    await user.click(input)
    await user.click(screen.getByRole('option', { name: 'Все' }))
    expect(input).toHaveValue('')
    expect(new URLSearchParams(screen.getByLabelText('Адрес').textContent ?? '').has(namespaced ? 'calculationProgram' : 'status')).toBe(false)
  })
})
