import { useState } from 'react'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { mockMortgageCatalogs } from '@/test/mockMortgageCatalogs'
import { renderWithProviders } from '@/test/render'

import { PropertyFields } from './PropertyFields'
import { emptyManualProperty } from './manualProperty'
import type { ManualPropertyState } from './manualProperty'

const properties = [1, 2].map((id) => ({
  id, regionId: id, cityId: id, districtId: id, developerId: id,
  realEstateComplexId: id, buildingId: id, layoutId: id, decorationId: id,
  city: `Город ${id}`, district: `Район ${id}`, developer: `Застройщик ${id}`,
  realEstateComplex: `ЖК ${id}`, building: String(id), apartmentNumber: '42',
  area: '50.00', floor: 5, layout: `Планировка ${id}`, decoration: `Отделка ${id}`,
  propertyCost: '5000000.00', detailUrl: `/property/${id}/`,
}))

const initial: ManualPropertyState = {
  regionId: '1', cityId: '1', districtId: '1', developerId: '1',
  realEstateComplexId: '1', buildingId: '1', apartmentNumber: '42',
  area: '50.00', floor: '5', layoutId: '1', decorationId: '1',
}

function renderFields(value = initial, errors: Record<string, string> = {}) {
  mockMortgageCatalogs(properties)
  const changed = vi.fn()
  function Editor() {
    const [current, setCurrent] = useState(value)
    return <PropertyFields value={current} errors={errors} onChange={(next) => {
      changed(next)
      setCurrent(next)
    }} />
  }
  const result = renderWithProviders(<Editor />)
  return { ...result, changed }
}

describe('PropertyFields', () => {
  it('renders eight unified selectors immediately and connects validation errors', () => {
    const { container } = renderFields({ ...emptyManualProperty }, {
      'manualProperty.area': 'Укажите положительную площадь.',
    })
    expect(screen.getAllByRole('combobox')).toHaveLength(8)
    expect(container.querySelectorAll('select, input[type="search"], form')).toHaveLength(0)
    expect(screen.getByRole('combobox', { name: 'Район' })).toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'Корпус' })).toBeDisabled()
    expect(screen.getByLabelText('Площадь, м²')).toHaveAccessibleDescription('Укажите положительную площадь.')
    expect(screen.getByLabelText('Площадь, м²')).toHaveAttribute('aria-invalid', 'true')
  })

  it.each([
    ['Регион', 'Регион 2', { regionId: '2', cityId: '', districtId: '', realEstateComplexId: '', buildingId: '' }],
    ['Город', 'Город 2', { regionId: '2', cityId: '2', districtId: '', realEstateComplexId: '', buildingId: '' }],
    ['Застройщик', 'Застройщик 2', { developerId: '2', realEstateComplexId: '', buildingId: '' }],
    ['Жилой комплекс', 'ЖК 2', { regionId: '2', cityId: '2', districtId: '2', developerId: '2', realEstateComplexId: '2', buildingId: '' }],
  ] as const)('updates the %s cascade without losing apartment details', async (label, choice, expected) => {
    const user = userEvent.setup()
    const { changed } = renderFields()
    await user.click(screen.getByRole('combobox', { name: label }))
    await user.click(await screen.findByRole('option', { name: choice }))
    expect(changed).toHaveBeenLastCalledWith(expect.objectContaining({
      ...expected, apartmentNumber: '42', area: '50.00', floor: '5',
    }))
  })

  it('keeps the selected region when the city is cleared', async () => {
    const user = userEvent.setup()
    const { changed } = renderFields()
    await user.click(screen.getByRole('combobox', { name: 'Город' }))
    await user.click(screen.getByRole('option', { name: 'Не выбрано' }))
    expect(changed).toHaveBeenLastCalledWith(expect.objectContaining({
      regionId: '1', cityId: '', districtId: '', realEstateComplexId: '', buildingId: '',
    }))
  })
})
