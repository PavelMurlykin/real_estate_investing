import assert from 'node:assert/strict'
import { test } from 'node:test'

import { createAuthenticatedPage, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'
import { screenshot } from './helpers.mjs'

async function keyboardChoice(page, name, query, optionName = query, multiple = false) {
  const input = page.getByRole('combobox', { name, exact: true }).first()
  await input.fill(query.toLocaleLowerCase('ru-RU'))
  const option = page.getByRole('listbox').getByRole('option', { name: optionName, exact: true })
  await option.waitFor()
  await input.and(page.locator('[aria-busy="true"]')).waitFor({ state: 'hidden' })
  const label = await option.textContent()
  await page.waitForFunction(() => {
    const list = document.querySelector('[role=listbox]')
    const bounds = list?.getBoundingClientRect()
    return bounds && bounds.top >= 0 && bounds.bottom <= innerHeight
  })
  await screenshot(page, 'dictionary-menu-' + String(name).replace(/[^\p{L}\p{N}]+/gu, '-') + '-' + page.viewportSize().width + '.png')
  await input.press('Enter')
  if (multiple) await page.getByRole('button', { name: `Убрать: ${label}`, exact: true }).waitFor()
  else {
    await page.getByRole('listbox').waitFor({ state: 'hidden' })
    assert.equal(await input.inputValue(), label)
  }
  await input.press('Escape')
  assert.equal(await input.evaluate((element) => element === document.activeElement), true)
  return input
}

async function clearChoice(page, name) {
  const input = page.getByRole('combobox', { name, exact: true })
  await input.click()
  const count = await page.getByRole('listbox').getByRole('option').count()
  for (let index = 0; index < count; index += 1) await input.press('ArrowUp')
  await input.press('Enter')
  assert.equal(await input.inputValue(), '')
}

const forms = [
  ['properties/new', async (page) => {
    assert.equal(await page.getByRole('combobox', { name: 'Город *', exact: true }).isDisabled(), true)
    await keyboardChoice(page, 'Регион *', 'E2E регион')
    await keyboardChoice(page, 'Город *', 'E2E город')
    await keyboardChoice(page, 'Район *', 'E2E район')
    await keyboardChoice(page, 'Застройщик *', 'E2E застройщик', /^E2E застройщик(?: \(.*\))?$/)
    await keyboardChoice(page, 'Жилой комплекс *', 'E2E квартал')
    const building = page.getByRole('combobox', { name: 'Корпус *', exact: true })
    await building.click()
    const number = await page.getByRole('listbox').getByRole('option').nth(1).textContent()
    await building.press('Escape')
    await keyboardChoice(page, 'Корпус *', number)
    await keyboardChoice(page, 'Планировка *', 'E2E планировка')
    await keyboardChoice(page, 'Отделка *', 'E2E отделка')
    await clearChoice(page, 'Застройщик *')
    for (const name of ['Жилой комплекс *', 'Корпус *']) {
      const input = page.getByRole('combobox', { name, exact: true })
      assert.equal(await input.inputValue(), '')
      assert.equal(await input.isDisabled(), true)
    }
    assert.equal(await page.getByRole('combobox', { name: 'Город *', exact: true }).inputValue(), 'E2E город')
    await clearChoice(page, 'Регион *')
    assert.equal(await page.getByRole('combobox', { name: 'Город *', exact: true }).isDisabled(), true)
  }],
  ['customers/new', async (page) => {
    assert.equal(await page.getByRole('combobox', { name: 'Желаемый район', exact: true }).isDisabled(), true)
    await keyboardChoice(page, 'Желаемый город покупки', 'E2E город')
    await keyboardChoice(page, 'Желаемый район', 'E2E район')
    const layout = await keyboardChoice(page, 'Планировки', 'E2E планировка', 'E2E планировка', true)
    await layout.click()
    await layout.fill('нет такого варианта')
    await layout.press('Enter')
    await layout.press('Escape')
    await page.getByRole('button', { name: 'Убрать: E2E планировка' }).waitFor()
    await layout.press('Shift+Tab')
    assert.equal(await page.getByRole('button', { name: 'Убрать: E2E планировка' }).evaluate((element) => element === document.activeElement), true)
    await page.keyboard.press('Enter')
    assert.equal(await page.getByRole('button', { name: 'Убрать: E2E планировка' }).count(), 0)
    await clearChoice(page, 'Желаемый город покупки')
    assert.equal(await page.getByRole('combobox', { name: 'Желаемый район', exact: true }).inputValue(), '')
    assert.equal(await page.getByRole('combobox', { name: 'Желаемый район', exact: true }).isDisabled(), true)
  }],
  ['developers/new', async (page) => {
    await keyboardChoice(page, 'Группа компаний', 'E2E группа')
    await keyboardChoice(page, 'Регионы', 'E2E регион', 'E2E регион', true)
  }],
  ['banks/new', async (page) => {
    await page.getByRole('button', { name: 'Добавить программу', exact: true }).click()
    await keyboardChoice(page, 'Ипотечная программа *', 'E2E ипотечная программа')
  }],
  ['mortgage-programs/new', async (page) => {
    await page.getByRole('button', { name: 'Добавить регион', exact: true }).click()
    await keyboardChoice(page, 'Регион *', 'E2E регион')
  }],
  ['developer-programs/new', async (page) => {
    const complex = page.getByRole('combobox', { name: 'Жилой комплекс', exact: true })
    assert.equal(await complex.isDisabled(), true)
    await keyboardChoice(page, 'Группа компаний *', 'E2E группа')
    await keyboardChoice(page, 'Жилой комплекс', 'E2E квартал', /^E2E квартал \(/)
    await keyboardChoice(page, 'Банк *', 'E2E банк')
    await keyboardChoice(page, 'Ипотечная программа *', 'E2E ипотечная программа')
    await clearChoice(page, 'Группа компаний *')
    assert.equal(await complex.inputValue(), '')
    assert.equal(await complex.isDisabled(), true)
  }],
]

for (const width of [360, 768, 1280]) {
  for (const [route, check] of forms) {
    test(`dictionary keyboard search on ${route} at ${width}px`, {
      skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack',
    }, async (context) => {
      const { page } = await createAuthenticatedPage(context, 'moderator', { width, height: 900 })
      const errors = []
      const writes = []
      page.on('pageerror', (error) => errors.push(error.message))
      page.on('request', (request) => {
        if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) writes.push(request.method() + ' ' + new URL(request.url()).pathname)
      })
      await page.goto(isolatedBaseUrl + '/app/' + route)
      await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor()
      await check(page)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      assert.deepEqual(errors, [])
      assert.deepEqual(writes, [], 'Selecting a dictionary must never submit a form')
      await screenshot(page, route.replace('/', '-') + '-' + width + '.png')
    })
  }
}
