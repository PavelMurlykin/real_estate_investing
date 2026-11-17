import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

test('saved mortgage and tranche histories use Pushkin and Strelna without changing finances or customer links', {
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
  const template = await read(`/api/v1/properties/${fixtureManifest.propertyId}/`)
  const templateProject = await read(`/api/v1/complexes/${template.realEstateComplexId}/`)
  const towns = []
  for (const [name, localityId] of [
    ['Пушкин', fixtureManifest.pushkinLocationId], ['Стрельна', fixtureManifest.strelnaLocationId],
  ]) {
    const project = await create('/api/v1/complexes/', {
      name: `E2E расчёты ${name} ${Date.now()}`, locationId: localityId,
      developerId: template.developerId, realEstateClassId: templateProject.realEstateClassId,
      realEstateTypeId: templateProject.realEstateTypeId, buildings: [{ number: '1' }],
    })
    const apartment = await create('/api/v1/properties/', {
      buildingId: project.buildings[0].id, apartmentNumber: 'NP-1', area: '45.00', floor: 3,
      propertyCost: '5000000.00', layoutId: template.layoutId, decorationId: template.decorationId,
    })
    towns.push({ name, localityId, project, apartment })
  }
  const customer = await create('/api/v1/customers/', {
    firstName: `E2E расчёты ${Date.now()}`, desiredLocalityId: towns[1].localityId,
  })
  const parameters = {
    propertyCost: '5000000.00', priceAdjustmentType: 'discount', priceAdjustmentUnit: 'percent',
    priceAdjustmentValue: '10.00', initialPaymentUnit: 'percent', initialPaymentValue: '20.00',
    initialPaymentDate: '2026-01-15', mortgageTermMonths: 12, annualRate: '12.00', hasGracePeriod: false,
  }
  const histories = [
    { api: '/api/v1/mortgage/calculations/', react: '/app/mortgage/calculations', native: '/mortgage/calculations/', program: 'market' },
    { api: '/api/v1/mortgage/trench/calculations/', react: '/app/mortgage/trench/calculations', native: '/mortgage/trench-calculations/', program: 'trench' },
  ]
  const saved = []
  for (const town of towns) {
    for (const history of histories) {
      const calculationParameters = history.program === 'market' ? parameters : {
        ...parameters, mortgageTermMonths: 24, trenches: [
          { date: '2026-01-15', amountUnit: 'percent', amountValue: '40.00', annualRate: '12.00' },
          { date: '2026-07-15', amountUnit: 'rubles', amountValue: null, annualRate: '10.00' },
        ],
      }
      const result = await create(history.api, {
        propertyId: town.apartment.id, customerId: customer.id, parameters: calculationParameters,
      })
      saved.push({ history, town, result, before: await read(`${history.api}${result.id}/`) })
    }
  }
  const customerEndpoint = `/api/v1/customers/${customer.id}/calculations/`
  const linksBefore = await read(customerEndpoint)
  assert.equal(linksBefore.totalCount, 4)
  const chooseLocality = async (endpoint, town) => {
    const pending = page.waitForResponse((response) => {
      const target = new URL(response.url())
      return target.pathname === endpoint && target.searchParams.get('localityId') === String(town.localityId)
    })
    await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).fill(town.name)
    await page.getByRole('option', { name: new RegExp(`${town.name} ·`) }).click()
    const response = await pending
    assert.equal(response.status(), 200)
    const result = await response.json()
    assert.ok(result.results.length)
    assert.ok(result.results.every((row) => row.property.localityId === town.localityId))
    await page.locator('tbody').getByText(town.project.name, { exact: true }).first().waitFor()
    assert.match(await page.locator('tbody').innerText(), new RegExp(town.name))
    assert.match(await page.locator('tbody').innerText(), /Санкт-Петербург/)
  }
  for (const history of histories) {
    await page.goto(url(history.react))
    await chooseLocality(history.api, towns[0])
    assert.equal(new URL(page.url()).searchParams.get('localityId'), String(towns[0].localityId))
    await chooseLocality(history.api, towns[1])
    await page.goto(url(`${history.react}?q=${encodeURIComponent('Пушкин')}`))
    await page.locator('tbody').getByText(towns[0].project.name, { exact: false }).waitFor()
    assert.equal(await page.locator('tbody').getByText(towns[1].project.name, { exact: false }).count(), 0)
    const filtered = await read(`${history.api}?q=${encodeURIComponent('Стрельна')}`)
    assert.ok(filtered.results.some((row) => row.property.localityId === towns[1].localityId))

    await page.goto(url(`${history.native}?legacy=1`))
    const pending = page.waitForResponse((response) => {
      const target = new URL(response.url())
      return target.pathname === history.native && target.searchParams.get('localityId') === String(towns[0].localityId)
    })
    await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).fill('Пушкин')
    await page.getByRole('option', { name: /г\. Пушкин · Пушкинский/ }).click()
    assert.equal((await pending).status(), 200)
    await page.locator('tbody').getByText(towns[0].project.name, { exact: false }).waitFor()
    assert.equal(await page.locator('tbody').getByText(towns[1].project.name, { exact: false }).count(), 0)
    assert.equal(new URL(page.url()).searchParams.get('legacy'), '1')
    const regionChanged = page.waitForResponse((response) => {
      const target = new URL(response.url())
      return target.pathname === history.native && target.searchParams.get('regionLocationId')
        && !target.searchParams.get('localityId')
    })
    await page.getByRole('combobox', { name: 'Регион', exact: true }).fill('Санкт-Петербург')
    await page.getByRole('option', { name: /Санкт-Петербург/ }).click()
    assert.equal((await regionChanged).status(), 200)
    assert.equal(await page.locator('select[name="localityId"]').inputValue(), '')
    await page.locator('tbody').getByText(towns[1].project.name, { exact: false }).waitFor()
  }
  await page.goto(url(`/app/customers/${customer.id}`))
  await chooseLocality(customerEndpoint, towns[1])
  assert.equal(new URL(page.url()).searchParams.get('calculationLocalityId'), String(towns[1].localityId))
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    for (const path of [histories[0].react, histories[1].react, `/app/customers/${customer.id}`]) {
      await page.goto(url(path))
      await page.getByRole('combobox', { name: 'Населённый пункт', exact: true }).waitFor()
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    }
  }
  for (const record of saved) {
    assert.deepEqual(await read(`${record.history.api}${record.result.id}/`), record.before)
  }
  assert.deepEqual(await read(customerEndpoint), linksBefore)
  const { page: other } = await createAuthenticatedPage(context, 'other', { width: 1280, height: 900 })
  for (const record of saved) {
    assert.equal((await other.request.get(url(`${record.history.api}${record.result.id}/`))).status(), 404)
  }
  assert.equal((await other.request.get(url(customerEndpoint))).status(), 404)
})
