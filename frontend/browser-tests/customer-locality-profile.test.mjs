import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('edits residence and purchase geography in React and Django while retaining financial region and ownership', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 120000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'owner', { width: 1440, height: 1100 })
  const url = (path) => new URL(path, isolatedBaseUrl).href
  const read = async (path) => (await page.context().request.get(url(path))).json()
  const localities = (await read('/api/v1/locations/?category=locality&q=%D0%9F%D1%83%D1%88%D0%BA%D0%B8%D0%BD')).results
  const pushkin = localities.find((row) => row.name === 'Пушкин')
  const strelna = (await read('/api/v1/locations/?category=locality&q=%D0%A1%D1%82%D1%80%D0%B5%D0%BB%D1%8C%D0%BD%D0%B0')).results.find((row) => row.name === 'Стрельна')
  const programs = await read('/api/v1/catalog-options/preferential-programs/')
  await page.goto(url('/app/customers/new'))
  await page.getByLabel('Имя *', { exact: true }).fill('E2E новые локации клиента')
  for (const [label, name] of [['Населённый пункт проживания', 'Пушкин'], ['Населённый пункт покупки', 'Стрельна']]) {
    await page.getByRole('combobox', { name: label, exact: true }).fill(name)
    await page.getByRole('option', { name: new RegExp(`${name} ·`) }).click()
  }
  if (programs.results.length) {
    await page.getByRole('combobox', { name: 'Доступные льготные программы', exact: true }).click()
    await page.getByRole('option', { name: programs.results[0].label, exact: true }).click()
  }
  const created = page.waitForResponse((reply) => reply.request().method() === 'POST' && new URL(reply.url()).pathname === '/api/v1/customers/')
  await page.getByRole('button', { name: 'Сохранить клиента', exact: true }).click()
  const response = await created
  assert.equal(response.status(), 201, await response.text())
  const { id } = await response.json()
  trackCleanup(`/api/v1/customers/${id}/`)
  const before = await read(`/api/v1/customers/${id}/`)
  assert.equal(before.residenceLocalityId, pushkin.id)
  assert.equal(before.desiredLocalityId, strelna.id)
  assert.equal(before.desiredRegionLocationId, strelna.regionId)
  assert.equal(before.residenceCityId, null)
  assert.equal(before.desiredCityId, null)
  await page.waitForURL(`**/app/customers/${id}`)
  const selectionLink = page.getByRole('link', { name: 'Рассчитать ипотеку', exact: true })
  const selection = new URL(await selectionLink.getAttribute('href'), isolatedBaseUrl)
  assert.equal(selection.searchParams.get('localityId'), String(strelna.id))
  assert.equal(selection.searchParams.get('customerId'), String(id))
  await page.goto(url(`/app/customers/${id}/edit`))
  const residence = page.getByRole('combobox', { name: 'Населённый пункт проживания', exact: true })
  await residence.fill('Стрельна')
  await page.getByRole('option', { name: /Стрельна · Петродворцовый/ }).click()
  const edited = page.waitForResponse((reply) => reply.request().method() === 'PATCH' && new URL(reply.url()).pathname === `/api/v1/customers/${id}/`)
  await page.getByRole('button', { name: 'Сохранить клиента', exact: true }).click()
  assert.equal((await edited).status(), 200)
  const after = await read(`/api/v1/customers/${id}/`)
  assert.equal(after.desiredFinancialRegionId, before.desiredFinancialRegionId)
  assert.equal(after.calculated.preferentialCreditLimit, before.calculated.preferentialCreditLimit)
  assert.deepEqual(after.preferentialPrograms, before.preferentialPrograms)

  await page.goto(url(`/customers/${id}/update/?legacy=1`))
  const nativeLocality = page.getByRole('combobox', { name: /^Населённый пункт покупки/ })
  const nativeDistrict = page.getByRole('combobox', { name: /^Административный район покупки/ })
  const nativeRegion = page.getByRole('combobox', { name: /^Регион покупки/ })
  await nativeDistrict.fill('Пушкинский')
  await page.getByRole('option', { name: /Пушкинский район/ }).click()
  await nativeRegion.click()
  await page.getByRole('option', { name: 'Не указано', exact: true }).click()
  await nativeRegion.fill('Санкт-Петербург')
  await page.getByRole('option', { name: /Санкт-Петербург/ }).click()
  await nativeLocality.fill('Стрельна')
  await page.getByRole('option', { name: /Стрельна · Петродворцовый/ }).click()
  await nativeDistrict.fill('Пушкинский')
  await page.getByRole('option', { name: /Пушкинский район/ }).click()
  assert.equal(await nativeLocality.inputValue(), '')
  const geographicReply = page.waitForResponse((reply) => {
    const target = new URL(reply.url())
    return target.pathname === '/api/v1/catalog-options/locations/' && target.searchParams.get('q') === 'Пушкин'
  })
  await nativeLocality.fill('Пушкин')
  const geographicResponse = await geographicReply
  const geographicData = await geographicResponse.json()
  assert.ok(geographicData.results.some((row) => row.id === pushkin.id), JSON.stringify({ url: geographicResponse.url(), results: geographicData.results }))
  await page.getByRole('option', { name: /г\. Пушкин · Пушкинский/ }).click()
  const nativeSaved = page.waitForResponse((reply) => reply.request().method() === 'POST' && new URL(reply.url()).pathname === `/customers/${id}/update/`)
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  assert.equal((await nativeSaved).status(), 302)
  const native = await read(`/api/v1/customers/${id}/`)
  assert.equal(native.desiredLocalityId, pushkin.id)
  assert.equal(native.desiredFinancialRegionId, before.desiredFinancialRegionId)
  assert.equal(native.calculated.preferentialCreditLimit, before.calculated.preferentialCreditLimit)
  assert.deepEqual(native.preferentialPrograms, before.preferentialPrograms)
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto(url(`/app/customers/${id}/edit`))
    await page.getByLabel('Имя *', { exact: true }).waitFor()
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
  }
  await page.getByRole('combobox', { name: 'Регион покупки', exact: true }).click()
  await page.getByRole('option', { name: 'Не выбрано', exact: true }).click()
  const cleared = page.waitForResponse((reply) => reply.request().method() === 'PATCH' && new URL(reply.url()).pathname === `/api/v1/customers/${id}/`)
  await page.getByRole('button', { name: 'Сохранить клиента', exact: true }).click()
  assert.equal((await cleared).status(), 200)
  const empty = await read(`/api/v1/customers/${id}/`)
  assert.equal(empty.desiredLocalityId, null)
  assert.equal(empty.desiredRegionLocationId, null)
  assert.equal(empty.desiredFinancialRegionId, null)
  const other = await createAuthenticatedPage(context, 'other', { width: 1440, height: 1000 })
  assert.equal((await other.page.context().request.get(url(`/api/v1/customers/${id}/`))).status(), 404)
})
