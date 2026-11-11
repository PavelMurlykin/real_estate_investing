import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  createIsolatedPage,
  fixtureManifest,
  isolatedBaseUrl,
  isolatedWritesEnabled,
} from './isolated-helpers.mjs'

const calculationTest = (name, callback) => test(name, {
  skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack',
}, callback)

for (const width of [360, 1280]) {
  for (const mode of ['market', 'trench']) {
    calculationTest(mode + ' quick form preserves Django field rules at ' + width + 'px', async (context) => {
      const prefix = '/api/v1/mortgage/' + (mode === 'trench' ? 'trench/' : '')
      const route = '/app/mortgage' + (mode === 'trench' ? '/trench' : '')
      const page = await createIsolatedPage(context, { width, height: 1000 }, {
        allowedUnsafeRequests: ['POST ' + prefix + 'calculate/'],
      })
      await page.goto(new URL(route, isolatedBaseUrl).href)
      const years = page.getByLabel('Срок ипотеки, лет', { exact: true })
      const months = page.getByLabel('Срок ипотеки, месяцев', { exact: true })
      await years.fill('12.5')
      assert.equal(await months.inputValue(), '144')
      await months.fill('25')
      assert.equal(await years.inputValue(), '2')
      if (mode === 'trench') {
        assert.equal(await page.getByRole('combobox', { name: /^Количество траншей/ }).inputValue(), '1')
        assert.equal(await page.getByLabel('Дата транша', { exact: true }).count(), 1)
      }
      const calculate = page.getByRole('button', {
        name: mode === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку', exact: true,
      })
      const [result] = await Promise.all([
        page.waitForResponse((response) => new URL(response.url()).pathname === prefix + 'calculate/'),
        calculate.click(),
      ])
      assert.equal(result.status(), 200)
      assert.equal((await result.json()).schedule.length, 25)

      await page.getByLabel('Дата первоначального взноса', { exact: true }).fill('9999-12-31')
      if (mode === 'trench') await page.getByLabel('Дата транша', { exact: true }).fill('9999-12-31')
      const [invalid] = await Promise.all([
        page.waitForResponse((response) => new URL(response.url()).pathname === prefix + 'calculate/'),
        calculate.click(),
      ])
      assert.equal(invalid.status(), 400)
      await page.getByText('Дата первоначального взноса слишком поздняя для указанного срока ипотеки.', { exact: true }).waitFor()

      await page.goto(new URL('/mortgage/?legacy=1', isolatedBaseUrl).href)
      await page.locator('#mortgage_term_years').fill('12.5')
      assert.equal(await page.locator('#mortgage_term_months').inputValue(), '144')
      await page.locator('#mortgage_term_months').fill('25')
      assert.equal(await page.locator('#mortgage_term_years').inputValue(), '2')
    })
  }
}

calculationTest('maximum rate and term fully repay the market loan', async (context) => {
  const page = await createIsolatedPage(context, { width: 1280, height: 1000 }, {
    allowedUnsafeRequests: ['POST /api/v1/mortgage/calculate/'],
  })
  await page.goto(new URL('/app/mortgage', isolatedBaseUrl).href)
  await page.getByLabel('Срок ипотеки, месяцев', { exact: true }).fill('600')
  await page.getByLabel('Годовая ставка, %', { exact: true }).fill('100')
  const [response] = await Promise.all([
    page.waitForResponse((entry) => new URL(entry.url()).pathname === '/api/v1/mortgage/calculate/'),
    page.getByRole('button', { name: 'Рассчитать ипотеку', exact: true }).click(),
  ])
  assert.equal(response.status(), 200)
  const result = await response.json()
  assert.equal(result.schedule.length, 600)
  assert.equal(result.schedule.at(-1).remainingDebt, '0.00')
  const kopecks = (value) => Math.round(Number(value) * 100)
  assert.equal(
    result.schedule.reduce((sum, row) => sum + kopecks(row.principalAmount), 0),
    kopecks(result.summary.loanAmount),
  )
  assert.equal(
    result.schedule.reduce((sum, row) => sum + kopecks(row.interestAmount), 0),
    kopecks(result.summary.overpayment),
  )
})

for (const mode of ['market', 'trench']) {
  calculationTest(mode + ' waits for a property passed by its natural link', async (context) => {
    const prefix = '/api/v1/mortgage/' + (mode === 'trench' ? 'trench/' : '')
    const page = await createIsolatedPage(context, { width: 1280, height: 1000 }, {
      allowedUnsafeRequests: ['POST ' + prefix + 'calculate/'],
    })
    const gate = Promise.withResolvers()
    await page.route(/\/api\/v1\/properties\/(?:\d+\/)?(?:\?.*)?$/, async (route) => {
      await gate.promise
      await route.fallback()
    })
    const calculate = page.getByRole('button', {
      name: mode === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку', exact: true,
    })
    try {
      const route = '/app/mortgage' + (mode === 'trench' ? '/trench' : '')
      await page.goto(new URL(route + '?propertyId=' + fixtureManifest.propertyId + '&propertyCost=6300000', isolatedBaseUrl).href)
      await page.getByText('Загружаем данные объекта…', { exact: true }).waitFor()
      assert.equal(await calculate.isDisabled(), true)
    } finally {
      gate.resolve()
    }
    const [response] = await Promise.all([
      page.waitForResponse((entry) => new URL(entry.url()).pathname === prefix + 'calculate/'),
      calculate.click(),
    ])
    assert.equal(response.status(), 200)
    assert.equal(response.request().postDataJSON().propertyCost, '6300000')
    assert.equal(await page.getByText('Данные изменены. Повторите расчёт перед сохранением.').count(), 0)
  })
}

