import assert from 'node:assert/strict'
import { test } from 'node:test'
import { baseUrl, createPage, screenshot } from './helpers.mjs'
import { assertReactPageLayout } from './page-layout-helpers.mjs'
import { assertFocusedControlVisible, assertFormTraversal } from './final-audit-helpers.mjs'

const anonymous = { isAuthenticated: false, user: null, capabilities: { manageCatalogs: false, syncExternalData: false, viewPrivateRecords: false, viewAllPrivateRecords: false } }
const options = { defaultInitialPaymentDate: '2026-11-15', keyRate: '16.00', banks: [], programs: [] }
const variants = Array.from({ length: 12 }, (_, index) => ({ id: index + 1, label: `Вариант ${index + 1}` }))

async function mockCalculator(page, dictionary) {
  await page.route('**/api/**', (route) => {
    const address = new URL(route.request().url())
    assert.equal(route.request().method(), 'GET', 'Audit scenarios must not change records')
    if (address.pathname.startsWith('/api/v1/catalog-options/')) return dictionary(route, address)
    return route.fulfill({ json: address.pathname.endsWith('/auth/session/') ? anonymous
      : address.pathname === '/api/v1/mortgage/options/' ? options
        : { page: 1, pageSize: 20, totalCount: 0, totalPages: 1, results: [] } })
  })
}

function catalog(address) {
  const selectedIds = address.searchParams.getAll('selectedIds').map(Number)
  return { page: 1, nextPage: null, totalCount: variants.length, results: variants, selected: variants.filter((item) => selectedIds.includes(item.id)) }
}

for (const [width, height] of [[360, 640], [720, 400], [720, 320], [1280, 900]]) for (const theme of ['light', 'dark']) {
  test(`final audit keeps focus visible and lookup recovery safe in ${theme} at ${width}x${height}`, async (context) => {
    const page = await createPage(context, { width, height })
    await page.addInitScript((value) => localStorage.setItem('theme-preference', value), theme)
    let phase = 'ready'
    let release
    let retryStarted
    let requests = 0
    const gate = new Promise((resolve) => { release = resolve })
    const started = new Promise((resolve) => { retryStarted = resolve })
    context.after(() => release())
    await mockCalculator(page, async (route, address) => {
      if (address.pathname.includes('/regions/') && address.searchParams.has('q')) {
        requests++
        if (phase === 'pending') { retryStarted(); await gate }
        if (phase === 'error') return route.fulfill({ status: 503, json: { detail: 'Временный сбой.' } })
      }
      const data = catalog(address)
      if (address.searchParams.has('q')) data.results = [{ id: 3, label: 'Новый регион' }]
      return route.fulfill({ json: data })
    })
    for (const path of ['mortgage', 'mortgage/trench', 'login', 'register', 'password/reset']) {
      await page.goto(baseUrl + '/app/' + path)
      await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor()
      await assertFormTraversal(page, 40)
      await assertReactPageLayout(page)
    }
    await page.goto(baseUrl + '/app/mortgage')
    const cost = page.getByLabel('Базовая стоимость, ₽', { exact: true })
    await cost.fill('6123456')
    const region = page.getByRole('combobox', { name: 'Регион', exact: true })
    await region.click()
    await page.getByRole('option', { name: 'Вариант 2', exact: true }).click()
    phase = 'error'
    await region.fill('Новый')
    let retry = page.getByRole('button', { name: 'Повторить загрузку справочника', exact: true })
    await retry.waitFor()
    await page.getByRole('alert').filter({ hasText: 'Не удалось загрузить варианты.' }).waitFor()
    await assertReactPageLayout(page)
    await screenshot(page, `audit-error-${theme}-${width}x${height}.png`)
    await page.keyboard.press('Enter')
    await page.keyboard.press('Escape')
    assert.equal(await region.inputValue(), 'Вариант 2', 'Lookup failure must not clear the chosen value')
    await region.fill('Новый')
    await retry.waitFor()
    phase = 'pending'
    const before = requests
    await retry.focus()
    await page.keyboard.press('Enter')
    await started
    const pending = await region.evaluate((input) => {
      const button = input.closest('.searchable-select').querySelector('.searchable-select__retry')
      return { busy: input.getAttribute('aria-busy'), retryDisabled: !button || button.disabled }
    })
    assert.deepEqual(pending, { busy: 'true', retryDisabled: true })
    await page.keyboard.press('Enter')
    assert.equal(requests, before + 1, 'An active retry must not be restarted')
    assert.equal(await region.inputValue(), 'Новый')
    await assertFocusedControlVisible(page)
    await assertReactPageLayout(page)
    await screenshot(page, `audit-retry-${theme}-${width}x${height}.png`)
    phase = 'ready'
    release()
    await page.waitForFunction(() => document.querySelector('input[role=combobox][aria-busy=true]') === null)
    await page.getByRole('option', { name: 'Новый регион', exact: true }).waitFor()
    await page.keyboard.press('Enter')
    assert.equal(await region.inputValue(), 'Новый регион')
    assert.equal(await cost.inputValue(), '6123456')
    await assertReactPageLayout(page)
  })
}

for (const theme of ['light', 'dark']) {
  test(`final audit supports native touch selection and menu in ${theme}`, async (context) => {
    const page = await createPage(context, { width: 360, height: 640 }, { touch: true })
    await page.addInitScript((value) => localStorage.setItem('theme-preference', value), theme)
    await mockCalculator(page, (route, address) => route.fulfill({ json: catalog(address) }))
    await page.goto(baseUrl + '/app/mortgage')
    const region = page.getByRole('combobox', { name: 'Регион', exact: true })
    await region.tap()
    const list = page.getByRole('listbox', { name: 'Варианты: Регион' })
    await page.getByRole('option', { name: 'Вариант 12', exact: true }).waitFor()
    const bounds = await list.boundingBox()
    const motion = await list.evaluateHandle((element) => ({
      settled: new Promise((resolve) => element.addEventListener('scrollend', () => resolve(true), { once: true })),
    }))
    const session = await page.context().newCDPSession(page)
    const x = bounds.x + bounds.width / 2
    const y = bounds.y + bounds.height - 20
    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ id: 1, x, y }] })
    for (let step = 1; step <= 6; step++) await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ id: 1, x, y: y - step * 15 }] })
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await page.waitForFunction(() => document.querySelector('[role=listbox]').scrollTop > 0)
    await motion.evaluate((state) => state.settled)
    await motion.dispose()
    await session.detach()
    await page.getByRole('option', { name: 'Вариант 12', exact: true }).tap()
    assert.equal(await region.inputValue(), 'Вариант 12')
    await assertFocusedControlVisible(page)
    await page.getByRole('button', { name: 'Открыть меню разделов' }).tap()
    const dialog = page.getByRole('dialog', { name: 'Навигация по разделам' })
    await dialog.waitFor()
    await dialog.getByRole('button', { name: 'Закрыть меню', exact: true }).tap()
    await dialog.waitFor({ state: 'hidden' })
    await assertReactPageLayout(page)
    await screenshot(page, `audit-touch-${theme}.png`)
  })
}

for (const width of [360, 1280]) for (const theme of ['light', 'dark']) {
  test(`final audit distinguishes password-link outages from invalid tokens in ${theme} at ${width}px`, async (context) => {
    const page = await createPage(context, { width, height: 640 })
    await page.addInitScript((value) => localStorage.setItem('theme-preference', value), theme)
    let phase = 'error'
    let attempts = 0
    let release
    let started
    const gate = new Promise((resolve) => { release = resolve })
    const requestStarted = new Promise((resolve) => { started = resolve })
    context.after(() => release())
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      if (path === '/api/v1/auth/session/') return route.fulfill({ json: anonymous })
      assert.equal(path, '/api/v1/auth/password/reset/token/')
      assert.equal(request.method(), 'POST')
      attempts++
      if (phase === 'pending') { started(); await gate }
      return phase === 'error' ? route.fulfill({ status: 503, json: { detail: 'Временный сбой.' } })
        : phase === 'invalid' ? route.fulfill({ status: 400, json: { errors: { token: ['Ссылка для восстановления недействительна или устарела.'] } } })
          : route.fulfill({ json: { valid: true } })
    })
    await page.goto(baseUrl + '/app/password/reset/audit-user/audit-token')
    const main = page.getByRole('main')
    await main.getByRole('heading', { name: 'Не удалось проверить ссылку' }).waitFor()
    await assertReactPageLayout(page)
    phase = 'pending'
    await main.getByRole('button', { name: 'Повторить', exact: true }).focus()
    await page.keyboard.press('Enter')
    await requestStarted
    await page.keyboard.press('Enter')
    assert.equal(attempts, 2, 'The pending token check must not be duplicated')
    phase = 'ready'
    release()
    await page.waitForURL('**/app/password/reset/confirm')
    await main.getByRole('heading', { name: 'Новый пароль', exact: true }).waitFor()
    assert.doesNotMatch(await main.innerText(), /audit-token/)
    await assertReactPageLayout(page)
    phase = 'invalid'
    await page.goto(baseUrl + '/app/password/reset/audit-user/expired-audit-token')
    await main.getByRole('heading', { name: 'Ссылка не работает', exact: true }).waitFor()
    assert.equal(await main.getByRole('button', { name: 'Повторить', exact: true }).count(), 0)
    assert.equal(await main.getByRole('link', { name: 'Запросить новую ссылку' }).getAttribute('href'), '/app/password/reset')
    await assertReactPageLayout(page)
  })
}
