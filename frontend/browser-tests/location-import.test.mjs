import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  createAuthenticatedPage,
  getCsrfToken,
  isolatedBaseUrl,
  isolatedWritesEnabled,
} from './isolated-helpers.mjs'

for (const role of ['owner', 'moderator']) {
  test(`location import is forbidden for ${role}`, {
    skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack',
  }, async (context) => {
    const { page } = await createAuthenticatedPage(context, role, { width: 1280, height: 900 })
    await page.goto(new URL('/app/locations/regions', isolatedBaseUrl).href)
    await page.getByRole('heading', { name: 'Регионы', exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'Обновить данные' }).count(), 0)
    const response = await page.context().request.post(
      new URL('/api/v1/location-dictionaries/regions/import/', isolatedBaseUrl).href,
      { data: {}, headers: { 'X-CSRFToken': await getCsrfToken(page.context()) } },
    )
    assert.equal(response.status(), 403)
  })
}

test('administrator sees accessible import controls on desktop and phone', {
  skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack',
}, async (context) => {
  const { page } = await createAuthenticatedPage(context, 'administrator', { width: 1280, height: 1000 })
  await page.goto(new URL('/app/locations/cities', isolatedBaseUrl).href)
  const button = page.getByRole('button', { name: 'Обновить данные' })
  await button.waitFor()
  assert.equal(await button.isEnabled(), true)
  assert.equal(await button.count(), 1)
  await page.goto(new URL('/app/locations/regions', isolatedBaseUrl).href)
  await button.waitFor()
  assert.equal(await button.isEnabled(), true)
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => (
      document.documentElement.scrollWidth <= document.documentElement.clientWidth
    )), true)
    if (process.env.BROWSER_TEST_SCREENSHOTS) {
      await page.screenshot({ path: `${process.env.BROWSER_TEST_SCREENSHOTS}/location-import-controls-${width}.png`, fullPage: true })
    }
  }
  await page.goto(new URL('/app/locations/metro', isolatedBaseUrl).href)
  await button.waitFor()
  assert.equal(await button.count(), 1)
  assert.equal(await button.isDisabled(), true)
})

test('legacy import API still updates regions, city districts and metro without duplicates', {
  skip: isolatedWritesEnabled && process.env.BROWSER_TEST_LOCATION_LIVE === '1'
    ? false : 'requires isolated stack and BROWSER_TEST_LOCATION_LIVE=1',
  timeout: 900000,
}, async (context) => {
  const { page } = await createAuthenticatedPage(context, 'administrator', { width: 1280, height: 1000 })
  const cityName = process.env.BROWSER_TEST_LOCATION_CITY || 'Санкт-Петербург'
  const regionName = process.env.BROWSER_TEST_LOCATION_REGION || cityName
  const results = []
  const request = page.context().request
  const headers = { 'X-CSRFToken': await getCsrfToken(page.context()) }
  async function importDictionary(key, parents = {}) {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const response = await request.post(new URL(`/api/v1/location-dictionaries/${key}/import/`, isolatedBaseUrl).href, {
        headers, data: parents, timeout: 60000,
      })
      const result = await response.json()
      console.log(JSON.stringify({ locationImport: key, attempt: attempt + 1, result }))
      if (response.status() === 200) {
        results.push({ dictionary: key, ...result })
        return result
      }
      assert.equal(response.status(), 502, JSON.stringify(result))
      if (attempt === 2) assert.fail(`Live source unavailable: ${JSON.stringify(result)}`)
      await new Promise((resolve) => setTimeout(resolve, 3000))
    }
  }
  const regions = await importDictionary('regions')
  assert.ok(regions.created + regions.updated + regions.unchanged >= 70)
  const regionsAgain = await importDictionary('regions')
  assert.equal(regionsAgain.created, 0)
  assert.equal(regionsAgain.updated, 0)
  const regionResponse = await page.context().request.get(new URL(
    `/api/v1/location-dictionaries/regions/?q=${encodeURIComponent(regionName)}`, isolatedBaseUrl,
  ).href)
  const region = (await regionResponse.json()).results.find((row) => row.name === regionName)
  assert.ok(region)
  const cities = await importDictionary('cities', { regionId: String(region.id) })
  assert.ok(cities.created + cities.updated + cities.unchanged > 0)
  const citiesAgain = await importDictionary('cities', { regionId: String(region.id) })
  assert.equal(citiesAgain.created, 0)
  assert.equal(citiesAgain.updated, 0)
  const cityResponse = await page.context().request.get(new URL(
    `/api/v1/location-dictionaries/cities/?q=${encodeURIComponent(cityName)}&regionId=${region.id}`, isolatedBaseUrl,
  ).href)
  const city = (await cityResponse.json()).results.find((row) => row.name === cityName)
  assert.ok(city)
  const parents = { regionId: String(region.id), cityId: String(city.id) }
  const districts = await importDictionary('districts', parents)
  assert.ok(districts.created + districts.updated + districts.unchanged > 0)
  const districtsAgain = await importDictionary('districts', parents)
  assert.equal(districtsAgain.created, 0)
  assert.equal(districtsAgain.updated, 0)
  const metro = await importDictionary('metro', parents)
  assert.ok(metro.created + metro.updated + metro.unchanged > 0)
  const metroAgain = await importDictionary('metro', parents)
  assert.equal(metroAgain.created, 0)
  assert.equal(metroAgain.updated, 0)
  assert.equal(metroAgain.lines.created, 0)
  assert.equal(metroAgain.lines.updated, 0)
  assert.equal(metroAgain.unchanged, metro.created + metro.updated + metro.unchanged)
  const stationTable = await page.context().request.get(new URL(
    `/api/v1/location-dictionaries/metro/?cityId=${city.id}&pageSize=100`, isolatedBaseUrl,
  ).href)
  assert.equal((await stationTable.json()).totalCount, metroAgain.unchanged)
  await page.goto(new URL('/app/locations/metro', isolatedBaseUrl).href)
  if (process.env.BROWSER_TEST_SCREENSHOTS) {
    await page.screenshot({ path: `${process.env.BROWSER_TEST_SCREENSHOTS}/location-import-desktop.png`, fullPage: true })
  }
  await page.setViewportSize({ width: 360, height: 900 })
  assert.equal(await page.evaluate(() => (
    document.documentElement.scrollWidth <= document.documentElement.clientWidth
  )), true)
  if (process.env.BROWSER_TEST_SCREENSHOTS) {
    await page.screenshot({ path: `${process.env.BROWSER_TEST_SCREENSHOTS}/location-import-mobile.png`, fullPage: true })
  }
  console.log(JSON.stringify({ liveLocationImport: results }))
})
