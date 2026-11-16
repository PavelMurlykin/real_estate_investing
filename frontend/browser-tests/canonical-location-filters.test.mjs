import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('filters Veren Village by Strelna, excludes historical links and respects building overrides', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 120000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'administrator', { width: 1440, height: 1000 })
  const request = page.context().request
  const url = (path) => new URL(path, isolatedBaseUrl).href
  const headers = { 'X-CSRFToken': await getCsrfToken(page.context()) }
  const template = await request.get(url(`/api/v1/properties/${fixtureManifest.propertyId}/`)).then((reply) => reply.json())
  const locality = async (name) => (await request.get(url(`/api/v1/locations/?category=locality&q=${encodeURIComponent(name)}`)).then((reply) => reply.json())).results.find((row) => row.name === name)
  const strelna = await locality('Стрельна')
  const pushkin = await locality('Пушкин')
  const created = []
  for (const [name, location] of [['Veren Village E2E', strelna], ['Пушкин E2E', pushkin]]) {
    const reply = await request.post(url('/api/v1/complexes/'), { headers, data: {
      name, developerId: template.developerId, realEstateClassId: 1, realEstateTypeId: 1,
      locationId: location.id, buildings: [{ number: 'E2E корпус' }],
    } })
    assert.equal(reply.status(), 201, await reply.text())
    const project = await reply.json()
    trackCleanup(`/api/v1/complexes/${project.id}/`)
    const apartmentReply = await request.post(url('/api/v1/properties/'), { headers, data: {
      buildingId: project.buildings[0].id, apartmentNumber: 'E2E', area: '50.00', floor: 1,
      propertyCost: '5000000.00', layoutId: template.layoutId, decorationId: template.decorationId,
    } })
    assert.equal(apartmentReply.status(), 201, await apartmentReply.text())
    const apartment = await apartmentReply.json()
    trackCleanup(`/api/v1/properties/${apartment.id}/`)
    created.push({ project, apartment })
  }
  const [veren, other] = created
  const ids = async (path) => new Set((await request.get(url(path)).then((reply) => reply.json())).results.map((row) => row.id))
  for (const [parameter, identifier] of [['regionLocationId', strelna.regionId], ['districtLocationId', strelna.parentId], ['localityId', strelna.id]]) {
    await page.goto(url(`/app/complexes?${parameter}=${identifier}`))
    await page.getByRole('link', { name: veren.project.name, exact: true }).waitFor()
    if (parameter !== 'regionLocationId') assert.equal(await page.getByRole('link', { name: other.project.name, exact: true }).count(), 0)
  }
  await page.goto(url(`/app/?localityId=${strelna.id}`))
  const homepage = page.getByRole('region', { name: 'Жилые комплексы по территориям' })
  await homepage.getByRole('heading', { name: veren.project.name, exact: true }).waitFor()
  assert.equal(await homepage.getByRole('heading', { name: other.project.name, exact: true }).count(), 0)
  await page.goto(url(`/app/properties?customerId=${fixtureManifest.otherCustomerId}&localityId=${strelna.id}`))
  await page.getByRole('cell', { name: veren.project.name, exact: true }).waitFor()
  assert.ok((await ids(`/api/v1/properties/?localityId=${strelna.id}`)).has(veren.apartment.id))
  assert.ok(!(await ids(`/api/v1/properties/?localityId=${pushkin.id}`)).has(veren.apartment.id))
  for (const calculator of ['mortgage', 'mortgage/trench']) {
    await page.goto(url(`/app/${calculator}`))
    await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).fill('Стрельна')
    await page.getByRole('option', { name: /Стрельна · Петродворцовый район/ }).click()
    await page.getByRole('combobox', { name: 'Объект недвижимости', exact: true }).click()
    await page.getByRole('option', { name: /Veren Village E2E/ }).waitFor()
    assert.equal(await page.getByRole('option', { name: /Пушкин E2E/ }).count(), 0)
  }
  const move = await request.patch(url(`/api/v1/complexes/${other.project.id}/`), { headers, data: { locationId: strelna.id } })
  assert.equal(move.status(), 200, await move.text())
  assert.ok(!(await ids(`/api/v1/complexes/?localityId=${pushkin.id}`)).has(other.project.id))
  const bindings = await request.get(url(`/api/v1/complexes/${other.project.id}/locations/`)).then((reply) => reply.json())
  assert.equal(bindings.locations.find((row) => row.id === pushkin.id).isHistorical, true)
  const override = await request.put(url(`/api/v1/complexes/${other.project.id}/locations/`), { headers, data: {
    locations: bindings.locations.map((row) => ({ locationId: row.id, isPrimary: row.isPrimary, isHistorical: row.isHistorical })),
    buildings: [{ id: other.project.buildings[0].id, locationId: pushkin.id }],
  } })
  assert.equal(override.status(), 200, await override.text())
  try {
    assert.ok((await ids(`/api/v1/properties/?localityId=${pushkin.id}`)).has(other.apartment.id))
    assert.ok(!(await ids(`/api/v1/properties/?localityId=${strelna.id}`)).has(other.apartment.id))
    for (const width of [1440, 360]) {
      await page.setViewportSize({ width, height: 1000 })
      await page.goto(url(`/app/complexes?localityId=${strelna.id}`))
      await page.getByRole('link', { name: veren.project.name, exact: true }).waitFor()
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
    }
  } finally {
    const inherited = await request.put(url(`/api/v1/complexes/${other.project.id}/locations/`), { headers, data: {
      locations: bindings.locations.map((row) => ({ locationId: row.id, isPrimary: row.isPrimary, isHistorical: row.isHistorical })),
      buildings: [{ id: other.project.buildings[0].id, locationId: null }],
    } })
    assert.equal(inherited.status(), 200, await inherited.text())
  }
})
