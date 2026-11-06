import assert from 'node:assert/strict'
import { test } from 'node:test'
import { baseUrl, createPage, screenshot } from './helpers.mjs'

for (const width of [360, 1280]) {
  test(`reference filters combine search and choice, clear independently and reset at ${width}px`, async (context) => {
    const page = await createPage(context, { width, height: 1000 })
    const calls = new Set()
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname
      if (path.startsWith('/api/v1/catalog-options/')) calls.add(path)
    })
    const propertyResponse = await page.request.get(new URL('/api/v1/properties/', baseUrl).href)
    const property = (await propertyResponse.json()).results[0]
    assert.ok(property, 'A property is required to check cascades')
    const automaticLoads = Promise.all(['cities', 'developers', 'complexes', 'buildings', 'layouts'].map((dictionary) => (
      page.waitForResponse((response) => new URL(response.url()).pathname === `/api/v1/catalog-options/${dictionary}/`)
    )))
    await page.goto(new URL('/app/properties?customerId=42', baseUrl).href)
    await page.getByRole('heading', { name: 'Объекты недвижимости', exact: true }).waitFor()
    await page.waitForFunction(() => [...document.querySelectorAll('.searchable-select input')].length === 5)
    for (const response of await automaticLoads) assert.equal(response.status(), 200)
    for (const dictionary of ['cities', 'developers', 'complexes', 'buildings', 'layouts']) {
      assert.ok(calls.has(`/api/v1/catalog-options/${dictionary}/`), `${dictionary} should load automatically`)
    }
    assert.equal(await page.getByLabel('Поиск по каталогу', { exact: true }).count(), 0)
    assert.equal(await page.getByLabel('Сортировка', { exact: true }).count(), 0)
    assert.equal(await page.getByRole('button', { name: /Загрузить варианты|Показать ещё варианты/ }).count(), 0)
    const choices = await (await page.request.get(new URL('/api/v1/catalog-options/cities/', baseUrl).href)).json()
    const city = choices.results.find((item) => item.label === property.city)
    assert.ok(city)
    const cityInput = page.getByRole('combobox', { name: 'Город', exact: true })
    await cityInput.click()
    const searched = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/v1/catalog-options/cities/' && new URL(response.url()).searchParams.get('q') === property.city)
    await cityInput.fill(property.city)
    assert.equal((await searched).status(), 200)
    await page.getByRole('listbox', { name: 'Варианты: Город', exact: true }).getByRole('option', { name: property.city, exact: true }).click()
    await page.waitForURL((url) => url.searchParams.get('city') === String(city.id))
    const complexes = await (await page.request.get(new URL(`/api/v1/catalog-options/complexes/?cityId=${city.id}`, baseUrl).href)).json()
    const complex = complexes.results.find((item) => item.label === property.realEstateComplex)
    assert.ok(complex)
    await page.getByRole('combobox', { name: 'Жилой комплекс', exact: true }).click()
    await page.getByRole('listbox', { name: 'Варианты: Жилой комплекс', exact: true }).getByRole('option', { name: complex.label, exact: true }).click()
    await page.waitForURL((url) => url.searchParams.get('realEstateComplex') === String(complex.id))
    await page.getByLabel('Площадь, м²', { exact: true }).fill(property.area)
    await cityInput.click()
    await page.getByRole('listbox', { name: 'Варианты: Город', exact: true }).getByRole('option', { name: 'Все', exact: true }).click()
    await page.waitForURL((url) => !url.searchParams.has('city'))
    assert.equal(new URL(page.url()).searchParams.get('realEstateComplex'), String(complex.id))
    assert.equal(new URL(page.url()).searchParams.get('area'), property.area)
    assert.equal(new URL(page.url()).searchParams.get('customerId'), '42')
    await page.getByLabel('Номер квартиры').fill('zz-no-match-filter-827')
    await page.getByRole('heading', { name: 'По вашему запросу ничего не найдено', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Сбросить', exact: true }).click()
    await page.waitForURL((url) => url.search === '?customerId=42')
    const table = page.getByRole('table', { name: 'Список объектов недвижимости' })
    await table.waitFor()
    assert.equal(await page.getByLabel('Площадь, м²', { exact: true }).inputValue(), '')
    assert.equal(await cityInput.inputValue(), '')
    await table.getByRole('button', { name: 'Стоимость', exact: true }).click()
    await page.waitForURL((url) => url.searchParams.get('ordering') === 'propertyCost')
    await table.getByRole('columnheader', { name: 'Стоимость' }).and(page.locator('[aria-sort="ascending"]')).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await screenshot(page, `filter-controls-${width}.png`)
  })
}
