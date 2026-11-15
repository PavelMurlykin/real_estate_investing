import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, createPage, screenshot } from './helpers.mjs'

async function mockCatalogs(page) {
  await page.route('**/api/v1/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    const body = pathname.includes('/auth/session/') ? {
      isAuthenticated: false, user: null,
      capabilities: { manageCatalogs: false, syncExternalData: false, viewPrivateRecords: false, viewAllPrivateRecords: false },
    } : pathname.includes('/mortgage/options/') ? {
      defaultInitialPaymentDate: '2026-11-15', keyRate: '16.00', banks: [], programs: [],
    } : { page: 1, pageSize: 100, totalCount: 0, totalPages: 0, results: [], selected: [], nextPage: null }
    assert.equal(route.request().method(), 'GET', 'Settings must not send writes to the API')
    await route.fulfill({ json: body })
  })
}

for (const width of [360, 768, 1280]) {
  for (const mode of ['market', 'trench']) {
    test(`${mode} modifiers, keyboard and always-visible steppers at ${width}px`, async (context) => {
      const page = await createPage(context, { width, height: 1000 })
      await mockCatalogs(page)
      await page.goto(new URL(`/app/mortgage${mode === 'trench' ? '/trench' : ''}`, baseUrl).href)
      const settings = page.getByRole('button', { name: 'Настройки', exact: true })
      await settings.waitFor()
      await page.waitForLoadState('networkidle')
      if (width >= 768) {
        const settingsBounds = await settings.boundingBox()
        const historyBounds = await page.getByRole('link', { name: 'История расчётов', exact: true }).boundingBox()
        assert.equal(settingsBounds.y, historyBounds.y, 'Header buttons should be on one row')
      }
      const originalCost = Number(await page.getByLabel('Базовая стоимость, ₽', { exact: true }).inputValue())
      await settings.click()
      const dialog = page.getByRole('dialog', { name: 'Настройки калькулятора' })
      assert.equal(await dialog.evaluate((element) => element.matches(':modal')), true)
      const radioPositions = await dialog.getByRole('radio').evaluateAll((radios) => radios.map((radio) => radio.getBoundingClientRect().y))
      assert.equal(new Set(radioPositions).size, 1, 'Increment options should stay on one row')
      await dialog.getByLabel('Шаг изменения суммы, ₽', { exact: true }).fill('25000')
      await dialog.getByRole('radio', { name: '0,01 п.п.' }).check()
      const save = dialog.getByRole('button', { name: 'Сохранить', exact: true })
      await save.focus()
      await page.keyboard.press('Tab')
      assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true)
      await screenshot(page, `mortgage-settings-${mode}-${width}.png`)
      await save.click()
      assert.equal(await settings.evaluate((element) => element === document.activeElement), true)
      assert.equal(await page.getByLabel('Базовая стоимость, ₽', { exact: true }).inputValue(), String(originalCost))
      await page.getByRole('button', { name: 'Увеличить: Базовая стоимость, ₽', exact: true }).click()
      assert.equal(Number(await page.getByLabel('Базовая стоимость, ₽', { exact: true }).inputValue()), originalCost + 25000)
      const downPayment = page.getByLabel('Первоначальный взнос, %', { exact: true })
      await downPayment.focus()
      await page.keyboard.press('ArrowUp')
      assert.equal(await downPayment.inputValue(), '20.01')
      await page.reload()
      await settings.click()
      assert.equal(await dialog.getByLabel('Шаг изменения суммы, ₽', { exact: true }).inputValue(), '25000')
      assert.equal(await dialog.getByRole('radio', { name: '0,01 п.п.' }).isChecked(), true)
      await page.keyboard.press('Escape')
      assert.equal(await settings.evaluate((element) => element === document.activeElement), true)
      const otherMode = mode === 'market' ? '/app/mortgage/trench' : '/app/mortgage'
      await page.goto(new URL(otherMode, baseUrl).href)
      await settings.click()
      assert.equal(await dialog.getByLabel('Шаг изменения суммы, ₽', { exact: true }).inputValue(), '25000')
      await page.keyboard.press('Escape')
      if (mode === 'trench') await page.getByLabel('Использовать льготный период').check()
      else await page.getByLabel('Количество траншей').selectOption('3')
      await page.mouse.move(0, 0)
      const issues = await page.locator('.calculator-card').evaluate((form) => {
        const failures = []
        for (const field of form.querySelectorAll('.number-field')) {
          const input = field.querySelector('input')
          const buttons = [...field.querySelectorAll('button')]
          const bounds = field.getBoundingClientRect()
          if (getComputedStyle(input).appearance !== 'textfield') failures.push('Native spinner remains')
          for (const button of buttons) {
            const box = button.getBoundingClientRect()
            if (box.width < 44 || box.height < 44 || box.right > bounds.right + 1
              || getComputedStyle(button).visibility !== 'visible' || getComputedStyle(button).opacity === '0') {
              failures.push(button.getAttribute('aria-label'))
            }
          }
        }
        if (document.documentElement.scrollWidth > innerWidth) failures.push('Horizontal overflow')
        return failures
      })
      assert.deepEqual(issues, [])
      await page.getByLabel('Базовая стоимость, ₽', { exact: true }).scrollIntoViewIfNeeded()
      await screenshot(page, `mortgage-steppers-${mode}-${width}.png`)
      if (mode === 'market') {
        const theme = page.getByRole('button', { name: /^Тема:/ })
        for (let attempt = 0; attempt < 3; attempt += 1) {
          if ((await theme.getAttribute('aria-label')).startsWith('Тема: тёмная.')) break
          await theme.click()
        }
        await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
        await settings.click()
        await screenshot(page, `mortgage-settings-dark-${width}.png`)
        assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark')
        await page.keyboard.press('Escape')
      }
    })
  }
}
