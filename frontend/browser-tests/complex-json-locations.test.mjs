import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('imports and repeats canonical and legacy complex JSON for Pushkin and Strelna', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 120000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'administrator', { width: 1440, height: 1100 })
  const url = (path) => new URL(path, isolatedBaseUrl).href
  const read = async (path) => (await page.context().request.get(url(path))).json()
  const source = await read(`/api/v1/complexes/${fixtureManifest.complexId}/`)
  const developer = await read(`/api/v1/developers/${source.developerId}/`)
  const oldCounts = await Promise.all(['regions', 'cities', 'districts'].map(async (key) => (await read(`/api/v1/location-dictionaries/${key}/`)).totalCount))
  const marker = Date.now()
  const createdStation = await page.context().request.post(url('/api/v1/location-dictionaries/metro/'), {
    headers: { 'X-CSRFToken': await getCsrfToken(page.context()) },
    data: { name: `E2E JSON станция ${marker}`, metroLineId: fixtureManifest.metroLineId },
  })
  assert.equal(createdStation.status(), 201, await createdStation.text())
  const station = await createdStation.json()
  trackCleanup(`/api/v1/location-dictionaries/metro/${station.id}/`)
  await page.goto(url('/app/complexes'))
  const photo = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 8
    canvas.getContext('2d').fillRect(0, 0, 8, 8)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  const payload = { version: 2, complexes: [{
    key: `browser:canonical:${marker}`, name: `E2E JSON ЖК ${marker}`,
    location: { fias_id: '110d6ad9-0b64-47cf-a2ee-7e935228799c' },
    developer: developer.name, real_estate_class: source.realEstateClass,
    real_estate_type: source.realEstateType, description: 'Изолированная проверка импорта',
    buildings: [{ number: '1', isActive: true }],
    metro: [{ station_id: station.id, mode: 'На транспорте', minutes: 25 }],
    photos: [{ name: 'fixture.png', data: photo }], sources: ['https://example.com/fixture'],
  }] }
  await page.getByText('Импорт жилых комплексов из JSON', { exact: true }).click()
  const upload = async (data, expected = 200) => {
    await page.getByLabel('Файл JSON', { exact: true }).setInputFiles({
      name: 'complexes.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)),
    })
    const reply = page.waitForResponse((response) => response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/complexes/import/')
    await page.getByRole('button', { name: 'Импортировать', exact: true }).click()
    const response = await reply
    assert.equal(response.status(), expected, await response.text())
    await page.getByRole('button', { name: 'Импортировать', exact: true }).click({ trial: true })
    assert.equal(await page.getByRole('button', { name: 'Импортировать', exact: true }).isEnabled(), true)
    return response.json()
  }
  assert.equal((await upload(payload)).created, 1)
  const complexId = (await read(`/api/v1/complexes/?q=${encodeURIComponent(payload.complexes[0].name)}`)).results.find((entry) => entry.name === payload.complexes[0].name).id
  trackCleanup(`/api/v1/complexes/${complexId}/`)
  const first = await read(`/api/v1/complexes/${complexId}/`)
  assert.equal(first.location.id, fixtureManifest.pushkinLocationId)
  assert.equal(first.districtId, null)
  assert.equal((await upload(payload)).created, 0)
  payload.complexes[0].location = { fias_id: '3eece910-1326-4602-aa21-e4ee117275ad' }
  payload.complexes[0].photos = []
  payload.complexes[0].metro = []
  await upload(payload)
  await upload(payload)
  const moved = await read(`/api/v1/complexes/${complexId}/`)
  assert.equal(moved.location.id, fixtureManifest.strelnaLocationId)
  assert.deepEqual(moved.buildings.map((entry) => entry.id), first.buildings.map((entry) => entry.id))
  assert.deepEqual(moved.metroAvailability, first.metroAvailability)
  assert.deepEqual(moved.photos.map((entry) => entry.id), first.photos.map((entry) => entry.id))

  const legacy = structuredClone(payload)
  legacy.version = 1
  const row = legacy.complexes[0]
  delete row.location
  Object.assign(row, { key: `browser:legacy:${marker}`, name: `E2E старый JSON ${marker}`,
    region_code: '78', region: 'Санкт-Петербург', city: 'Пушкин', district: 'Пушкинский район',
    metro: [{ station: station.name, line: station.metroLine.name, color: station.metroLine.color, mode: 'Пешком', minutes: 20 }],
    photos: [{ name: 'fixture.png', data: photo }] })
  assert.equal((await upload(legacy)).created, 1)
  const legacyId = (await read(`/api/v1/complexes/?q=${encodeURIComponent(row.name)}`)).results.find((entry) => entry.name === row.name).id
  trackCleanup(`/api/v1/complexes/${legacyId}/`)
  assert.equal((await upload(legacy)).created, 0)
  assert.equal((await read(`/api/v1/complexes/${legacyId}/`)).location.id, fixtureManifest.pushkinLocationId)
  const invalid = structuredClone(payload)
  invalid.complexes[0].location = { id: 99999999 }
  await upload(invalid, 400)
  await page.getByRole('alert').filter({ hasText: 'Населённый пункт не найден' }).waitFor()
  await upload(payload)
  const afterCounts = await Promise.all(['regions', 'cities', 'districts'].map(async (key) => (await read(`/api/v1/location-dictionaries/${key}/`)).totalCount))
  assert.deepEqual(afterCounts, oldCounts)
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
  }
})
