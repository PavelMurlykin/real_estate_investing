import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, createPage, openPage, screenshot } from './helpers.mjs'
import { assertReactPageLayout } from './page-layout-helpers.mjs'

const homeHeading = 'Инвестиции в недвижимость — в единой системе'
const publicPages = [
  ['/app/', homeHeading],
  ['/app/properties', 'Объекты недвижимости'],
  ['/app/company-groups', 'Группы компаний'],
  ['/app/developers', 'Застройщики'],
  ['/app/complexes', 'Жилые комплексы'],
  ['/app/banks', 'Банки и программы'],
  ['/app/mortgage-programs', 'Ипотечные программы'],
  ['/app/developer-programs', 'Программы застройщиков'],
  ['/app/key-rate', 'Ключевая ставка'],
  ['/app/dictionaries/real-estate-types', 'Справочники объектов'],
  ['/app/locations/regions', 'Локации'],
  ['/app/mortgage', 'Ипотечный калькулятор'],
  ['/app/mortgage/trench', 'Ипотечный калькулятор'],
  ['/app/login', 'Вход'],
  ['/app/register', 'Регистрация'],
  ['/app/password/reset', 'Восстановление пароля'],
  ['/app/password/reset/confirm', 'Новый пароль'],
]

for (const width of [360, 768, 1280]) {
  for (const [route, heading] of publicPages) {
    test(`public route ${route} loads without errors or overflow at ${width}px`, async (context) => {
      const page = await createPage(context, { width, height: 900 })
      const errors = []
      page.on('pageerror', (error) => errors.push(error.message))
      const response = await page.goto(new URL(route, baseUrl).href)
      assert.equal(response?.status(), 200)
      await page.getByRole('main').getByRole('heading', { name: heading, exact: true }).waitFor()
      assert.equal(await page.getByRole('alert').count(), 0)
      await assertReactPageLayout(page)
      assert.deepEqual(errors, [])
      const primary = page.getByRole('navigation', { name: 'Основная навигация' })
      assert.deepEqual(await primary.getByRole('link').evaluateAll((links) =>
        links.map((link) => new URL(link.href).pathname)), [
        '/app/properties', '/app/mortgage',
      ])
      const overflow = await page.evaluate(() => ({
        present: document.documentElement.scrollWidth > window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: window.innerWidth,
        elements: [...document.querySelectorAll('body *')]
          .filter((element) => element.getBoundingClientRect().right > window.innerWidth + 1)
          .slice(0, 8)
          .map((element) => ({
            className: element.className,
            right: Math.round(element.getBoundingClientRect().right),
            tagName: element.tagName,
          })),
      }))
      assert.equal(overflow.present, false, JSON.stringify(overflow))
      if (route === '/app/properties') await screenshot(page, `catalog-${width}.png`)
    })
  }
}

for (const [route, heading] of [
  ['/app/customers', 'Войдите, чтобы открыть список клиентов'],
  ['/app/mortgage/calculations', 'Войдите, чтобы открыть историю'],
  ['/app/mortgage/trench/calculations', 'Войдите, чтобы открыть историю'],
  ['/app/banks/new', 'Войдите для управления банками'],
]) {
  test(`anonymous access to ${route} offers login with a return URL`, async (context) => {
    const page = await openPage(context, { width: 1280, height: 900 }, route, heading)
    const sections = page.getByRole('navigation', { name: 'Разделы приложения' })
    assert.equal(await sections.getByRole('link', { name: 'Клиенты', exact: true }).count(), 0)
    const login = page.getByRole('main').getByRole('link', { name: 'Войти', exact: true })
    await login.click()
    await page.getByRole('heading', { name: 'Вход', exact: true }).waitFor()
    const url = new URL(page.url())
    assert.match(url.pathname, /^\/app\/login\/?$/)
    assert.equal(url.searchParams.get('next'), route)
    assert.equal(await page.getByLabel('Email или телефон').isVisible(), true)
  })
}

for (const route of ['/app/profile', '/app/password/change']) {
  test(`anonymous direct access to ${route} redirects to React login`, async (context) => {
    const page = await openPage(context, { width: 1280, height: 900 }, route, 'Вход')
    const url = new URL(page.url())
    assert.match(url.pathname, /^\/app\/login\/?$/)
    assert.equal(url.searchParams.get('next'), route)
    assert.equal(await page.getByRole('alert').count(), 0)
  })
}

test('anonymous users cannot open the property creation form', async (context) => {
  const page = await openPage(context, { width: 1280, height: 900 },
    '/app/properties/new', 'Недостаточно прав')
  assert.equal(await page.getByRole('button', { name: /Сохранить|Создать/ }).count(), 0)
  await page.getByRole('link', { name: 'К каталогу', exact: true }).click()
  await page.getByRole('heading', { name: 'Объекты недвижимости', exact: true }).waitFor()
  assert.equal(await page.getByRole('link', { name: 'Добавить объект' }).count(), 0)
})

test('catalog field filters and header ordering survive reload and browser history', async (context) => {
  const page = await openPage(context, { width: 1280, height: 900 }, '/app/properties')
  const table = page.getByRole('table', { name: 'Список объектов недвижимости' })
  const search = page.getByLabel('Номер квартиры')
  const apartment = (await table.locator('tbody tr').first().locator('td').nth(4).textContent()).trim()
  await search.fill(apartment)
  await page.waitForURL((url) => url.searchParams.get('apartmentNumber') === apartment)
  const ordering = table.getByRole('button', { name: 'Стоимость', exact: true })
  const costHeader = table.getByRole('columnheader', { name: 'Стоимость' })
  const waitForCostOrder = async (direction) => {
    const parameter = direction === 'ascending' ? 'propertyCost' : '-propertyCost'
    await page.waitForURL((url) => url.searchParams.get('ordering') === parameter)
    await costHeader.and(page.locator(`[aria-sort="${direction}"]`)).waitFor()
  }
  await ordering.click()
  await page.keyboard.press('Enter')
  await waitForCostOrder('descending')
  assert.equal(await ordering.evaluate((element) => element === document.activeElement), true)
  assert.equal(new URL(page.url()).searchParams.get('apartmentNumber'), apartment)
  await page.reload()
  await search.waitFor()
  assert.equal(await search.inputValue(), apartment)
  await waitForCostOrder('descending')
  await page.goBack()
  await waitForCostOrder('ascending')
  assert.equal(await search.inputValue(), apartment)
  await page.goForward()
  await waitForCostOrder('descending')
  await ordering.click()
  await waitForCostOrder('ascending')
  await page.keyboard.press('Space')
  await waitForCostOrder('descending')
  await page.getByRole('button', { name: 'Сбросить', exact: true }).click()
  await page.waitForURL((url) => url.search === '')
  await table.getByRole('columnheader', { name: 'Город' }).and(page.locator('[aria-sort="ascending"]')).waitFor()
  assert.equal(await search.inputValue(), '')
  assert.equal(await page.getByRole('alert').count(), 0)
})

test('a failed catalog API request can be retried without losing navigation', async (context) => {
  const page = await createPage(context, { width: 1280, height: 900 })
  await page.route('**/api/v1/properties/**', (route) => route.fulfill({
    status: 503, contentType: 'application/json', body: '{}',
  }))
  await page.goto(new URL('/app/properties', baseUrl).href)
  await page.getByRole('heading', { name: 'Не удалось загрузить данные' }).waitFor()
  assert.equal(await page.getByRole('navigation', { name: 'Основная навигация' }).isVisible(), true)
  await page.unroute('**/api/v1/properties/**')
  await page.getByRole('button', { name: 'Повторить', exact: true }).click()
  await page.getByRole('heading', { name: 'Объекты недвижимости', exact: true }).waitFor()
  assert.equal(await page.getByRole('alert').count(), 0)
})

test('an unknown React URL provides a working way home', async (context) => {
  const page = await openPage(context, { width: 360, height: 900 },
    '/app/e2e-unknown-route', 'Такой страницы нет')
  await page.getByRole('link', { name: 'Вернуться на главную', exact: true }).click()
  await page.getByRole('heading', { name: homeHeading, exact: true }).waitFor()
  assert.equal(await page.getByRole('alert').count(), 0)
})

test('key rate chart stays wide and compact, spaces years and enlarges points on hover', async (context) => {
  const page = await createPage(context, { width: 2048, height: 1000 })
  const points = [
    { meetingDate: '2013-09-17', keyRate: '5.50' },
    { meetingDate: '2022-02-28', keyRate: '20.00' },
    { meetingDate: '2023-07-24', keyRate: '8.50' },
    { meetingDate: '2024-10-28', keyRate: '21.00' },
    { meetingDate: '2026-10-23', keyRate: '14.00' },
  ]
  await page.route('**/api/v1/key-rates/chart/', (route) => route.fulfill({ json: points }))
  await page.route('**/api/v1/key-rates/', (route) => route.fulfill({ json: {
    page: 1, pageSize: 20, totalCount: points.length, totalPages: 1,
    currentRate: points.at(-1), lastSyncedAt: null, legacyUrl: '/bank/key-rate/',
    results: points.map((point, index) => ({
      ...point, id: index + 1, rateChange: null, isActive: true, updatedAt: '2026-11-05T00:00:00Z',
    })).reverse(),
  } }))
  await page.goto(new URL('/app/key-rate', baseUrl).href)

  const graph = page.getByRole('img', { name: 'Динамика ключевой ставки' })
  await graph.waitFor()
  const figure = page.locator('figure.key-rate-chart')
  const content = page.getByRole('main').locator('.key-rate-page')
  const table = page.getByRole('table', { name: 'История ключевой ставки Банка России' })
  const count = page.locator('.results-heading')
  await table.waitFor()
  assert((await figure.boundingBox()).width > 1380)
  for (const [width, yearStep] of [[2048, 1], [600, 2], [360, 3], [2048, 1]]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.waitForFunction(() => {
      const svg = document.querySelector('.key-rate-chart svg')
      return Math.abs(svg.viewBox.baseVal.width - svg.getBoundingClientRect().width) < 1
    })
    const figureBox = await figure.boundingBox()
    const contentBox = await content.boundingBox()
    assert(Math.abs(figureBox.x - contentBox.x) < 1)
    assert(Math.abs(figureBox.width - contentBox.width) < 1)
    const graphBox = await graph.boundingBox()
    assert(graphBox.height <= 272)
    const gridLine = await graph.locator('.key-rate-chart__grid').first().boundingBox()
    assert(gridLine.width > graphBox.width - 80)
    const yearLabels = await graph.locator('.key-rate-chart__year').evaluateAll((labels) => labels.map((label) => {
      const { left, right } = label.getBoundingClientRect()
      return { year: Number(label.textContent), left, right }
    }))
    assert(yearLabels.length > 1)
    assert.equal(yearLabels.at(-1).year, 2026)
    for (let index = 1; index < yearLabels.length; index++) {
      const previous = yearLabels[index - 1]
      const current = yearLabels[index]
      assert.equal(current.year - previous.year, yearStep, `year interval at ${width}px`)
      assert(current.left >= previous.right, `year labels overlap at ${width}px`)
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    const countBox = await count.boundingBox()
    assert(countBox.y + countBox.height <= (await table.boundingBox()).y)
  }

  const circles = graph.locator('circle')
  const linePoints = await graph.locator('polyline').evaluate((line) =>
    Array.from(line.points, ({ x, y }) => [x, y]))
  const markerPoints = await circles.evaluateAll((markers) =>
    markers.map((marker) => [marker.cx.baseVal.value, marker.cy.baseVal.value]))
  assert.deepEqual(linePoints, markerPoints)
  for (const date of ['28.02.2022', '23.10.2026']) {
    const point = circles.filter({ hasText: date })
    const original = await point.boundingBox()
    await point.hover()
    assert((await point.boundingBox()).width > original.width)
    await figure.locator('figcaption').hover()
    assert.equal((await point.boundingBox()).width, original.width)
  }
})

test('mortgage program descriptions wrap and reset stays beside search', async (context) => {
  const page = await createPage(context, { width: 1280, height: 900 })
  const description = `Длинное описание ипотечной программы. ${'СловоБезПробелов'.repeat(16)}`
  await page.route('**/api/v1/auth/session/', (route) => route.fulfill({ json: {
    isAuthenticated: true,
    user: { id: 1, displayName: 'Модератор', email: 'manager@example.com', agencyName: '' },
    capabilities: {
      manageCatalogs: true, syncExternalData: false, viewPrivateRecords: true, viewAllPrivateRecords: false,
    },
  } }))
  await page.route('**/api/v1/mortgage-programs/', (route) => route.fulfill({ json: {
    page: 1, pageSize: 20, totalCount: 1, totalPages: 1,
    results: [{
      id: 5, name: 'Семейная ипотека', condition: description, isPreferential: true,
      creditLimit: '12000000.00', bankCount: 2, developerProgramCount: 1, regionalLimitCount: 1,
      isActive: true, updatedAt: '2026-01-11T10:00:00Z',
      detailUrl: '/mortgage-programs/5', legacyEditUrl: '/bank/?model=mortgage_program&edit=5',
    }],
  } }))
  await page.goto(new URL('/app/mortgage-programs', baseUrl).href)
  const table = page.getByRole('table', { name: 'Список ипотечных программ' })
  const descriptionCell = table.getByRole('cell', { name: description })
  await table.getByRole('columnheader', { name: 'Действия' }).waitFor()

  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 })
    const search = await page.getByRole('searchbox', { name: 'Поиск' }).boundingBox()
    const reset = await page.getByRole('button', { name: 'Сбросить' }).boundingBox()
    const type = await page.getByLabel('Тип программы').boundingBox()
    if (width === 1280) {
      assert(type.x + type.width <= search.x)
      assert(Math.abs(type.y - search.y) < 1)
    } else {
      assert(type.y + type.height <= search.y)
    }
    assert(reset.x >= search.x + search.width)
    assert(Math.abs(reset.y - search.y) < 1)
    assert(await table.evaluate((element) => element.parentElement.scrollWidth <= element.parentElement.clientWidth))
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))

    const wrapsInsideCell = await descriptionCell.evaluate((cell) => {
      const range = document.createRange()
      range.selectNodeContents(cell)
      const lines = [...range.getClientRects()]
      const bounds = cell.getBoundingClientRect()
      return lines.length > 1 && lines.every((line) => line.left >= bounds.left && line.right <= bounds.right)
    })
    assert(wrapsInsideCell, `description overflows at ${width}px`)
  }
})

test('developer programs search as you type and keep reset after the filters on the same row', async (context) => {
  const page = await openPage(context, { width: 1280, height: 900 }, '/app/developer-programs')
  const search = page.getByRole('searchbox', { name: 'Поиск' })
  const program = page.getByRole('combobox', { name: 'Программа', exact: true })
  const reset = page.getByRole('button', { name: 'Сбросить', exact: true })
  assert.equal(await page.getByRole('link', { name: 'Прежняя версия' }).count(), 0)
  assert.equal(await page.getByRole('button', { name: 'Найти' }).count(), 0)
  assert.equal(await page.getByRole('combobox', { name: 'Статус', exact: true }).count(), 0)
  for (const name of ['Группа компаний', 'Жилой комплекс', 'Банк', 'Программа']) {
    await page.getByRole('combobox', { name, exact: true }).waitFor()
  }

  for (const width of [1280, 900, 700, 360]) {
    await page.setViewportSize({ width, height: 900 })
    const programBox = await program.boundingBox()
    const resetBox = await reset.boundingBox()
    assert(resetBox.x >= programBox.x + programBox.width)
    assert(Math.abs(resetBox.y + resetBox.height - programBox.y - programBox.height) < 1)
  }

  const searchText = 'zz-no-developer-program-827'
  const results = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/api/v1/developer-mortgage-programs/'
      && url.searchParams.get('q') === searchText
  })
  await search.fill(searchText)
  assert.equal((await results).status(), 200)
  await page.getByRole('heading', { name: 'Программы застройщиков не найдены' }).waitFor()
  await reset.click()
  await page.waitForURL((url) => url.search === '')
  await page.waitForFunction(() => document.querySelector('#developer-program-search')?.value === '')
})

test('bank search updates live and reset follows the program filter on the same row', async (context) => {
  const page = await openPage(context, { width: 1280, height: 900 }, '/app/banks')
  const search = page.getByRole('searchbox', { name: 'Поиск' })
  const scope = page.getByRole('combobox', { name: 'Программы', exact: true })
  const reset = page.getByRole('button', { name: 'Сбросить', exact: true })
  assert.equal(await page.getByRole('link', { name: 'Прежняя версия' }).count(), 0)
  assert.equal(await page.getByRole('button', { name: 'Найти' }).count(), 0)
  assert.equal(await page.getByRole('combobox', { name: 'Статус', exact: true }).count(), 0)

  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 })
    const filterBox = await scope.boundingBox()
    const resetBox = await reset.boundingBox()
    assert(resetBox.x >= filterBox.x + filterBox.width)
    assert(Math.abs(resetBox.y + resetBox.height - filterBox.y - filterBox.height) < 1)
  }

  const searchText = 'zz-no-bank-827'
  await scope.selectOption('withPrograms')
  const results = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/api/v1/banks/'
      && url.searchParams.get('q') === searchText
      && url.searchParams.get('scope') === 'withPrograms'
  })
  await search.fill(searchText)
  assert.equal((await results).status(), 200)
  await page.getByRole('heading', { name: 'Банки не найдены' }).waitFor()
  await reset.click()
  await page.waitForURL((url) => url.search === '')
  await page.waitForFunction(() => document.querySelector('#bank-search')?.value === ''
    && document.querySelector('#bank-program-scope')?.value === 'all')
})

test('bank table fits narrow screens with long names and catalog actions', async (context) => {
  const page = await createPage(context, { width: 1280, height: 900 })
  const names = [
    'Межрегиональный банк жилищного финансирования и долгосрочного развития',
    'ДлинноеНазваниеБезПробелов'.repeat(7),
  ]
  await page.route('**/api/v1/auth/session/', (route) => route.fulfill({ json: {
    isAuthenticated: true,
    user: { id: 1, displayName: 'Модератор', email: 'manager@example.com', agencyName: '' },
    capabilities: {
      manageCatalogs: true, syncExternalData: false, viewPrivateRecords: true, viewAllPrivateRecords: false,
    },
  } }))
  await page.route('**/api/v1/banks/', (route) => route.fulfill({ json: {
    page: 1, pageSize: 20, totalCount: names.length, totalPages: 1,
    results: names.map((name, index) => ({
      id: index + 1, name, logoUrl: '', programCount: 20, programs: [],
      minimumInterestRate: '12.75', isActive: true, updatedAt: '2026-01-11T10:00:00Z',
      detailUrl: `/banks/${index + 1}`, legacyDetailUrl: `/bank/banks/${index + 1}/`,
    })),
  } }))
  await page.goto(new URL('/app/banks', baseUrl).href)
  const table = page.getByRole('table', { name: 'Список банков' })
  await table.getByRole('columnheader', { name: 'Действия' }).waitFor()
  for (const width of [1280, 600, 360, 320]) {
    await page.setViewportSize({ width, height: 900 })
    assert(await table.evaluate((element) => element.parentElement.scrollWidth <= element.parentElement.clientWidth))
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    for (const name of names) {
      const layout = await table.getByRole('link', { name, exact: true }).evaluate((link) => {
        const range = document.createRange()
        range.selectNodeContents(link)
        const lines = [...range.getClientRects()]
        const cell = link.closest('td').getBoundingClientRect()
        return {
          lineCount: lines.length,
          insideCell: lines.every((line) => line.left >= cell.left && line.right <= cell.right),
        }
      })
      assert(layout.insideCell, `bank name overflows at ${width}px`)
      if (width <= 360) assert(layout.lineCount > 1, `bank name did not wrap at ${width}px`)
      assert(await table.getByRole('link', { name: `Редактировать: ${name}`, exact: true }).isVisible())
      assert(await table.getByRole('button', { name: `Удалить: ${name}`, exact: true }).isVisible())
    }
  }
})

test('wide tables keep accessible action labels and scrolling inside the card', async (context) => {
  const page = await createPage(context, { width: 1280, height: 900 })
  // A populated fixture ensures this regression is tested even on an empty database.
  await page.route('**/api/v1/complexes/', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      page: 1, pageSize: 20, totalCount: 1, totalPages: 1,
      results: [{
        id: 7, name: 'Тестовый жилой комплекс',
        developer: { id: 4, name: 'Тестовый застройщик', label: 'Тестовый застройщик' },
        city: 'Санкт-Петербург', realEstateClass: 'Бизнес', realEstateType: 'Квартира',
        buildingCount: 3, isActive: true,
      }],
    }),
  }))
  await page.goto(new URL('/app/complexes', baseUrl).href)
  const table = page.getByRole('table', { name: 'Список жилых комплексов' })
  await table.waitFor()
  const count = await page.locator('.results-heading').boundingBox()
  assert(count.y + count.height <= (await table.boundingBox()).y)
  assert.equal(await table.getByRole('columnheader', { name: 'Действия' }).count(), 1)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  const scrollsInsideCard = await table.evaluate((element) => {
    const container = element.parentElement
    container.scrollLeft = container.scrollWidth
    return container.scrollWidth > container.clientWidth && container.scrollLeft > 0
  })
  assert.equal(scrollsInsideCard, true)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await screenshot(page, 'wide-table-contained.png')
})
