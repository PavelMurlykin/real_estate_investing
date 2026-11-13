import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

import { baseUrl, createPage, screenshot } from './helpers.mjs'
import { assertReactPageLayout } from './page-layout-helpers.mjs'
import { assertDetailKeyboard } from './detail-style-helpers.mjs'

// Synthetic, schema-shaped data shared with the existing component scenarios.
const fixtures = JSON.parse(await readFile(new URL('./detail-fixtures.json', import.meta.url), 'utf8'))
const records = [
  ['banks', 'bank'], ['mortgage-programs', 'program'], ['developer-programs', 'developerProgram'],
  ['properties', 'property'], ['complexes', 'complex'], ['customers', 'customer'],
  ['mortgage/calculations', 'market'], ['mortgage/trench/calculations', 'trench'],
]

async function mockDetails(page, data = fixtures) {
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname
    const payload = path === '/api/v1/auth/session/' ? data.session
      : path === `/api/v1/customers/${data.customer.id}/calculations/` ? data.customerCalculations
      : path.startsWith('/api/v1/catalog-options/') ? { results: [], selected: [], totalCount: 0, page: 1, nextPage: null }
      : records.find(([resource, key]) => path === `/api/v1/${resource === 'developer-programs' ? 'developer-mortgage-programs' : resource}/${data[key].id}/`)?.[1]
    assert.ok(payload, 'Unexpected API request: ' + path)
    assert.equal(route.request().method(), 'GET', 'Detail checks must not change data')
    return route.fulfill({ json: typeof payload === 'string' ? data[payload] : payload })
  })
  await page.route('**/*', (route) => route.request().resourceType() === 'image'
    ? route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64') })
    : route.fallback())
}

for (const width of [360, 768, 1280]) {
  for (const theme of ['light', 'dark']) {
    test(`detail pages share cards, headings, actions and keyboard behavior in ${theme} at ${width}px`, async (context) => {
      const page = await createPage(context, { width, height: 900 })
      await page.addInitScript((value) => localStorage.setItem('theme-preference', value), theme)
      await mockDetails(page)
      for (const [resource, key] of records) {
        await page.goto(baseUrl + '/app/' + resource + '/' + fixtures[key].id)
        await page.locator('.detail-page > .page-header h1').waitFor()
        await assertReactPageLayout(page)
        await screenshot(page, `detail-${key}-${theme}-${width}.png`)
        await assertDetailKeyboard(page)
        const trigger = page.locator('.detail-page > .page-header').getByRole('button', { name: 'Удалить', exact: true })
        await trigger.focus()
        await page.keyboard.press('Enter')
        const dialog = page.getByRole('alertdialog')
        await dialog.waitFor()
        const cancel = dialog.getByRole('button', { name: 'Отмена', exact: true })
        assert.equal(await cancel.evaluate((element) => element === document.activeElement), true)
        await page.keyboard.press('Shift+Tab')
        assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true)
        await page.keyboard.press('Tab')
        assert.equal(await cancel.evaluate((element) => element === document.activeElement), true)
        await assertReactPageLayout(page)
        if (key === 'bank') await screenshot(page, `detail-dialog-${theme}-${width}.png`)
        await page.keyboard.press('Escape')
        await dialog.waitFor({ state: 'hidden' })
        assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
        if (['property', 'complex'].includes(key)) {
          const image = page.getByRole('button', { name: key === 'property' ? 'Увеличить: Планировка' : 'Увеличить фото жилого комплекса', exact: true })
          await image.focus()
          await page.keyboard.press('Enter')
          const preview = page.getByRole('dialog')
          await preview.waitFor()
          const close = preview.getByRole('button', { name: 'Закрыть изображение', exact: true })
          assert.equal(await close.evaluate((element) => element === document.activeElement), true)
          await page.keyboard.press('Shift+Tab')
          assert.equal(await preview.evaluate((element) => element.contains(document.activeElement)), true)
          await page.keyboard.press('Tab')
          assert.equal(await close.evaluate((element) => element === document.activeElement), true)
          await page.keyboard.press('Escape')
          await preview.waitFor({ state: 'hidden' })
          assert.equal(await image.evaluate((element) => element === document.activeElement), true)
        }
      }
    })
  }
}

test('detail pages wrap long names and retain empty states at 320px', async (context) => {
  const page = await createPage(context, { width: 320, height: 900 })
  const data = structuredClone(fixtures)
  const long = 'ОченьДлинноеНазваниеБезПробелов'.repeat(8)
  Object.assign(data.bank, { name: long, programs: [] })
  Object.assign(data.program, { name: long, regionalCreditLimits: [] })
  Object.assign(data.property, { realEstateComplex: long, images: data.property.images.map((image) => ({ ...image, url: null })) })
  Object.assign(data.complex, { name: long, photoUrl: null, photos: [], buildings: [], metroAvailability: [] })
  Object.assign(data.customer, { fullName: long, email: long + '@example.com', comment: long })
  Object.assign(data.developerProgram, { companyGroupName: long, bankName: long })
  await mockDetails(page, data)
  for (const [resource, key] of records) {
    await page.goto(baseUrl + '/app/' + resource + '/' + data[key].id)
    await page.locator('.detail-page > .page-header h1').waitFor()
    await assertReactPageLayout(page)
  }
})

test('detail deletion keeps focus during a pending request and recovers after conflict', async (context) => {
  const page = await createPage(context, { width: 360, height: 900 })
  await mockDetails(page)
  let release
  const pending = new Promise((resolve) => { release = resolve })
  // This response is intercepted locally; no deletion reaches the application.
  await page.route(`**/api/v1/banks/${fixtures.bank.id}/`, async (route) => {
    if (route.request().method() !== 'DELETE') return route.fallback()
    await pending
    return route.fulfill({ status: 409, json: { detail: 'Есть связанные программы.' } })
  })
  await page.goto(baseUrl + '/app/banks/' + fixtures.bank.id)
  const trigger = page.locator('.page-header').getByRole('button', { name: 'Удалить', exact: true })
  await trigger.click()
  const dialog = page.getByRole('alertdialog')
  await dialog.getByRole('button', { name: 'Удалить', exact: true }).click()
  await dialog.and(page.locator('[aria-busy=true]')).waitFor()
  await page.keyboard.press('Tab')
  await page.keyboard.press('Escape')
  assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true)
  assert.equal(await dialog.getByRole('button', { name: 'Отмена', exact: true }).isDisabled(), true)
  release()
  await dialog.getByRole('alert').waitFor()
  await page.keyboard.press('Tab')
  const cancel = dialog.getByRole('button', { name: 'Отмена', exact: true })
  assert.equal(await cancel.evaluate((element) => element === document.activeElement), true)
  await page.keyboard.press('Enter')
  await dialog.waitFor({ state: 'hidden' })
  assert.equal(await trigger.evaluate((element) => element === document.activeElement), true)
})
