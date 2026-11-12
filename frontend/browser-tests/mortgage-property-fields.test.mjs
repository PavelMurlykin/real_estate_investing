import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  createAuthenticatedPage, fixtureManifest, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

for (const mode of ['market', 'trench']) {
  test(mode + ' creates and saves a property directly in the unified calculator', {
    skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack',
  }, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1280, height: 1000 })
    const details = await page.request.get(isolatedBaseUrl + '/api/v1/properties/' + fixtureManifest.propertyId + '/')
    const property = await details.json()
    const prefix = '/api/v1/mortgage/' + (mode === 'trench' ? 'trench/' : '')
    await page.goto(isolatedBaseUrl + '/app/mortgage' + (mode === 'trench' ? '/trench' : ''))
    await page.getByRole('heading', { name: 'Ипотечный калькулятор', exact: true }).waitFor()
    assert.equal(await page.locator('form').count(), 1)
    assert.equal(await page.getByRole('button', { name: 'Заполнить объект вручную' }).count(), 0)
    const fields = page.locator('[aria-label="Данные объекта недвижимости"]')
    assert.equal(await fields.getByRole('combobox').count(), 8)
    assert.equal(await fields.locator('select,input[type=search]').count(), 0)

    const choose = async (name, dictionary, identifier, search) => {
      const response = await page.request.get(isolatedBaseUrl + '/api/v1/catalog-options/'
        + dictionary + '/?selectedIds=' + identifier)
      const option = (await response.json()).selected.find((entry) => entry.id === identifier)
      assert.ok(option)
      const control = fields.getByRole('combobox', { name, exact: true })
      await control.fill(search)
      await fields.getByRole('listbox', { name: `Варианты: ${name}`, exact: true })
        .getByRole('option', { name: option.label, exact: true }).click()
    }
    await choose('Город', 'cities', property.cityId, property.city)
    await choose('Район', 'districts', property.districtId, property.district)
    await choose('Застройщик', 'developers', property.developerId, property.developer)
    await choose('Жилой комплекс', 'complexes', property.realEstateComplexId, property.realEstateComplex)
    await choose('Корпус', 'buildings', property.buildingId, property.building)
    await choose('Планировка', 'layouts', property.layoutId, property.layout)
    await choose('Отделка', 'decorations', property.decorationId, property.decoration)
    const apartment = `UNIFIED-${mode}-${Date.now()}`
    await fields.getByLabel('Номер квартиры', { exact: true }).fill(apartment)
    await fields.getByLabel('Площадь, м²', { exact: true }).fill('0')
    await fields.getByLabel('Этаж', { exact: true }).fill('5')
    await page.getByLabel('Базовая стоимость, ₽', { exact: true }).fill('6300000')
    await page.getByLabel('Срок ипотеки, месяцев', { exact: true }).fill('24')
    const calculate = async () => {
      const [response] = await Promise.all([
        page.waitForResponse((response) => new URL(response.url()).pathname === prefix + 'calculate/'),
        page.getByRole('button', { name: mode === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку', exact: true }).click(),
      ])
      return response
    }
    assert.equal((await calculate()).status(), 400)
    assert.equal(await fields.getByLabel('Площадь, м²', { exact: true }).getAttribute('aria-invalid'), 'true')
    assert.ok(await fields.getByLabel('Площадь, м²', { exact: true }).getAttribute('aria-describedby'))
    await fields.getByLabel('Площадь, м²', { exact: true }).fill('45.67')
    const calculated = await calculate()
    assert.equal(calculated.status(), 200)
    assert.equal(calculated.request().postDataJSON().manualProperty.apartmentNumber, apartment)
    const [response] = await Promise.all([
      page.waitForResponse((response) => new URL(response.url()).pathname === prefix + 'calculations/' && response.request().method() === 'POST'),
      page.getByRole('button', { name: 'Сохранить расчёт', exact: true }).click(),
    ])
    assert.equal(response.status(), 201)
    assert.equal(Object.hasOwn(response.request().postDataJSON(), 'propertyId'), false)
    const created = await response.json()
    const calculationUrl = prefix + 'calculations/' + created.id + '/'
    trackCleanup(calculationUrl)
    const saved = await page.request.get(isolatedBaseUrl + calculationUrl).then((response) => response.json())
    trackCleanup('/api/v1/properties/' + saved.property.id + '/')
    trackCleanup(calculationUrl)
    assert.notEqual(saved.property.id, fixtureManifest.propertyId)
    assert.equal(saved.property.apartmentNumber, apartment)
    await page.getByRole('link', { name: 'Открыть сохранённый расчёт', exact: true }).click()
    for (const name of ['Excel', 'Word']) {
      const [download] = await Promise.all([
        page.waitForEvent('download'), page.getByRole('link', { name, exact: true }).click(),
      ])
      assert.equal(await download.failure(), null)
    }
  })
}
