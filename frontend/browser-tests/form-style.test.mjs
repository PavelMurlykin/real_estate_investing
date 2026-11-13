import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, createPage, screenshot } from './helpers.mjs'
import { assertReactPageLayout } from './page-layout-helpers.mjs'
import { assertFormKeyboard } from './form-style-helpers.mjs'

for (const width of [360, 1280]) {
  for (const theme of ['light', 'dark']) {
    test(`form controls, keyboard focus and validation remain consistent in ${theme} at ${width}px`, async (context) => {
      const page = await createPage(context, { width, height: 900 })
      await page.addInitScript((theme) => localStorage.setItem('theme-preference', theme), theme)
      await page.goto(baseUrl + '/app/login')
      const identifier = page.getByRole('textbox', { name: 'Email или телефон', exact: true })
      await identifier.waitFor()
      await assertReactPageLayout(page)
      await assertFormKeyboard(page)
      const colors = await identifier.evaluate((element) => {
        const style = getComputedStyle(element)
        return { text: style.color, background: style.backgroundColor, outline: style.outlineColor, border: style.borderTopColor }
      })
      const luminance = (color) => color.match(/[\d.]+/g).slice(0, 3).map(Number).map((value) => {
        const channel = value / 255
        return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
      }).reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index], 0)
      const contrast = (first, second) => (Math.max(luminance(first), luminance(second)) + 0.05)
        / (Math.min(luminance(first), luminance(second)) + 0.05)
      assert.ok(contrast(colors.text, colors.background) >= 4.5)
      assert.ok(contrast(colors.outline, colors.background) >= 3)
      await identifier.press('Tab')
      assert.equal(await page.getByLabel('Пароль', { exact: true }).evaluate((element) => element === document.activeElement), true)
      await page.keyboard.press('Tab')
      assert.equal(await page.getByRole('button', { name: 'Войти', exact: true }).evaluate((element) => element === document.activeElement), true)
      await page.keyboard.press('Enter')
      await page.getByRole('alert').filter({ hasText: 'Введите email или телефон и пароль.' }).waitFor()
      assert.equal(await identifier.getAttribute('aria-invalid'), 'true')
      assert.equal(await identifier.getAttribute('aria-describedby'), 'login-form-error')
      const invalidBorder = await identifier.evaluate((element) => getComputedStyle(element).borderTopColor)
      assert.notEqual(invalidBorder, colors.border)
      await assertReactPageLayout(page)
      await screenshot(page, `form-validation-${theme}-${width}.png`)
      for (const route of ['register', 'password/reset', 'password/reset/confirm', 'mortgage', 'mortgage/trench']) {
        await page.goto(baseUrl + '/app/' + route)
        await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor()
        await assertReactPageLayout(page)
        await assertFormKeyboard(page)
      }
    })
  }
}
