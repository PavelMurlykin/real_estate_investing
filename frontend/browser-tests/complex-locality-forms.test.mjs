import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('creates and edits a complex by locality without a legacy district', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 90000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  const base = (path) => new URL(path, isolatedBaseUrl).href
  const name = `E2E населённый пункт ${Date.now()}`
  await page.goto(base('/app/complexes/new'))
  await page.getByLabel('Название ЖК *', { exact: true }).fill(name)
  for (const [label, option] of [['Застройщик *', /^E2E застройщик \(E2E группа\)$/], ['Класс ЖК *', /E2E комфорт/], ['Тип недвижимости *', /E2E квартира/]]) {
    await page.getByRole('combobox', { name: label, exact: true }).click()
    await page.getByRole('option', { name: option }).click()
  }
  assert.equal(await page.getByRole('combobox', { name: 'Район *', exact: true }).count(), 0)
  await page.getByRole('combobox', { name: 'Населённый пункт *', exact: true }).fill('Пушкин')
  await page.getByRole('option', { name: /г\. Пушкин · Пушкинский район/ }).click()
  await page.getByLabel('Номер корпуса 1 *', { exact: true }).fill('1')
  const created = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/complexes/')
  await page.getByRole('button', { name: 'Создать ЖК', exact: true }).click()
  const response = await created
  assert.equal(response.status(), 201, await response.text())
  const data = await response.json()
  trackCleanup(`/api/v1/complexes/${data.id}/`)
  assert.equal(data.districtId, null)
  assert.equal(data.regionLocationId, data.location.regionId)
  const submitted = response.request().postData() ?? ''
  assert.ok(submitted.includes('name="regionLocationId"'))
  assert.ok(submitted.includes('name="districtLocationId"'))
  assert.ok(!submitted.includes('name="districtId"'))
  assert.ok(!submitted.includes('name="cityId"'))
  assert.equal(data.location.id, fixtureManifest.pushkinLocationId)
  await page.getByRole('heading', { name, exact: true }).waitFor()
  await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
  const locality = page.getByRole('combobox', { name: 'Населённый пункт *', exact: true })
  await locality.waitFor()
  await page.waitForFunction((input) => input.value.includes('Пушкин'), await locality.elementHandle())
  assert.match(await locality.inputValue(), /Пушкин/)
  assert.match(await page.getByRole('combobox', { name: 'Регион', exact: true }).inputValue(), /Санкт-Петербург/)
  assert.match(await page.getByRole('combobox', { name: 'Административный район', exact: true }).inputValue(), /Пушкинский/)
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
    assert.equal(await locality.isVisible(), true)
  }
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.getByRole('combobox', { name: 'Административный район', exact: true }).fill('Петродворцовый')
  await page.getByRole('option', { name: /Петродворцовый район/ }).click()
  assert.equal(await locality.inputValue(), '')
  await locality.fill('Стрельна')
  await page.getByRole('option', { name: /п\. Стрельна · Петродворцовый район/ }).click()
  const updated = page.waitForResponse((reply) => reply.request().method() === 'PATCH' && new URL(reply.url()).pathname === `/api/v1/complexes/${data.id}/`)
  await page.getByRole('button', { name: 'Сохранить изменения', exact: true }).click()
  const saved = await updated
  assert.equal(saved.status(), 200, await saved.text())
  const final = await saved.json()
  assert.equal(final.districtId, null)
  assert.equal(final.location.id, fixtureManifest.strelnaLocationId)
  assert.deepEqual(final.buildings.map((row) => row.id), data.buildings.map((row) => row.id))
  await page.getByRole('heading', { name, exact: true }).waitFor()
  await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
  await page.getByRole('combobox', { name: 'Населённый пункт *', exact: true }).waitFor()
  const repeated = page.waitForResponse((reply) => reply.request().method() === 'PATCH' && new URL(reply.url()).pathname === `/api/v1/complexes/${data.id}/`)
  await page.getByRole('button', { name: 'Сохранить изменения', exact: true }).click()
  const repeatedResponse = await repeated
  assert.equal(repeatedResponse.status(), 200, await repeatedResponse.text())
  const repeatedData = await repeatedResponse.json()
  assert.equal(repeatedData.location.id, fixtureManifest.strelnaLocationId)
  assert.deepEqual(repeatedData.buildings.map((row) => row.id), final.buildings.map((row) => row.id))
  await page.getByRole('heading', { name, exact: true }).waitFor()
  await page.reload()
  await page.getByRole('heading', { name, exact: true }).waitFor()
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
  }
  await page.goto(base('/app/properties/new'))
  for (const [label, option] of [['Застройщик *', /^E2E застройщик \(E2E группа\)$/], ['Жилой комплекс *', name], ['Корпус *', '1'], ['Планировка *', 'E2E планировка'], ['Отделка *', 'E2E отделка']]) {
    await page.getByRole('combobox', { name: label, exact: true }).click()
    await page.getByRole('option', { name: option, exact: true }).click()
  }
  for (const [label, value] of [['Номер квартиры *', '2'], ['Площадь, м² *', '45'], ['Этаж *', '2'], ['Стоимость, ₽ *', '5000000']]) {
    await page.getByLabel(label, { exact: true }).fill(value)
  }
  const propertyResponse = page.waitForResponse((reply) => reply.request().method() === 'POST' && new URL(reply.url()).pathname === '/api/v1/properties/')
  await page.getByRole('button', { name: 'Создать объект', exact: true }).click()
  const apartment = await propertyResponse
  assert.equal(apartment.status(), 201, await apartment.text())
  const property = await apartment.json()
  trackCleanup(`/api/v1/properties/${property.id}/`)
  assert.equal(property.districtId, null)
  assert.equal(property.city, 'Стрельна')
})

test('edits legacy complexes through canonical React fields while retaining apartment and metro links', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 120000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  const request = page.context().request
  const base = (path) => new URL(path, isolatedBaseUrl).href
  const headers = { 'X-CSRFToken': await getCsrfToken(page.context()) }
  const read = async (path) => {
    const response = await request.get(base(path))
    assert.equal(response.status(), 200, await response.text())
    return response.json()
  }
  const create = async (path, data) => {
    const response = await request.post(base(path), { headers, data })
    assert.equal(response.status(), 201, await response.text())
    const result = await response.json()
    trackCleanup(`${path}${result.id}/`)
    return result
  }
  const template = await read(`/api/v1/properties/${fixtureManifest.propertyId}/`)
  const source = await read(`/api/v1/complexes/${template.realEstateComplexId}/`)
  const station = await create('/api/v1/location-dictionaries/metro/', {
    name: `E2E сохранённое метро ${Date.now()}`, metroLineId: fixtureManifest.metroLineId,
  })
  const accessibility = await create('/api/v1/property-dictionaries/transport-accessibility-types/', {
    name: `E2E пешком ${Date.now()}`,
  })
  const project = await create('/api/v1/complexes/', {
    name: `E2E прежняя территория ${Date.now()}`, districtId: source.districtId,
    developerId: template.developerId, realEstateClassId: source.realEstateClassId,
    realEstateTypeId: source.realEstateTypeId, buildings: [{ number: 'OLD-1' }],
    metroAvailability: [{ metroId: station.id, transportAccessibilityTypeId: accessibility.id,
      walkingTimeMinutes: 12, isActive: true }],
  })
  const apartment = await create('/api/v1/properties/', {
    buildingId: project.buildings[0].id, apartmentNumber: 'OLD-1', area: '45.00', floor: 3,
    propertyCost: '5000000.00', layoutId: template.layoutId, decorationId: template.decorationId,
  })
  const save = async () => {
    const response = page.waitForResponse((reply) => reply.request().method() === 'PATCH'
      && new URL(reply.url()).pathname === `/api/v1/complexes/${project.id}/`)
    await page.getByRole('button', { name: 'Сохранить изменения', exact: true }).click()
    const saved = await response
    assert.equal(saved.status(), 200, await saved.text())
    const result = await saved.json()
    assert.equal(result.districtId, project.districtId)
    assert.deepEqual(result.buildings.map((row) => row.id), project.buildings.map((row) => row.id))
    assert.deepEqual(result.metroAvailability, project.metroAvailability)
    await page.getByRole('heading', { name: project.name, exact: true }).waitFor()
    return result
  }
  await page.goto(base(`/app/complexes/${project.id}/edit`))
  await page.getByText(/Населённый пункт пока не уточнён/).waitFor()
  await page.getByLabel('Описание', { exact: true }).fill('Сохранить территорию и связи')
  const unchanged = await save()
  assert.deepEqual(unchanged.location, project.location)
  await page.goto(base(`/app/complexes/${project.id}/edit`))
  await page.getByRole('combobox', { name: 'Регион', exact: true }).fill('Санкт-Петербург')
  await page.getByRole('option', { name: /Санкт-Петербург/ }).click()
  await page.getByRole('combobox', { name: 'Населённый пункт *', exact: true }).fill('Пушкин')
  await page.getByRole('option', { name: /г\. Пушкин · Пушкинский район/ }).click()
  const refined = await save()
  assert.equal(refined.location.id, fixtureManifest.pushkinLocationId)
  const bindingUrl = `/api/v1/complexes/${project.id}/locations/`
  const assigned = await request.put(base(bindingUrl), { headers, data: {
    locations: [{ locationId: fixtureManifest.pushkinLocationId, isPrimary: true, isHistorical: false }],
    buildings: [{ id: project.buildings[0].id, locationId: fixtureManifest.pushkinLocationId }],
  } })
  assert.equal(assigned.status(), 200, await assigned.text())
  try {
    for (let repetition = 0; repetition < 2; repetition += 1) {
      await page.goto(base(`/app/complexes/${project.id}/edit`))
      const locality = page.getByRole('combobox', { name: 'Населённый пункт *', exact: true })
      await locality.waitFor()
      if (repetition === 0) {
        await page.getByRole('combobox', { name: 'Административный район', exact: true }).fill('Петродворцовый')
        await page.getByRole('option', { name: /Петродворцовый район/ }).click()
        await locality.fill('Стрельна')
        await page.getByRole('option', { name: /п\. Стрельна · Петродворцовый район/ }).click()
      }
      const result = await save()
      assert.equal(result.location.id, fixtureManifest.strelnaLocationId)
    }
    const preserved = await read(`/api/v1/properties/${apartment.id}/`)
    assert.equal(preserved.buildingId, apartment.buildingId)
    assert.equal(preserved.propertyCost, apartment.propertyCost)
    assert.equal(preserved.city, 'Пушкин')
    const bindings = await read(bindingUrl)
    assert.equal(bindings.buildings[0].locationId, fixtureManifest.pushkinLocationId)
    assert.ok(bindings.locations.find((row) => row.id === fixtureManifest.pushkinLocationId).isHistorical)
  } finally {
    const bindings = await read(bindingUrl)
    const restored = await request.put(base(bindingUrl), { headers, data: {
      locations: bindings.locations.map((row) => ({ locationId: row.id, isPrimary: row.isPrimary, isHistorical: row.isHistorical })),
      buildings: [{ id: project.buildings[0].id, locationId: null }],
    } })
    assert.equal(restored.status(), 200, await restored.text())
  }
})
