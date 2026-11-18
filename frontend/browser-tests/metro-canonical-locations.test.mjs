import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('edits metro systems, lines and suburban station geography while preserving complex links', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 120000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  const legacyOptionsRequests = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v1/location-dictionaries/options/') {
      legacyOptionsRequests.push(request.url())
    }
  })
  const url = (path) => new URL(path, isolatedBaseUrl).href
  const read = async (path) => (await page.context().request.get(url(path))).json()
  const choose = async (label, query, option) => {
    await page.getByRole('complementary').getByRole('combobox', { name: label, exact: true }).fill(query)
    await page.getByRole('option', { name: option }).click()
  }
  const save = async (key) => {
    const reply = page.waitForResponse((response) => response.request().method() === 'POST'
      && new URL(response.url()).pathname === `/api/v1/location-dictionaries/${key}/`)
    await page.getByRole('complementary').getByRole('button', { name: 'Сохранить', exact: true }).click()
    const response = await reply
    assert.equal(response.status(), 201, await response.text())
    const entry = await response.json()
    trackCleanup(`/api/v1/location-dictionaries/${key}/${entry.id}/`)
    return entry
  }
  const systemName = `E2E система ${Date.now()}`
  await page.goto(url('/app/locations/metro-systems'))
  await page.getByLabel('Название системы *', { exact: true }).fill(systemName)
  await choose('Центр системы *', 'Санкт-Петербург', /^г\. Санкт-Петербург/)
  const system = await save('metro-systems')
  const lines = []
  for (const suffix of ['первая', 'вторая']) {
    await page.goto(url('/app/locations/metro-lines'))
    await page.getByLabel('Название линии *', { exact: true }).fill(`E2E ${suffix}`)
    await choose('Система метро *', systemName, systemName)
    lines.push(await save('metro-lines'))
  }
  await page.goto(url('/app/locations/metro'))
  await page.getByLabel('Название станции *', { exact: true }).fill('E2E пригородная станция')
  await choose('Система метро *', systemName, systemName)
  await choose('Линия метро *', 'E2E первая', 'E2E первая')
  await choose('Все линии станции', 'E2E вторая', 'E2E вторая')
  await page.keyboard.press('Escape')
  await choose('Населённый пункт станции', 'Пушкин', /г\. Пушкин · Пушкинский/)
  const station = await save('metro')
  assert.deepEqual(new Set(station.lines.map((line) => line.id)), new Set(lines.map((line) => line.id)))
  assert.equal(station.location.id, fixtureManifest.pushkinLocationId)
  assert.equal(station.locationIsInferred, false)

  const source = await read(`/api/v1/complexes/${fixtureManifest.complexId}/`)
  const transport = (await read('/api/v1/catalog-options/transport-accessibility-types/')).results[0]
  const created = await page.context().request.post(url('/api/v1/complexes/'), {
    headers: { 'X-CSRFToken': await getCsrfToken(page.context()) },
    data: { name: systemName, developerId: source.developerId, realEstateClassId: source.realEstateClassId,
      realEstateTypeId: source.realEstateTypeId, locationId: fixtureManifest.strelnaLocationId,
      buildings: [{ number: '1', isActive: true }], metroAvailability: [
        { metroId: station.id, transportAccessibilityTypeId: transport.id, walkingTimeMinutes: 25, isActive: true },
      ] },
  })
  assert.equal(created.status(), 201, await created.text())
  const complex = await created.json()
  trackCleanup(`/api/v1/complexes/${complex.id}/`)
  await page.goto(url(`/app/locations/metro/${station.id}/edit`))
  await choose('Населённый пункт станции', 'Стрельна', /п\. Стрельна · Петродворцовый/)
  const edited = page.waitForResponse((reply) => reply.request().method() === 'PATCH'
    && new URL(reply.url()).pathname === `/api/v1/location-dictionaries/metro/${station.id}/`)
  await page.getByRole('complementary').getByRole('button', { name: 'Сохранить', exact: true }).click()
  assert.equal((await edited).status(), 200)
  const after = await read(`/api/v1/complexes/${complex.id}/`)
  assert.deepEqual(after.metroAvailability, complex.metroAvailability)
  const updated = await read(`/api/v1/location-dictionaries/metro/${station.id}/`)
  assert.equal(updated.location.id, fixtureManifest.strelnaLocationId)

  await page.goto(url(`/locations/?model=metro&edit=${station.id}&legacy=1`))
  await page.locator('#id_location').waitFor({ state: 'attached' })
  assert.equal(await page.locator('#id_location').inputValue(), String(fixtureManifest.strelnaLocationId))
  assert.deepEqual(new Set(await page.locator('#id_lines').evaluate((element) => [...element.selectedOptions].map((option) => Number(option.value)))), new Set(lines.map((line) => line.id)))
  await page.locator('#id_station').fill('E2E станция после Django')
  const nativeSave = page.waitForResponse((reply) => reply.request().method() === 'POST'
    && new URL(reply.url()).pathname === '/locations/')
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  assert.equal((await nativeSave).status(), 302)
  const nativeStation = await read(`/api/v1/location-dictionaries/metro/${station.id}/`)
  assert.equal(nativeStation.name, 'E2E станция после Django')
  assert.equal(nativeStation.location.id, fixtureManifest.strelnaLocationId)
  assert.deepEqual((await read(`/api/v1/complexes/${complex.id}/`)).metroAvailability.map((row) => row.id), complex.metroAvailability.map((row) => row.id))
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto(url('/app/locations/metro'))
    await page.getByRole('heading', { name: 'Локации', exact: true }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
  }
  assert.deepEqual(legacyOptionsRequests, [])
})
