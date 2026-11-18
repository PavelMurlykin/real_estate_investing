import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

test('developer Location regions retain Pushkin and Strelna projects and repeat registry imports', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 180000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'administrator', { width: 1440, height: 1100 })
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
  const name = `E2E регионы ${Date.now()}`
  await page.goto(url('/app/developers/new'))
  await page.getByLabel('Название *', { exact: true }).fill(name)
  await page.getByLabel('ИНН', { exact: true }).fill('7812345678')
  await page.getByRole('combobox', { name: 'Регионы', exact: true }).fill('Санкт-Петербург')
  await page.getByRole('option', { name: /Санкт-Петербург/ }).click()
  const created = page.waitForResponse((reply) => reply.request().method() === 'POST'
    && new URL(reply.url()).pathname === '/api/v1/developers/')
  await page.getByRole('button', { name: 'Создать застройщика', exact: true }).click()
  const response = await created
  assert.equal(response.status(), 201, await response.text())
  const developer = await response.json()
  trackCleanup(`/api/v1/developers/${developer.id}/`)
  assert.equal(developer.regionLocations.length, 1)
  assert.equal(developer.regions.length, 1)
  const body = response.request().postDataJSON()
  assert.deepEqual(body.regionLocationIds, [developer.regionLocations[0].id])
  assert.ok(!Object.hasOwn(body, 'regionIds'))
  const template = await read(`/api/v1/properties/${fixtureManifest.propertyId}/`)
  const sourceProject = await read(`/api/v1/complexes/${template.realEstateComplexId}/`)
  const properties = []
  for (const [town, location] of [['Пушкин', fixtureManifest.pushkinLocationId], ['Стрельна', fixtureManifest.strelnaLocationId]]) {
    const project = await create('/api/v1/complexes/', {
      name: `${name} ${town}`, developerId: developer.id, locationId: location,
      realEstateClassId: sourceProject.realEstateClassId, realEstateTypeId: sourceProject.realEstateTypeId,
      buildings: [{ number: '1' }],
    })
    properties.push(await create('/api/v1/properties/', {
      buildingId: project.buildings[0].id, apartmentNumber: '1', area: '45.00', floor: 2,
      propertyCost: '5000000.00', layoutId: template.layoutId, decorationId: template.decorationId,
    }))
  }
  await page.goto(url(`/app/developers?q=${encodeURIComponent(name)}`))
  await page.getByRole('combobox', { name: 'Регион', exact: true }).fill('Санкт-Петербург')
  const filtered = page.waitForResponse((reply) => new URL(reply.url()).pathname === '/api/v1/developers/'
    && new URL(reply.url()).searchParams.has('regionLocationId'))
  await page.getByRole('option', { name: /Санкт-Петербург/ }).click()
  assert.equal((await (await filtered).json()).results[0].id, developer.id)
  await page.goto(url(`/app/developers/${developer.id}/edit`))
  await page.getByRole('button', { name: /Убрать:.*Санкт-Петербург/ }).waitFor()
  await page.getByLabel('Юридический адрес', { exact: true }).fill('Сохранённый адрес')
  const updated = page.waitForResponse((reply) => reply.request().method() === 'PATCH'
    && new URL(reply.url()).pathname === `/api/v1/developers/${developer.id}/`)
  await page.getByRole('button', { name: 'Сохранить изменения', exact: true }).click()
  const update = await updated
  assert.equal(update.status(), 200, await update.text())
  assert.ok(!Object.hasOwn(update.request().postDataJSON(), 'regionLocationIds'))
  await page.getByRole('heading', { name: 'Застройщики', exact: true }).waitFor()
  for (let repetition = 0; repetition < 2; repetition += 1) {
    await page.getByLabel('Файл ЕРЗ', { exact: true }).setInputFiles({
      name: 'developer-regions.csv', mimeType: 'text/csv',
      buffer: Buffer.from(`Застройщик;ИНН;Регион\n${name};7812345678;78\n`),
    })
    const imported = page.waitForResponse((reply) => reply.request().method() === 'POST'
      && new URL(reply.url()).pathname === '/api/v1/developers/import-registry/')
    await page.getByRole('button', { name: 'Импортировать', exact: true }).click()
    const importResponse = await imported
    assert.equal(importResponse.status(), 200, await importResponse.text())
    const summary = await importResponse.json()
    assert.equal(summary.createdDevelopers, 0)
    assert.equal(summary.createdDeveloperRegionLinks, 0)
    assert.deepEqual(summary.errors, [])
  }
  const old = await request.patch(url(`/api/v1/developers/${developer.id}/`), {
    headers, data: { regionIds: [developer.regions[0].id] },
  })
  assert.equal(old.status(), 200, await old.text())
  assert.deepEqual((await old.json()).regionLocations, developer.regionLocations)
  for (const apartment of properties) {
    const preserved = await read(`/api/v1/properties/${apartment.id}/`)
    assert.equal(preserved.buildingId, apartment.buildingId)
    assert.equal(preserved.propertyCost, apartment.propertyCost)
    assert.equal(preserved.developerId, developer.id)
  }
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto(url(`/app/developers/${developer.id}/edit`))
    await page.getByRole('combobox', { name: 'Регионы', exact: true }).waitFor()
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
  }
})
