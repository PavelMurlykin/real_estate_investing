import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, openPage, screenshot } from './helpers.mjs'

async function assertFormSpacing(page) {
  const issues = await page.locator('.calculator-card').evaluate((form) => {
    const failures = []
    for (const section of form.querySelectorAll('.calculator-section')) {
      const children = [...section.children].filter((child) => child.getBoundingClientRect().height > 0)
      for (let index = 1; index < children.length; index += 1) {
        const gap = children[index].getBoundingClientRect().top - children[index - 1].getBoundingClientRect().bottom
        if (gap < 20) failures.push(section.getAttribute('aria-labelledby') + ': gap ' + gap)
      }
    }
    for (const field of form.querySelectorAll('.form-field')) {
      const label = [...field.children].find((child) => ['LABEL', 'SPAN'].includes(child.tagName))
      const input = field.querySelector('input:not([type=radio]):not([type=checkbox]), select, textarea')
      if (label && input && label.getBoundingClientRect().height > 0) {
        const gap = input.getBoundingClientRect().top - label.getBoundingClientRect().bottom
        if (gap < 7) failures.push(label.textContent + ': label gap ' + gap)
      }
    }
    return failures
  })
  assert.deepEqual(issues, [])
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
}

for (const width of [360, 768, 1280]) {
  for (const mode of ['market', 'trench']) {
    test(mode + ' calculator has one property control and clear spacing at ' + width + 'px', async (context) => {
      const route = '/app/mortgage' + (mode === 'trench' ? '/trench' : '')
      const page = await openPage(context, { width, height: 1000 }, route, 'Ипотечный калькулятор')
      await page.waitForLoadState('networkidle')
      assert.equal(await page.getByRole('link', { name: 'Django-версия' }).count(), 0)
      assert.equal(await page.getByRole('complementary', { name: 'Справочная информация' }).count(), 0)
      assert.equal(await page.getByLabel('Поиск объекта', { exact: true }).count(), 0)
      assert.equal(await page.getByRole('link', { name: 'История расчётов', exact: true }).getAttribute('href'),
        '/app/mortgage/' + (mode === 'trench' ? 'trench/' : '') + 'calculations')
      const control = page.getByRole('combobox', { name: 'Объект недвижимости', exact: true })
      assert.equal(await control.count(), 1)
      const response = await page.request.get(new URL('/api/v1/properties/?pageSize=100&ordering=realEstateComplex', baseUrl).href)
      const property = (await response.json()).results[0]
      assert.ok(property, 'A property is required for selection verification')
      await control.fill(property.realEstateComplex)
      const label = `${property.city}, ${property.realEstateComplex}, корпус ${property.building}, кв. ${property.apartmentNumber}`
      await page.getByRole('option', { name: label, exact: true }).waitFor()
      await page.waitForFunction(() => document.querySelector('.calculator-card [role=combobox]')?.getAttribute('aria-busy') !== 'true')
      const optionNames = await page.getByRole('option').allTextContents()
      for (let index = 1; index < optionNames.indexOf(label); index += 1) await control.press('ArrowDown')
      await control.press('Enter')
      assert.equal(await page.getByLabel('Базовая стоимость, ₽', { exact: true }).inputValue(), property.propertyCost)
      if (mode === 'market') await page.getByLabel('Использовать льготный период').check()
      else await page.getByRole('combobox', { name: /^Количество траншей/ }).selectOption('3')
      await assertFormSpacing(page)
      await screenshot(page, `mortgage-${mode}-${width}.png`)
      assert.equal(await page.getByRole('button', { name: 'Заполнить объект вручную' }).count(), 0)
      assert.equal(await page.locator('form').count(), 1)
      assert.equal(await page.locator('[aria-label="Данные объекта недвижимости"] [role=combobox]').count(), 8)
      assert.equal(await page.locator('[aria-label="Данные объекта недвижимости"] [type=search]').count(), 0)
      await page.getByRole('button', { name: 'Очистить поля', exact: true }).click()
      assert.equal(await page.getByLabel('Номер квартиры', { exact: true }).inputValue(), '')
      await assertFormSpacing(page)
    })
  }
}
