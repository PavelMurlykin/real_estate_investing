import { chooseDictionary } from './dictionary-helpers.mjs'
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { baseUrl, createPage, screenshot } from './helpers.mjs'

// Keep acceptance deterministic without depending on the external map provider.
const mapScript = `
  window.__homepageMaps = { markers: 0 };
  window.ymaps = {
    ready: (callback) => callback(),
    Map: class {
      constructor(element) {
        this.element = element;
        this.geoObjects = {
          add: () => { window.__homepageMaps.markers += 1; },
          getLength: () => window.__homepageMaps.markers,
          getBounds: () => [[59, 30], [60, 31]]
        };
        element.textContent = 'Карта загружена';
      }
      setBounds() {}
      setCenter() {}
      destroy() { this.element.textContent = ''; window.__homepageMaps.markers = 0; }
    },
    Placemark: class {},
    geocode: async () => ({ geoObjects: { get: () => ({ geometry: { getCoordinates: () => [59.9, 30.3] } }) } })
  };
`

for (const width of [360, 1280]) {
  test(`homepage preserves city, list details and lazy map at ${width}px`, async (context) => {
    const page = await createPage(context, { width, height: 1000 })
    let sdkRequests = 0
    await page.route('https://api-maps.yandex.ru/**', async (route) => {
      sdkRequests += 1
      await route.fulfill({ contentType: 'application/javascript', body: mapScript })
    })
    const response = await page.request.get(new URL('/api/v1/homepage/complexes/', baseUrl).href)
    const data = await response.json()
    assert.ok(data.selectedCity && data.results.length, 'Acceptance fixture must contain an active city and complex')
    await page.goto(new URL('/app/', baseUrl).href)
    const section = page.getByRole('region', { name: 'Жилые комплексы по городам' })
    const complex = data.results[0]
    await section.getByRole('heading', { name: complex.name, exact: true }).waitFor()
    assert.equal(await section.getByLabel('Город на главной', { exact: true }).inputValue(), data.selectedCity.name)
    assert.equal(await section.getByRole('link', { name: 'Подробнее о ЖК', exact: true }).first().getAttribute('href'), `/app/complexes/${complex.id}`)
    assert.equal(await section.getByRole('link', { name: 'Объекты ЖК', exact: true }).first().getAttribute('href'), `/app/properties?realEstateComplex=${complex.id}`)
    assert.equal(sdkRequests, 0, 'List view should not download the map SDK')
    await section.getByRole('button', { name: 'На карте', exact: true }).click()
    const map = section.getByRole('region', { name: `Карта ЖК: ${data.selectedCity.name}` })
    await map.getByText('Карта загружена', { exact: true }).waitFor()
    await page.waitForFunction(() => window.__homepageMaps?.markers > 0)
    assert.equal(sdkRequests, 1)
    await chooseDictionary(page, 'Город на главной', data.selectedCity.name)
    await page.waitForURL((url) => url.searchParams.get('city') === String(data.selectedCity.id) && url.searchParams.get('view') === 'map')
    await section.getByRole('heading', { name: complex.name, exact: true }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await screenshot(page, `homepage-map-${width}.png`)
    await section.getByRole('button', { name: 'Списком', exact: true }).click()
    await section.getByRole('region', { name: /^Карта ЖК:/ }).waitFor({ state: 'detached' })
    assert.equal(new URL(page.url()).searchParams.get('city'), String(data.selectedCity.id))
    assert.equal(await section.getByRole('region', { name: /^Карта ЖК:/ }).count(), 0)
  })
}

test('homepage retains complex cards and retries after map provider failure', async (context) => {
  const page = await createPage(context, { width: 360, height: 900 })
  let unavailable = true
  await page.route('https://api-maps.yandex.ru/**', async (route) => {
    if (unavailable) await route.abort('failed')
    else await route.fulfill({ contentType: 'application/javascript', body: mapScript })
  })
  await page.goto(new URL('/app/?view=map', baseUrl).href)
  const section = page.getByRole('region', { name: 'Жилые комплексы по городам' })
  await section.getByText('Карта временно недоступна. Список ЖК и прямые ссылки доступны ниже.', { exact: true }).waitFor()
  assert.ok(await section.getByRole('link', { name: 'Подробнее о ЖК', exact: true }).count())
  unavailable = false
  await section.getByRole('button', { name: 'Повторить загрузку карты', exact: true }).click()
  await section.getByText('Карта загружена', { exact: true }).waitFor()
  await page.waitForFunction(() => window.__homepageMaps?.markers > 0)
})
