import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('creates apartments in Pushkin and Strelna and edits effective building geography in React and Django', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 120000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  const propertyOptionsRequests = []
  page.on('request', (request) => {
    const endpoint = new URL(request.url())
    if (endpoint.pathname === '/api/v1/properties/options/') propertyOptionsRequests.push(endpoint)
  })
  const request = page.context().request
  const url = (path) => new URL(path, isolatedBaseUrl).href
  const headers = { 'X-CSRFToken': await getCsrfToken(page.context()) }
  const read = async (path) => (await request.get(url(path))).json()
  const template = await read(`/api/v1/properties/${fixtureManifest.propertyId}/`)
  const templateProject = await read(`/api/v1/complexes/${template.realEstateComplexId}/`)
  const projects = []
  for (const name of ['Пушкин', 'Стрельна']) {
    const locality = (await read(`/api/v1/locations/?category=locality&q=${encodeURIComponent(name)}`)).results.find((row) => row.name === name)
    const response = await request.post(url('/api/v1/complexes/'), { headers, data: {
      name: `E2E квартиры ${name} ${Date.now()}`, locationId: locality.id,
      developerId: template.developerId, realEstateClassId: templateProject.realEstateClassId,
      realEstateTypeId: templateProject.realEstateTypeId, buildings: [{ number: '1' }],
    } })
    assert.equal(response.status(), 201, await response.text())
    const project = await response.json()
    trackCleanup(`/api/v1/complexes/${project.id}/`)
    projects.push({ project, locality })
  }
  for (const record of projects) {
    await page.goto(url('/app/properties/new'))
    await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).fill(record.locality.name)
    await page.getByRole('option', { name: new RegExp(`${record.locality.name} ·`) }).click()
    for (const [label, choice] of [
      ['Застройщик *', templateProject.developer.label], ['Жилой комплекс *', record.project.name],
      ['Корпус *', '1'], ['Планировка *', template.layout], ['Отделка *', template.decoration],
    ]) {
      await page.getByRole('combobox', { name: label, exact: true }).click()
      await page.getByRole('option', { name: choice, exact: true }).click()
    }
    for (const [label, value] of [['Номер квартиры *', 'NP-42'], ['Площадь, м² *', '52.25'], ['Этаж *', '4'], ['Стоимость, ₽ *', '7000000']]) {
      await page.getByLabel(label, { exact: true }).fill(value)
    }
    const saved = page.waitForResponse((reply) => reply.request().method() === 'POST' && new URL(reply.url()).pathname === '/api/v1/properties/')
    await page.getByRole('button', { name: 'Создать объект', exact: true }).click()
    const response = await saved
    assert.equal(response.status(), 201, await response.text())
    record.apartment = await response.json()
    trackCleanup(`/api/v1/properties/${record.apartment.id}/`)
    assert.equal(record.apartment.localityId, record.locality.id)
    assert.equal(record.apartment.buildingId, record.project.buildings[0].id)
    assert.equal(record.apartment.districtId, null)
  }
  assert.ok(propertyOptionsRequests.length > 0)
  assert.ok(propertyOptionsRequests.every((endpoint) => endpoint.searchParams.get('canonicalLocations') === 'true'))
  const [pushkin, strelna] = projects
  const bindings = { locations: [
    { locationId: pushkin.locality.id, isPrimary: false, isHistorical: true },
    { locationId: strelna.locality.id, isPrimary: true, isHistorical: false },
  ], buildings: [{ id: pushkin.project.buildings[0].id, locationId: pushkin.locality.id }] }
  const override = await request.put(url(`/api/v1/complexes/${pushkin.project.id}/locations/`), { headers, data: bindings })
  assert.equal(override.status(), 200, await override.text())
  try {
    await page.goto(url(`/app/properties/${pushkin.apartment.id}/edit`))
    const locality = page.getByRole('combobox', { name: 'Населённый пункт', exact: true })
    await locality.waitFor()
    await page.waitForFunction((input) => input.value.includes('Пушкин'), await locality.elementHandle())
    await page.getByLabel('Площадь, м² *', { exact: true }).fill('53.25')
    const updated = page.waitForResponse((reply) => reply.request().method() === 'PATCH' && new URL(reply.url()).pathname === `/api/v1/properties/${pushkin.apartment.id}/`)
    await page.getByRole('button', { name: 'Сохранить изменения', exact: true }).click()
    const response = await updated
    assert.equal(response.status(), 200, await response.text())
    const apartment = await response.json()
    assert.equal(apartment.localityId, pushkin.locality.id)
    assert.equal(apartment.buildingId, pushkin.apartment.buildingId)
    assert.equal(apartment.propertyCost, pushkin.apartment.propertyCost)
    assert.deepEqual(apartment.images, pushkin.apartment.images)

    await page.goto(url(`/property/${strelna.apartment.id}/update/?legacy=1`))
    const nativeLocality = page.getByRole('combobox', { name: /^Населённый пункт/ })
    assert.match(await nativeLocality.inputValue(), /Стрельна/)
    await page.getByRole('combobox', { name: /^Административный район/ }).click()
    await page.getByRole('option', { name: 'Не выбрано', exact: true }).click()
    await nativeLocality.fill('Пушкин')
    await page.getByRole('option', { name: /г\. Пушкин · Пушкинский/ }).click()
    await page.getByRole('combobox', { name: /^Жилой комплекс/ }).fill(pushkin.project.name)
    await page.getByRole('option', { name: pushkin.project.name, exact: true }).click()
    await page.getByRole('combobox', { name: /^Корпус/ }).fill('1')
    await page.getByRole('option', { name: '1', exact: true }).click()
    await page.getByText('Локация квартиры соответствует выбранному корпусу.', { exact: true }).waitFor()
    const nativeSaved = page.waitForResponse((reply) => reply.request().method() === 'POST' && new URL(reply.url()).pathname === `/property/${strelna.apartment.id}/update/`)
    await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
    assert.equal((await nativeSaved).status(), 302)
    const moved = await read(`/api/v1/properties/${strelna.apartment.id}/`)
    assert.equal(moved.localityId, pushkin.locality.id)
    assert.equal(moved.buildingId, pushkin.apartment.buildingId)
    assert.equal(moved.propertyCost, strelna.apartment.propertyCost)
    assert.deepEqual(moved.images, strelna.apartment.images)
    for (const width of [1440, 360]) {
      await page.setViewportSize({ width, height: 1000 })
      await page.goto(url(`/app/properties/${pushkin.apartment.id}/edit`))
      await page.getByLabel('Номер квартиры *', { exact: true }).waitFor()
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    }
  } finally {
    bindings.buildings[0].locationId = null
    const cleared = await request.put(url(`/api/v1/complexes/${pushkin.project.id}/locations/`), { headers, data: bindings })
    assert.equal(cleared.status(), 200, await cleared.text())
  }
})
