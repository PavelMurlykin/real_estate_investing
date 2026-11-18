import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, fixtureManifest, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('finds Pushkin and Strelna and refines complex territory without changing legacy references', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 90000,
}, async (context) => {
  const { page } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  await page.goto(new URL('/app/locations/localities', isolatedBaseUrl).href)
  assert.equal(await page.getByRole('button', { name: 'Обновить данные' }).count(), 0)
  const search = page.getByRole('region', { name: 'Фильтры: Населённые пункты' })
    .getByLabel('Поиск', { exact: true })
  await search.fill('Пушкин')
  await page.getByRole('cell', { name: 'Пушкин', exact: true }).waitFor()
  await page.getByRole('cell', { name: 'Пушкинский район', exact: true }).waitFor()
  await search.fill('Стрельна')
  await page.getByRole('cell', { name: 'Стрельна', exact: true }).waitFor()
  await page.getByRole('cell', { name: 'Петродворцовый район', exact: true }).waitFor()
  const complexPath = `/api/v1/complexes/${fixtureManifest.geographyComplexId}/`
  const original = await page.context().request.get(new URL(complexPath, isolatedBaseUrl).href).then((response) => response.json())
  await page.goto(new URL(`/app/complexes/${fixtureManifest.geographyComplexId}`, isolatedBaseUrl).href)
  const panel = page.getByRole('region', { name: 'Территории ЖК', exact: true })
  const territory = panel.getByRole('combobox', { name: 'Территория 1 *', exact: true })
  await territory.fill('Пушкин')
  await page.getByRole('option', { name: /г\. Пушкин · Пушкинский/ }).click()
  await panel.getByRole('button', { name: 'Сохранить территории ЖК', exact: true }).click()
  await panel.getByText(/г\. Пушкин · Пушкинский район · Санкт-Петербург · основная/).waitFor()
  await page.reload()
  await panel.getByText(/г\. Пушкин · Пушкинский район · Санкт-Петербург · основная/).waitFor()
  const current = await page.context().request.get(new URL(complexPath, isolatedBaseUrl).href).then((response) => response.json())
  assert.equal(current.districtId, original.districtId)
  assert.deepEqual(current.metroAvailability, original.metroAvailability)
  assert.deepEqual(current.buildings.map((row) => row.id), original.buildings.map((row) => row.id))
  const bindings = await page.context().request.get(new URL(`${complexPath}locations/`, isolatedBaseUrl).href).then((response) => response.json())
  assert.equal(bindings.locations[0].id, fixtureManifest.pushkinLocationId)
  assert.equal(bindings.buildings[0].effectiveLocationId, fixtureManifest.pushkinLocationId)
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
    if (process.env.BROWSER_TEST_SCREENSHOTS) await page.screenshot({ path: `${process.env.BROWSER_TEST_SCREENSHOTS}/geography-${width}.png`, fullPage: true })
  }
})
