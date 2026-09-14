import assert from 'node:assert/strict'
import { test } from 'node:test'

import { openPage, screenshot } from './helpers.mjs'

test('desktop navigation highlights the section across dictionary tabs', async (context) => {
  const page = await openPage(context, { width: 1440, height: 1000 }, '/app/locations/regions/')
  const primary = page.getByRole('navigation', { name: 'Основная навигация' })
  assert.equal(await primary.getByRole('link').count(), 3)
  const sections = page.getByRole('navigation', { name: 'Разделы приложения' })
  assert.equal(await sections.getByRole('link', { name: 'Локации' }).getAttribute('aria-current'), 'page')
  await page.getByRole('navigation', { name: 'Справочники локаций' })
    .getByRole('link', { name: 'Города', exact: true }).click()
  await page.waitForURL('**/app/locations/cities')
  assert.equal(await sections.locator('[aria-current="page"]').count(), 1)
  assert.equal(await sections.getByRole('link', { name: 'Локации' }).getAttribute('aria-current'), 'page')
  await screenshot(page, 'navigation-desktop.png')
})

for (const width of [360, 780]) {
  test(`mobile dialog at ${width}px keeps focus, closes and follows browser history`, async (context) => {
    const page = await openPage(context, { width, height: 900 })
    const opener = page.getByRole('button', { name: 'Открыть меню разделов' })
    const dialog = page.getByRole('dialog', { name: 'Навигация по разделам' })
    const closeButton = dialog.getByRole('button', { name: 'Закрыть меню', exact: true })
    assert.equal(await dialog.count(), 0)
    await opener.click()
    await dialog.waitFor({ state: 'visible' })
    assert.equal(await opener.getAttribute('aria-expanded'), 'true')
    assert.equal(await closeButton.evaluate((element) => element === document.activeElement), true)
    assert.equal(await dialog.evaluate((element) => element.matches(':modal')), true)
    assert.equal(await page.evaluate(() => document.body.style.overflow), 'hidden')
    // The browser, not a jsdom shim, must keep both Tab directions inside the dialog.
    await page.keyboard.press('Shift+Tab')
    assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true)
    await page.keyboard.press('Tab')
    assert.equal(await closeButton.evaluate((element) => element === document.activeElement), true)
    await screenshot(page, `navigation-mobile-${width}.png`)
    assert.equal(await page.evaluate(() =>
      document.documentElement.scrollWidth <= window.innerWidth), true)

    await page.keyboard.press('Escape')
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(await opener.evaluate((element) => element === document.activeElement), true)
    assert.equal(await page.evaluate(() => document.body.style.overflow), '')

    await opener.click()
    await closeButton.click()
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(await opener.evaluate((element) => element === document.activeElement), true)
    await opener.click()
    await page.mouse.click(width - 5, 450)
    await dialog.waitFor({ state: 'hidden' })

    await opener.click()
    await dialog.getByRole('link', { name: 'Банки', exact: true }).click()
    await page.waitForURL('**/app/banks')
    await dialog.waitFor({ state: 'hidden' })
    await page.waitForFunction(() => document.activeElement?.id === 'main-content')
    assert.equal(await page.getByRole('main').evaluate((element) => element === document.activeElement), true)

    await opener.click()
    await page.goBack()
    await dialog.waitFor({ state: 'hidden' })
    await page.goForward()
    assert.equal(await opener.getAttribute('aria-expanded'), 'false')
    assert.equal(await dialog.count(), 0)

    await opener.click()
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.getByRole('complementary').waitFor({ state: 'visible' })
    assert.equal(await page.evaluate(() => document.body.style.overflow), '')
    await page.setViewportSize({ width, height: 900 })
    await opener.waitFor({ state: 'visible' })
    assert.equal(await opener.getAttribute('aria-expanded'), 'false')
    assert.equal(await dialog.count(), 0)
  })
}

test('navigation remains usable while a page module is loading', async (context) => {
  const page = await openPage(context, { width: 1280, height: 900 })
  let release
  const gate = new Promise((resolve) => { release = resolve })
  await page.route('**/chunks/BankListPage-*.js', async (route) => {
    await gate
    await route.continue()
  })
  try {
    await page.getByRole('link', { name: 'Банки', exact: true }).click()
    await page.getByRole('status', { name: 'Загрузка данных' }).waitFor()
    assert.equal(await page.getByRole('navigation', { name: 'Основная навигация' }).isVisible(), true)
    assert.equal(await page.getByRole('navigation', { name: 'Разделы приложения' }).isVisible(), true)
  } finally {
    release()
  }
  await page.getByRole('heading', { name: 'Банки и программы' }).waitFor()
})

test('failed page downloads show recovery controls and preserve navigation', async (context) => {
  const page = await openPage(context, { width: 1280, height: 900 })
  await page.route('**/chunks/BankListPage-*.js', (route) => route.abort('failed'))
  await page.getByRole('link', { name: 'Банки', exact: true }).click()
  await page.getByRole('heading', { name: 'Не удалось открыть страницу' }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Обновить страницу' }).isEnabled(), true)
  await screenshot(page, 'navigation-error.png')
  await page.getByRole('link', { name: 'На главную', exact: true }).click()
  await page.waitForURL((url) => /^\/app\/?$/.test(url.pathname))
  await page.getByRole('heading', {
    name: 'Инвестиции в недвижимость — в единой системе',
  }).waitFor()
  assert.equal(await page.getByRole('alert').count(), 0)

  await page.getByRole('link', { name: 'Банки', exact: true }).click()
  await page.getByRole('heading', { name: 'Не удалось открыть страницу' }).waitFor()
  await page.unroute('**/chunks/BankListPage-*.js')
  await Promise.all([
    page.waitForEvent('load'),
    page.getByRole('button', { name: 'Обновить страницу' }).click(),
  ])
  await page.getByRole('heading', { name: 'Банки и программы' }).waitFor()
  assert.equal(await page.getByRole('alert').count(), 0)
})
