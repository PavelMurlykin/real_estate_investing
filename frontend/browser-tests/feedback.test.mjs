import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { baseUrl, createPage, screenshot } from './helpers.mjs'
import { assertFeedbackStyles } from './feedback-style-helpers.mjs'

const fixtures = JSON.parse(await readFile(new URL('./feedback-fixtures.json', import.meta.url), 'utf8'))
const detail = JSON.parse(await readFile(new URL('./detail-fixtures.json', import.meta.url), 'utf8'))
const cases = [
  ['banks', 'banks'], ['company-groups', 'groups'], ['developers', 'developers'],
  ['mortgage-programs', 'programs'], ['developer-programs', 'developerPrograms'], ['complexes', 'complexes'],
  ...['regions', 'cities', 'districts', 'metro'].map((key) => ['locations/' + key, key]),
  ...['real-estate-types', 'real-estate-classes', 'apartment-layouts', 'apartment-decorations', 'window-views', 'transport-accessibility-types'].map((key) => ['dictionaries/' + key, 'dictionary']),
]
const locations = { regions: 'region', cities: 'city', districts: 'district', metro: 'metro' }
const directory = (row) => ({ page: 1, pageSize: 20, totalCount: 1, totalPages: 1, results: [row] })

async function mockCatalogs(page) {
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname
    // Destructive requests are fulfilled here and never reach the application.
    if (route.request().method() === 'DELETE') return route.fulfill({ status: 409, json: { detail: 'Запись используется в связанных данных.' } })
    let payload = path === '/api/v1/auth/session/' ? detail.session
      : path.startsWith('/api/v1/catalog-options/') ? { results: [], selected: [], totalCount: 0, page: 1, nextPage: null }
      : path.includes('/developers/options/') ? fixtures.developerOptions
      : path.includes('/developer-mortgage-programs/options/') ? fixtures.developerProgramOptions
      : path.includes('/complexes/options/') ? fixtures.complexOptions
      : path.includes('/location-dictionaries/options/') ? fixtures.locationOptions
      : path.startsWith('/api/v1/property-dictionaries/') ? fixtures.dictionary
      : path.startsWith('/api/v1/location-dictionaries/') ? directory(fixtures[locations[path.split('/')[4]]])
      : path === `/api/v1/customers/${detail.customer.id}/` ? detail.customer
      : path.includes('/customers/') && path.includes('/calculations/') ? detail.customerCalculations
      : fixtures[({ banks: 'banks', 'company-groups': 'groups', developers: 'developers', 'mortgage-programs': 'programs', 'developer-mortgage-programs': 'developerPrograms', complexes: 'complexes' })[path.split('/')[3]]]
    assert.ok(payload, 'Unexpected request: ' + path)
    return route.fulfill({ json: payload })
  })
}

for (const width of [360, 768, 1280]) for (const theme of ['light', 'dark']) {
  test(`feedback dialogs close, restore focus and stay usable in ${theme} at ${width}px`, async (context) => {
    const page = await createPage(context, { width, height: 900 })
    await page.addInitScript((value) => localStorage.setItem('theme-preference', value), theme)
    await mockCatalogs(page)
    for (const [resource] of cases) {
      await page.goto(baseUrl + '/app/' + resource)
      const trigger = page.getByRole('button', { name: /^Удалить/ }).first()
      await trigger.waitFor()
      const open = async () => { await trigger.focus(); await page.keyboard.press('Enter'); await page.getByRole('alertdialog').waitFor() }
      await open()
      const dialog = page.getByRole('alertdialog')
      const cancel = dialog.getByRole('button', { name: 'Отмена', exact: true })
      assert.equal(await cancel.evaluate((element) => element === document.activeElement), true)
      await page.keyboard.press('Shift+Tab')
      assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true)
      await page.keyboard.press('Tab')
      assert.equal(await cancel.evaluate((element) => element === document.activeElement), true)
      await page.keyboard.press('Escape')
      await dialog.waitFor({ state: 'hidden' })
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
      await open()
      await cancel.click()
      await dialog.waitFor({ state: 'hidden' })
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
      await open()
      const heading = await dialog.getByRole('heading').boundingBox()
      await page.mouse.move(heading.x + 5, heading.y + 5)
      await page.mouse.down()
      await page.mouse.move(2, 2)
      await page.mouse.up()
      assert.equal(await dialog.isVisible(), true)
      await page.mouse.click(2, 2)
      await dialog.waitFor({ state: 'hidden' })
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
      await open()
      await dialog.getByRole('button', { name: 'Удалить', exact: true }).click()
      await dialog.getByRole('alert').waitFor()
      await assertFeedbackStyles(page)
      if (resource === 'banks') await screenshot(page, `feedback-error-${theme}-${width}.png`)
      await page.keyboard.press('Escape')
      await dialog.waitFor({ state: 'hidden' })
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
    }
    await page.goto(baseUrl + '/app/customers/' + detail.customer.id)
    const unlink = page.getByRole('button', { name: /^Отвязать расчёт от/ }).first()
    await unlink.click()
    const dialog = page.getByRole('alertdialog')
    assert.equal(await dialog.getByRole('button', { name: 'Отмена' }).evaluate((element) => element === document.activeElement), true)
    await page.keyboard.press('Escape')
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(await unlink.evaluate((element) => element === document.activeElement), true)
  })
}

test('feedback returns to the list heading after a record is removed', async (context) => {
  const page = await createPage(context, { width: 360, height: 900 })
  await mockCatalogs(page)
  let removed = false
  await page.route('**/api/v1/banks/**', (route) => {
    if (route.request().method() === 'DELETE') { removed = true; return route.fulfill({ status: 204 }) }
    return route.fulfill({ json: removed ? { ...fixtures.banks, results: [], totalCount: 0 } : fixtures.banks })
  })
  await page.goto(baseUrl + '/app/banks')
  await page.getByRole('button', { name: /^Удалить/ }).first().click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Удалить', exact: true }).click()
  await page.getByRole('alertdialog').waitFor({ state: 'hidden' })
  await page.waitForFunction(() => document.activeElement === document.querySelector('main h1'))
  assert.equal(removed, true)
})

test('feedback preserves focus in a field while an operation completes', async (context) => {
  const page = await createPage(context, { width: 360, height: 900 })
  let release
  const pending = new Promise((resolve) => { release = resolve })
  context.after(() => release())
  await page.route('**/api/**', async (route) => {
    if (route.request().method() === 'PATCH') await pending
    const path = new URL(route.request().url()).pathname
    return route.fulfill({ json: path.endsWith('/session/') ? detail.session : fixtures.profile })
  })
  await page.goto(baseUrl + '/app/profile')
  const save = page.getByRole('button', { name: 'Сохранить профиль', exact: true })
  await save.click()
  const input = page.getByRole('textbox', { name: 'Имя', exact: true })
  await input.focus()
  release()
  await page.locator('.notice--success').waitFor()
  assert.equal(await input.evaluate((element) => element === document.activeElement), true)
})

for (const width of [360, 1280]) for (const theme of ['light', 'dark']) {
  test(`feedback notices announce results without stealing focus in ${theme} at ${width}px`, async (context) => {
    const page = await createPage(context, { width, height: 900 })
    await page.addInitScript((value) => localStorage.setItem('theme-preference', value), theme)
    // All responses, including saves and synchronization, stay inside this test.
    await page.route('**/api/**', (route) => {
      const path = new URL(route.request().url()).pathname
      const payload = path === '/api/v1/auth/session/' ? fixtures.administrator
        : path === '/api/v1/auth/profile/' ? fixtures.profile
        : path === '/api/v1/key-rates/chart/' ? fixtures.keyRates.results.map(({ meetingDate, keyRate }) => ({ meetingDate, keyRate }))
        : path === '/api/v1/key-rates/sync/' ? { processed: 3, created: 1, updated: 0, currentRate: fixtures.keyRates.currentRate, synchronizedAt: '2026-11-13T10:00:00Z' }
        : path === '/api/v1/key-rates/' ? fixtures.keyRates : null
      assert.ok(payload, path)
      return route.fulfill({ json: payload })
    })
    for (const [resource, name] of [['profile', 'Сохранить профиль'], ['key-rate', 'Обновить из ЦБ РФ']]) {
      await page.goto(baseUrl + '/app/' + resource)
      const trigger = page.getByRole('button', { name, exact: true })
      await trigger.waitFor()
      await trigger.focus()
      await page.keyboard.press('Enter')
      const notice = page.locator('.notice--success')
      await notice.waitFor()
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
      await assertFeedbackStyles(page)
      await screenshot(page, `feedback-${resource}-${theme}-${width}.png`)
      const close = notice.getByRole('button', { name: 'Закрыть уведомление' })
      await close.focus()
      await page.keyboard.press('Enter')
      await notice.waitFor({ state: 'hidden' })
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
      await page.keyboard.press('Enter')
      await notice.waitFor()
    }
  })
}
