import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { baseUrl, createPage, screenshot } from './helpers.mjs'
import { assertReactPageLayout } from './page-layout-helpers.mjs'

const fixtures = JSON.parse(await readFile(new URL('./feedback-fixtures.json', import.meta.url), 'utf8'))
const anonymous = { isAuthenticated: false, user: null, capabilities: { manageCatalogs: false, syncExternalData: false, viewPrivateRecords: false, viewAllPrivateRecords: false } }

for (const width of [360, 1280]) for (const mode of ['market', 'trench']) {
  test(`async mortgage ${mode} options recover by keyboard without losing inputs at ${width}px`, async (context) => {
    const page = await createPage(context, { width, height: 900 })
    let failed = true
    await page.route('**/api/v1/mortgage/options/', (route) => failed
      ? route.fulfill({ status: 503, json: { detail: 'Временный сбой.' } }) : route.fallback())
    await page.goto(baseUrl + '/app/mortgage' + (mode === 'trench' ? '/trench' : ''))
    const error = page.getByRole('alert', { name: /Программы банков временно недоступны/ })
    await error.waitFor()
    const cost = page.getByLabel('Базовая стоимость, ₽', { exact: true })
    await cost.fill('6123456')
    await assertReactPageLayout(page)
    failed = false
    await error.getByRole('button', { name: 'Повторить', exact: true }).focus()
    await page.keyboard.press('Enter')
    await error.waitFor({ state: 'hidden' })
    await page.getByRole('combobox', { name: 'Банк', exact: true }).and(page.locator(':enabled')).waitFor()
    assert.equal(await cost.inputValue(), '6123456')
    assert.equal(await page.getByRole('combobox', { name: 'Банк', exact: true }).isEnabled(), true)
    await assertReactPageLayout(page)
  })
}

for (const width of [360, 768, 1280]) for (const theme of ['light', 'dark']) {
  test(`async states support loading, failed retry, recovery and empty filters in ${theme} at ${width}px`, async (context) => {
    const page = await createPage(context, { width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.addInitScript((value) => localStorage.setItem('theme-preference', value), theme)
    let phase = 'loading'
    let release
    let gate = new Promise((resolve) => { release = resolve })
    let requests = 0
    let retryStarted
    let started
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      if (new URL(request.url()).pathname === '/api/v1/auth/session/') return route.fulfill({ json: fixtures.administrator })
      requests++
      if (phase === 'loading' || phase === 'retry') { retryStarted?.(); await gate }
      if (phase === 'error') return route.fulfill({ status: 503, json: { detail: 'Временный сбой.' } })
      return route.fulfill({ json: phase === 'empty' ? { ...fixtures.banks, results: [], totalCount: 0 } : fixtures.banks })
    })
    await page.goto(baseUrl + '/app/banks?customerId=42&q=Северный')
    const main = page.getByRole('main')
    await main.getByRole('status', { name: 'Загрузка данных', exact: true }).waitFor()
    assert.equal(await main.locator('.async-state__spinner').evaluate((element) => getComputedStyle(element).animationName), 'none')
    await assertReactPageLayout(page)
    await screenshot(page, `async-loading-${theme}-${width}.png`)
    phase = 'error'
    release()
    await main.getByRole('alert').waitFor()
    await assertReactPageLayout(page)
    await screenshot(page, `async-error-${theme}-${width}.png`)
    for (const nextPhase of ['error', 'ready']) {
      phase = 'retry'
      gate = new Promise((resolve) => { release = resolve })
      started = new Promise((resolve) => { retryStarted = resolve })
      const before = requests
      await main.getByRole('button', { name: 'Повторить', exact: true }).focus()
      await page.keyboard.press('Enter')
      await started
      await page.keyboard.press('Enter')
      assert.equal(requests, before + 1, 'Retry must not restart an active request')
      phase = nextPhase
      release()
      if (nextPhase === 'error') {
        await main.getByRole('button', { name: 'Повторить', exact: true }).waitFor()
        await page.waitForFunction(() => document.activeElement?.matches('[data-async-retry]'))
      } else {
        await main.getByRole('heading', { level: 1 }).waitFor()
        await page.waitForFunction(() => document.activeElement === document.querySelector('main h1'))
      }
    }
    assert.equal(new URL(page.url()).searchParams.get('customerId'), '42')
    phase = 'empty'
    await page.getByLabel('Поиск', { exact: true }).fill('нет такого банка')
    await main.locator('.async-state--empty').waitFor()
    await assertReactPageLayout(page)
    await screenshot(page, `async-empty-${theme}-${width}.png`)
    phase = 'ready'
    await page.getByRole('button', { name: 'Сбросить', exact: true }).focus()
    await page.keyboard.press('Space')
    await main.getByRole('table', { name: 'Список банков' }).waitFor()
    assert.equal(new URL(page.url()).searchParams.get('customerId'), '42')
    assert.equal(new URL(page.url()).searchParams.has('q'), false)
  })
}

test('async session errors remain retryable on private React pages', async (context) => {
  const page = await createPage(context, { width: 360, height: 900 })
  let failed = true
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname
    const session = path === '/api/v1/auth/session/'
    if (session && !failed) return route.fulfill({ json: anonymous })
    if (path.startsWith('/api/v1/property-dictionaries/')) return route.fulfill({ json: fixtures.dictionary })
    if (path.startsWith('/api/v1/location-dictionaries/options/')) return route.fulfill({ json: fixtures.locationOptions })
    if (path.startsWith('/api/v1/location-dictionaries/cities/')) return route.fulfill({ json: { page: 1, pageSize: 20, totalPages: 1, totalCount: 1, results: [fixtures.city] } })
    return route.fulfill({ status: 503, json: { detail: 'Временный сбой.' } })
  })
  for (const route of ['customers', 'customers/new', 'customers/12', 'properties/new', 'developers/new', 'company-groups/new',
    'banks/new', 'mortgage-programs/new', 'developer-programs/new', 'complexes/new', 'mortgage/calculations',
    'mortgage/trench/calculations', 'mortgage/calculations/7', 'mortgage/trench/calculations/17',
    'profile', 'password/change', 'dictionaries/real-estate-classes/7/edit', 'locations/cities/2/edit']) {
    failed = true
    await page.goto(baseUrl + '/app/' + route)
    const main = page.getByRole('main')
    await main.locator('.async-state--error').waitFor()
    await assertReactPageLayout(page)
    failed = false
    await main.getByRole('button', { name: 'Повторить', exact: true }).focus()
    await page.keyboard.press('Enter')
    await main.locator('.async-state--error').waitFor({ state: 'hidden' })
    await assertReactPageLayout(page)
  }
})

test('async session retries show a shared pending state in the page and sidebar', async (context) => {
  const page = await createPage(context, { width: 1280, height: 900 })
  let phase = 'error'
  let release
  let started
  const pending = new Promise((resolve) => { release = resolve })
  const requestStarted = new Promise((resolve) => { started = resolve })
  context.after(() => release())
  await page.route('**/api/**', async (route) => {
    if (phase === 'pending') { started(); await pending }
    return phase === 'ready' ? route.fulfill({ json: anonymous }) : route.fulfill({ status: 503, json: { detail: 'Временный сбой.' } })
  })
  await page.goto(baseUrl + '/app/customers')
  const main = page.getByRole('main')
  await main.getByRole('button', { name: 'Повторить', exact: true }).waitFor()
  phase = 'pending'
  await main.getByRole('button', { name: 'Повторить', exact: true }).click()
  await requestStarted
  await page.waitForFunction(() => [...document.querySelectorAll('[data-async-retry]')].every((button) => button.disabled))
  phase = 'ready'
  release()
  await main.locator('.async-state--empty').waitFor()
  await assertReactPageLayout(page)
})
