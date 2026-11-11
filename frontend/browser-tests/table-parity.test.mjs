import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, createPage, openPage, screenshot } from './helpers.mjs'

test('catalog searches while typing and sorts the full server selection by header', async (context) => {
  const page = await openPage(context, { width: 1440, height: 1000 }, '/app/properties')
  const table = page.getByRole('table', { name: 'Список объектов недвижимости' })
  const apartment = (await table.locator('tbody tr').first().locator('td').nth(4).textContent()).trim()
  const loaded = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/api/v1/properties/' && url.searchParams.get('apartmentNumber') === apartment
  })
  await page.getByLabel('Номер квартиры').fill(apartment)
  assert.equal((await loaded).status(), 200)
  const sorted = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/api/v1/properties/' && url.searchParams.get('ordering') === 'propertyCost'
  })
  await table.getByRole('button', { name: 'Стоимость', exact: true }).click()
  assert.equal((await sorted).status(), 200)
  assert.equal(await table.getByRole('columnheader', { name: 'Стоимость' }).getAttribute('aria-sort'), 'ascending')
  assert.equal(new URL(page.url()).searchParams.get('apartmentNumber'), apartment)
  assert.equal(await table.getByRole('columnheader', { name: /Статус|Обновл|^ID$/ }).count(), 0)
  await table.scrollIntoViewIfNeeded()
  await screenshot(page, 'tables-catalog-desktop.png')
})

test('nested bank table remains searchable and sortable at 360px', async (context) => {
  const page = await createPage(context, { width: 360, height: 900 })
  const response = await page.request.get(new URL('/api/v1/banks/', baseUrl).href)
  const banks = await response.json()
  const bank = banks.results.find((candidate) => candidate.programCount > 0)
  assert.ok(bank, 'Acceptance fixture must contain a bank with programs')
  await page.goto(new URL(`/app/banks/${bank.id}`, baseUrl).href)
  const table = page.getByRole('table', { name: `Ипотечные программы банка ${bank.name}` })
  await table.waitFor({ state: 'visible' })
  const name = (await table.locator('tbody tr td').first().textContent()).trim()
  await page.getByLabel(`Поиск в таблице: Ипотечные программы банка ${bank.name}`).fill(name)
  await table.getByRole('button', { name: 'Ставка', exact: true }).click()
  assert.equal(await table.getByRole('columnheader', { name: 'Ставка' }).getAttribute('aria-sort'), 'ascending')
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await screenshot(page, 'tables-bank-mobile.png')
})

for (const type of ['market', 'trench']) {
  test(`${type} schedule searches beyond its twelve-row preview and sorts all payments`, async (context) => {
    const page = await openPage(context, { width: 1280, height: 1000 }, type === 'market' ? '/app/mortgage' : '/app/mortgage/trench')
    const path = type === 'market' ? '/api/v1/mortgage/calculate/' : '/api/v1/mortgage/trench/calculate/'
    // Calculation is a side-effect-free POST; all other API writes remain blocked.
    await page.route(`**${path}`, (route) => route.continue())
    if (type === 'trench') {
      await page.getByRole('combobox', { name: /^Количество траншей/ }).selectOption('2')
      const start = await page.getByLabel('Дата первоначального взноса', { exact: true }).inputValue()
      const next = new Date(`${start}T12:00:00Z`)
      next.setUTCMonth(next.getUTCMonth() + 6)
      await page.getByLabel('Дата транша', { exact: true }).nth(1).fill(next.toISOString().slice(0, 10))
    }
    const response = page.waitForResponse((result) => new URL(result.url()).pathname === path)
    await page.getByRole('button', { name: type === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку', exact: true }).click()
    const calculated = await response
    assert.equal(calculated.status(), 200, JSON.stringify(await calculated.json()))
    const result = await calculated.json()
    const last = result.schedule.at(-1)
    assert.ok(last.paymentNumber > 12)
    const caption = type === 'market' ? 'График ежемесячных платежей' : 'Общий график ежемесячных платежей'
    const table = page.getByRole('table', { name: caption, exact: true })
    const date = last.paymentDate.split('-').reverse().join('.')
    const search = page.getByLabel(`Поиск в таблице: ${caption}`)
    await search.fill(date)
    assert.equal(await table.locator('tbody tr').count(), 1)
    assert.equal((await table.locator('tbody tr td').first().textContent()).trim(), String(last.paymentNumber))
    await search.clear()
    await table.getByRole('button', { name: '№', exact: true }).click()
    await page.keyboard.press('Enter')
    assert.equal(await table.locator('tbody tr').count(), 12)
    assert.equal((await table.locator('tbody tr td').first().textContent()).trim(), String(last.paymentNumber))
  })
}
