import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

test('catalogs sort and filter Pushkin and Strelna consistently in React and Django', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 180000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  const request = page.context().request
  const url = (path) => new URL(path, isolatedBaseUrl).href
  const headers = { 'X-CSRFToken': await getCsrfToken(page.context()) }
  const read = async (path) => {
    const response = await request.get(url(path))
    assert.equal(response.status(), 200, await response.text())
    return response.json()
  }
  const create = async (path, data) => {
    const response = await request.post(url(path), { headers, data })
    assert.equal(response.status(), 201, await response.text())
    const result = await response.json()
    trackCleanup(`${path}${result.id}/`)
    return result
  }
  const template = await read(`/api/v1/properties/${fixtureManifest.propertyId}/`)
  const sourceProject = await read(`/api/v1/complexes/${template.realEstateComplexId}/`)
  const marker = `E2E каталог ${Date.now()}`
  const records = []
  for (const [name, identifier, prefix] of [
    ['Пушкин', fixtureManifest.pushkinLocationId, 'Я'], ['Стрельна', fixtureManifest.strelnaLocationId, 'А'],
  ]) {
    const location = await read(`/api/v1/location-catalogs/localities/${identifier}/`)
    const project = await create('/api/v1/complexes/', {
      name: `${prefix} ${marker} ${name}`, locationId: identifier,
      developerId: template.developerId, realEstateClassId: sourceProject.realEstateClassId,
      realEstateTypeId: sourceProject.realEstateTypeId, buildings: [{ number: '1' }],
    })
    const apartment = await create('/api/v1/properties/', {
      buildingId: project.buildings[0].id, apartmentNumber: 'NP-1', area: '45.00', floor: 3,
      propertyCost: '5000000.00', layoutId: template.layoutId, decorationId: template.decorationId,
    })
    records.push({ name, location, project, apartment })
  }
  const [pushkin, strelna] = records
  const catalogs = [
    { api: '/api/v1/complexes/', react: '/app/complexes', native: '/property/complexes/', key: 'project' },
    { api: '/api/v1/properties/', react: '/app/properties', native: '/property/', key: 'apartment' },
  ]
  for (const catalog of catalogs) {
    await page.goto(url(`${catalog.react}?search=${encodeURIComponent(marker)}&ordering=city&pageSize=1`))
    await page.locator('tbody').getByText(pushkin.project.name, { exact: true }).waitFor()
    const next = page.waitForResponse((response) => {
      const target = new URL(response.url())
      return target.pathname === catalog.api && target.searchParams.get('page') === '2'
    })
    await page.getByRole('button', { name: /Далее/ }).click()
    const secondPage = await (await next).json()
    assert.equal(secondPage.results[0].id, strelna[catalog.key].id)
    const sorted = page.waitForResponse((response) => {
      const target = new URL(response.url())
      return target.pathname === catalog.api && target.searchParams.get('ordering') === '-city'
    })
    await page.getByRole('button', { name: 'Населённый пункт', exact: true }).click()
    const descending = await (await sorted).json()
    assert.equal(descending.page, 1)
    assert.equal(descending.results[0].city, 'Стрельна')
    assert.equal(descending.results[0].district, 'Петродворцовый район')
    const filtered = page.waitForResponse((response) => {
      const target = new URL(response.url())
      return target.pathname === catalog.api && target.searchParams.get('localityId') === String(pushkin.location.id)
    })
    await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).fill('Пушкин')
    await page.getByRole('option', { name: /г\. Пушкин · Пушкинский/ }).click()
    const selected = await (await filtered).json()
    assert.equal(selected.totalCount, 1)
    assert.equal(selected.results[0].id, pushkin[catalog.key].id)

    await page.goto(url(`${catalog.native}?legacy=1&filter_city=999999&search=${encodeURIComponent(marker)}&sort_by=city`))
    await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).waitFor()
    const nativeFiltered = page.waitForResponse((response) => {
      const target = new URL(response.url())
      return target.pathname === catalog.native && target.searchParams.get('localityId') === String(strelna.location.id)
    })
    await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).fill('Стрельна')
    await page.getByRole('option', { name: /п\. Стрельна · Петродворцовый/ }).click()
    const nativeResponse = await nativeFiltered
    assert.equal(nativeResponse.status(), 200)
    assert.equal(new URL(nativeResponse.url()).searchParams.get('filter_city'), '')
    await page.locator('tbody').getByText(strelna.project.name, { exact: true }).waitFor()
    assert.equal(await page.locator('tbody').getByText(pushkin.project.name, { exact: true }).count(), 0)
    assert.match(await page.locator('tbody').innerText(), /Петродворцовый район/)
    assert.equal(new URL(page.url()).searchParams.get('legacy'), '1')
    if (catalog.key === 'apartment') {
      await page.getByRole('combobox', { name: 'ЖК', exact: true }).fill(strelna.project.name)
      await page.getByRole('option', { name: new RegExp(strelna.project.name) }).waitFor()
    }
  }
  const bindingUrl = `/api/v1/complexes/${pushkin.project.id}/locations/`
  const bindings = { locations: [
    { locationId: pushkin.location.id, isPrimary: true, isHistorical: false },
    { locationId: strelna.location.id, isPrimary: false, isHistorical: true },
  ], buildings: [{ id: pushkin.project.buildings[0].id, locationId: strelna.location.id }] }
  const changed = await request.put(url(bindingUrl), { headers, data: bindings })
  assert.equal(changed.status(), 200, await changed.text())
  try {
    for (const catalog of catalogs) {
      await page.goto(url(`${catalog.react}?search=${encodeURIComponent(marker)}&localityId=${strelna.location.id}&ordering=city`))
      await page.locator('tbody').getByText(pushkin.project.name, { exact: true }).waitFor()
      const rows = await read(`${catalog.api}?search=${encodeURIComponent(marker)}&localityId=${strelna.location.id}&ordering=city`)
      const row = rows.results.find((item) => item.id === pushkin[catalog.key].id)
      assert.equal(row.city, catalog.key === 'apartment' ? 'Стрельна' : 'Пушкин')
    }
    const preserved = await read(`/api/v1/properties/${pushkin.apartment.id}/`)
    assert.equal(preserved.buildingId, pushkin.apartment.buildingId)
    assert.equal(preserved.propertyCost, pushkin.apartment.propertyCost)
    for (const width of [1440, 360]) {
      await page.setViewportSize({ width, height: 1000 })
      for (const catalog of catalogs) {
        await page.goto(url(`${catalog.react}?search=${encodeURIComponent(marker)}`))
        await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).waitFor()
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
      }
    }
  } finally {
    bindings.buildings[0].locationId = null
    assert.equal((await request.put(url(bindingUrl), { headers, data: bindings })).status(), 200)
  }
})
