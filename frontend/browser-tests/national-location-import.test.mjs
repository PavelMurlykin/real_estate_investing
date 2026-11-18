import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  createAuthenticatedPage, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

test('location filters are live and import errors leave controls reusable after reload', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 120000,
}, async (context) => {
  const { page } = await createAuthenticatedPage(context, 'administrator', { width: 1440, height: 1100 })
  await page.goto(new URL('/app/locations/districts', isolatedBaseUrl).href)
  const filters = page.getByRole('region', { name: 'Фильтры: Административные районы' })
  await filters.waitFor()
  assert.equal(await filters.getByRole('button', { name: 'Найти', exact: true }).count(), 0)
  assert.equal(await filters.getByRole('combobox', { name: 'Статус', exact: true }).count(), 0)
  assert.equal(await filters.getByRole('combobox', { name: 'Сортировка', exact: true }).count(), 0)
  const tabs = await page.getByRole('navigation', { name: 'Справочники локаций' }).boundingBox()
  const action = await page.getByRole('button', { name: 'Обновить данные' }).boundingBox()
  assert.ok(Math.abs(tabs.y + tabs.height / 2 - action.y - action.height / 2) < 12)
  assert.ok(action.x >= tabs.x + tabs.width)
  await filters.getByLabel('Поиск', { exact: true }).fill('Тверской')
  await page.waitForURL((url) => url.searchParams.get('q') === 'Тверской')
  await page.goto(new URL('/app/locations/regions', isolatedBaseUrl).href)
  const importButton = page.getByRole('button', { name: 'Обновить данные', exact: true })
  let tries = 0
  const completed = { job: {
    id: '382079fb-2acf-48e1-a8ba-47d49a468d55', status: 'completed', phase: 'completed',
    processedCities: 2, totalCities: 2, currentCity: '', counts: {}, coverage: {},
    errorMessage: '', updatedAt: '2026-11-18T10:00:00Z',
  } }
  await page.route('**/api/v1/location-imports/', async (route) => {
    if (route.request().method() !== 'POST') return route.fulfill({ json: tries >= 2 ? completed : { job: null } })
    assert.deepEqual(route.request().postDataJSON(), {})
    tries += 1
    await route.fulfill({ json: tries === 1 ? { bad: true } : completed })
  })
  await importButton.click()
  await page.getByRole('alert').filter({ hasText: 'Сервер вернул данные в неожиданном формате.' }).waitFor()
  assert.equal(await importButton.isEnabled(), true)
  await page.reload()
  await importButton.waitFor()
  assert.equal(await importButton.isEnabled(), true)
  assert.equal(await importButton.count(), 1)
  await importButton.click()
  const notice = page.getByRole('status').filter({ hasText: 'Справочники обновлены' })
  await notice.waitFor()
  assert.equal(await importButton.isEnabled(), true)
  assert.equal(tries, 2)
  await notice.getByRole('button', { name: 'Закрыть уведомление' }).click()
  await notice.waitFor({ state: 'hidden' })
  await importButton.click()
  await notice.waitFor()
  const restored = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/v1/location-imports/')
  await page.reload()
  assert.equal((await restored).status(), 200)
  await importButton.waitFor()
  assert.equal(await notice.count(), 0)
})

test('national import starts with no selected parents and survives a browser reload', {
  skip: isolatedWritesEnabled && process.env.BROWSER_TEST_LOCATION_LIVE === '1' ? false : 'requires explicit live import', timeout: 240000,
}, async (context) => {
  const { page } = await createAuthenticatedPage(context, 'administrator', { width: 1280, height: 1000 })
  await page.goto(new URL('/app/locations/cities', isolatedBaseUrl).href)
  const button = page.getByRole('button', { name: 'Обновить данные' })
  await button.click()
  const endpoint = new URL('/api/v1/location-imports/', isolatedBaseUrl).href
  let job
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const response = await page.context().request.get(endpoint)
    job = (await response.json()).job
    assert.notEqual(job?.status, 'failed', job?.errorMessage)
    if (job?.totalRegions >= 85 && job?.processedCities > 1000) break
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  assert.ok(job?.totalRegions >= 85 && job?.processedCities > 1000)
  const again = await page.context().request.post(endpoint, {
    data: {}, headers: { 'X-CSRFToken': await getCsrfToken(page.context()) },
  })
  assert.equal(again.status(), 202)
  assert.equal((await again.json()).job.id, job.id)
  await page.reload()
  await page.locator('.location-update button[aria-busy="true"]').waitFor()
  assert.equal(await button.isDisabled(), true)
  const cities = await page.context().request.get(new URL('/api/v1/locations/?category=locality&pageSize=100', isolatedBaseUrl).href)
  assert.ok((await cities.json()).totalCount >= 1000)
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
    if (process.env.BROWSER_TEST_SCREENSHOTS) {
      await page.screenshot({ path: `${process.env.BROWSER_TEST_SCREENSHOTS}/national-import-${width}.png`, fullPage: true })
    }
  }
  console.log(JSON.stringify({ nationalImport: job }))
})
