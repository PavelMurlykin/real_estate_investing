import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, createPage, screenshot } from './helpers.mjs'
import { assertReactPageLayout } from './page-layout-helpers.mjs'

for (const width of [360, 768, 1280]) {
  for (const theme of ['light', 'dark']) {
    test(`tables preserve search, numeric sorting, pagination and keyboard scrolling in ${theme} at ${width}px`, async (context) => {
      const page = await createPage(context, { width, height: 900 })
      await page.addInitScript((theme) => localStorage.setItem('theme-preference', theme), theme)
      await page.route('**/api/v1/banks/**', (route) => {
        const query = new URL(route.request().url()).searchParams
        const ordering = query.get('ordering') ?? 'name'
        let rows = Array.from({ length: 40 }, (_, index) => ({
          id: index + 1, name: 'Банк ' + String(index + 1).padStart(3, '0'), logoUrl: '', programs: [],
          programCount: index % 2, minimumInterestRate: index % 2 ? '12.75' : '3.20', isActive: true,
          updatedAt: '2026-01-11T10:00:00Z', detailUrl: '/banks/' + (index + 1), legacyDetailUrl: '/bank/banks/' + (index + 1) + '/',
        }))
        if (query.get('scope') === 'withPrograms') rows = rows.filter((row) => row.programCount > 0)
        const field = ordering.replace(/^-/, '')
        rows.sort((left, right) => (field === 'name' ? left.name.localeCompare(right.name) : Number(left[field]) - Number(right[field])) * (ordering.startsWith('-') ? -1 : 1))
        const current = Number(query.get('page') ?? 1)
        return route.fulfill({ json: { page: current, pageSize: 20, totalCount: rows.length, totalPages: Math.ceil(rows.length / 20), results: rows.slice((current - 1) * 20, current * 20) } })
      })
      await page.goto(baseUrl + '/app/banks?customerId=42')
      const table = page.getByRole('table', { name: 'Список банков' })
      await table.waitFor()
      await assertReactPageLayout(page)
      await screenshot(page, `tables-${theme}-${width}.png`)
      const pages = page.getByRole('navigation', { name: 'Страницы банков' })
      assert.equal(await pages.getByRole('button', { name: 'Назад', exact: true }).isDisabled(), true)
      await pages.getByRole('button', { name: 'Далее', exact: true }).focus()
      await page.keyboard.press('Enter')
      await pages.getByText('Страница 2 из 2', { exact: true }).waitFor()
      await screenshot(page, `pagination-${theme}-${width}.png`)
      const sort = table.getByRole('button', { name: 'Мин. ставка', exact: true })
      await sort.focus()
      await page.keyboard.press('Enter')
      const heading = table.getByRole('columnheader', { name: 'Мин. ставка', exact: true })
      await heading.and(page.locator('[aria-sort=ascending]')).waitFor()
      await page.waitForURL((url) => url.searchParams.get('ordering') === 'minimumInterestRate' && !url.searchParams.has('page'))
      await table.locator('tbody tr').first().locator('td').nth(2).filter({ hasText: '3,2' }).waitFor()
      await page.keyboard.press('Enter')
      await heading.and(page.locator('[aria-sort=descending]')).waitFor()
      await table.locator('tbody tr').first().locator('td').nth(2).filter({ hasText: '12,75' }).waitFor()
      const select = page.getByRole('combobox', { name: 'Программы', exact: true })
      await select.fill('С программами')
      assert.equal(new URL(page.url()).searchParams.has('scope'), false)
      await select.press('Enter')
      await page.waitForURL((url) => url.searchParams.get('scope') === 'withPrograms')
      assert.equal(new URL(page.url()).searchParams.get('customerId'), '42')
      await pages.waitFor({ state: 'hidden' })
      const scroll = page.getByRole('region', { name: 'Прокрутка: Список банков' })
      await scroll.focus()
      await page.waitForFunction(() => {
        const heading = document.querySelector('table thead').getBoundingClientRect()
        const header = document.querySelector('.topbar').getBoundingClientRect()
        return heading.top >= header.bottom && heading.top < innerHeight
      })
      if (await scroll.evaluate((element) => element.scrollWidth > element.clientWidth)) {
        await page.keyboard.press('ArrowRight')
        await page.waitForFunction(() => document.querySelector('.table-scroll-area').scrollLeft > 0)
      }
      await assertReactPageLayout(page)
      await screenshot(page, `table-focus-${theme}-${width}.png`)
    })
  }
}
