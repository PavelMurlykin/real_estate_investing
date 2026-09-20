import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, createPage, openPage, screenshot } from './helpers.mjs'

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
  ['/app/mortgage/trench', 'Траншевая ипотека'],
  ['/app/login', 'Вход'],
  ['/app/register', 'Регистрация'],
  ['/app/password/reset', 'Восстановление пароля'],
]

for (const width of [360, 1280]) {
  for (const [route, heading] of publicPages) {
    test(`public route ${route} loads without errors or overflow at ${width}px`, async (context) => {
      const page = await createPage(context, { width, height: 900 })
      const errors = []
      page.on('pageerror', (error) => errors.push(error.message))
      const response = await page.goto(new URL(route, baseUrl).href)
      assert.equal(response?.status(), 200)
      await page.getByRole('main').getByRole('heading', { name: heading, exact: true }).waitFor()
      assert.equal(await page.getByRole('alert').count(), 0)
      assert.deepEqual(errors, [])
      const primary = page.getByRole('navigation', { name: 'Основная навигация' })
      assert.deepEqual(await primary.getByRole('link').evaluateAll((links) =>
        links.map((link) => new URL(link.href).pathname)), [
        '/app/properties', '/app/mortgage',
      ])
      assert.equal(await page.evaluate(() =>
        document.documentElement.scrollWidth <= window.innerWidth), true)
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

test('catalog search and ordering survive reload and browser history', async (context) => {
  const page = await openPage(context, { width: 1280, height: 900 }, '/app/properties')
  const search = page.getByLabel('Поиск по каталогу')
  const ordering = page.getByLabel('Сортировка', { exact: true })
  // Independent of whatever records the local acceptance database contains.
  const phrase = 'e2e-no-match-8b47bd3e'
  await search.fill(phrase)
  await page.getByRole('button', { name: 'Найти', exact: true }).click()
  await page.waitForURL((url) => url.searchParams.get('search') === phrase)
  await page.getByRole('heading', { name: 'По вашему запросу ничего не найдено' }).waitFor()
  await ordering.focus()
  await ordering.selectOption('-propertyCost')
  await page.waitForURL((url) => url.searchParams.get('ordering') === '-propertyCost')
  assert.equal(await ordering.evaluate((element) => element === document.activeElement), true)
  assert.equal(new URL(page.url()).searchParams.get('search'), phrase)
  await page.reload()
  await search.waitFor()
  assert.equal(await search.inputValue(), phrase)
  assert.equal(await ordering.inputValue(), '-propertyCost')
  await page.goBack()
  await page.waitForURL((url) => !url.searchParams.has('ordering'))
  assert.equal(await ordering.inputValue(), 'city')
  assert.equal(await search.inputValue(), phrase)
  await page.goForward()
  await page.waitForURL((url) => url.searchParams.get('ordering') === '-propertyCost')
  assert.equal(await ordering.inputValue(), '-propertyCost')
  await page.getByRole('button', { name: 'Сбросить фильтры' }).click()
  await page.waitForURL((url) => url.search === '')
  await page.waitForFunction(() =>
    document.getElementById('property-search')?.value === ''
    && document.getElementById('property-ordering')?.value === 'city')
  assert.equal(await search.inputValue(), '')
  assert.equal(await ordering.inputValue(), 'city')
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
