import { chooseDictionary } from './dictionary-helpers.mjs'
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { test } from 'node:test'

import {
  createAuthenticatedPage,
  fixtureManifest,
  isolatedBaseUrl,
  isolatedWritesEnabled,
} from './isolated-helpers.mjs'

const writeTest = (name, callback) => test(
  name,
  { skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack' },
  callback,
)

async function openRoute(page, path) {
  const response = await page.goto(new URL(`/app/${path}`, isolatedBaseUrl).href)
  assert.equal(response.status(), 200)
  await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor()
}

async function submitRecord(page, apiPath, buttonName, method = 'POST') {
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === method
    && new URL(response.url()).pathname === apiPath
  ))
  await page.getByRole('button', { name: buttonName, exact: true }).click()
  const response = await responsePromise
  assert.equal(response.status(), method === 'POST' ? 201 : 200, apiPath)
  return response.json()
}

async function deleteDetailRecord(page, apiPath, listHeading) {
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === 'DELETE'
    && new URL(response.url()).pathname === apiPath
  ))
  await page.getByRole('button', { name: 'Удалить', exact: true }).click()
  await page.getByRole('alertdialog').getByRole('button', {
    name: 'Удалить', exact: true,
  }).click()
  assert.equal((await responsePromise).status(), 204)
  await page.getByRole('heading', { name: listHeading, level: 1 }).waitFor()
}

async function selectLocationChoice(page, name, choice) {
  const field = page.getByRole('combobox', { name, exact: true })
  await field.click()
  await field.fill(choice)
  await page.getByRole('option', { name: choice, exact: true }).click()
}

function locationEndpoint(dictionaryKey, identifier) {
  const endpoint = dictionaryKey.startsWith('metro') ? 'location-dictionaries' : 'location-catalogs'
  return `/api/v1/${endpoint}/${dictionaryKey}/${identifier ? `${identifier}/` : ''}`
}

async function saveLocation(page, dictionaryKey, fields, identifier = null) {
  const apiPath = locationEndpoint(dictionaryKey, identifier)
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === (identifier ? 'PATCH' : 'POST')
    && new URL(response.url()).pathname === apiPath
  ))
  await fields()
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  const response = await responsePromise
  assert.equal(response.status(), identifier ? 200 : 201, apiPath)
  return response.json()
}

async function deleteLocation(page, dictionaryKey, entry, expectedStatus = 204) {
  await openRoute(page, `locations/${dictionaryKey}?q=${encodeURIComponent(entry.name)}`)
  const apiPath = locationEndpoint(dictionaryKey, entry.id)
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === 'DELETE'
    && new URL(response.url()).pathname === apiPath
  ))
  await page.getByRole('button', { name: `Удалить: ${entry.name}` }).click()
  await page.getByRole('alertdialog').getByRole('button', {
    name: 'Удалить', exact: true,
  }).click()
  assert.equal((await responsePromise).status(), expectedStatus)
  if (expectedStatus === 204) {
    await page.waitForFunction((name) => !document.body.innerText.includes(name), entry.name)
  } else {
    await page.getByRole('alertdialog').getByRole('alert').waitFor()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Отмена' }).click()
  }
}

async function assertNoPageOverflow(page) {
  assert.equal(await page.evaluate(() => (
    document.documentElement.scrollWidth <= document.documentElement.clientWidth
  )), true, 'Page has horizontal overflow')
}

for (const width of [360, 1280]) {
  writeTest(`mortgage program preserves regional limits at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    const suffix = randomUUID().slice(0, 8)
    const name = `E2E ипотека ${suffix}`

    await openRoute(page, 'mortgage-programs/new')
    await page.getByRole('button', { name: 'Создать программу' }).click()
    await page.getByText('Укажите название программы.', { exact: true }).waitFor()
    await page.getByLabel(/^Название/).fill(name)
    await page.getByLabel(/^Федеральный лимит/).fill('12000000')
    await page.getByLabel(/^Условия/).fill('E2E условия программы')
    await page.getByLabel('Льготная программа').check()
    await page.getByRole('button', { name: 'Добавить регион' }).click()
    await chooseDictionary(page, /^Регион \*/, 'E2E регион')
    await page.getByLabel(/^Лимит, ₽/).fill('15000000')
    await assertNoPageOverflow(page)
    const program = await submitRecord(
      page, '/api/v1/mortgage-programs/', 'Создать программу',
    )
    trackCleanup(`/api/v1/mortgage-programs/${program.id}/`)
    assert.equal(program.regionalCreditLimits[0].creditLimit, '15000000.00')
    await page.getByRole('heading', { name, level: 1, exact: true }).waitFor()
    await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
    await page.getByLabel(/^Федеральный лимит/).fill('12500000')
    const updatedProgram = await submitRecord(
      page, `/api/v1/mortgage-programs/${program.id}/`,
      'Сохранить изменения', 'PATCH',
    )
    assert.equal(updatedProgram.creditLimit, '12500000.00')
    assert.equal(updatedProgram.regionalCreditLimits.length, 1)
    await deleteDetailRecord(
      page, `/api/v1/mortgage-programs/${program.id}/`, 'Ипотечные программы',
    )
  })

  writeTest(`developer mortgage program lifecycle at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    await openRoute(page, 'developer-programs/new')
    await chooseDictionary(page, /^Группа компаний/, 'E2E группа')
    await chooseDictionary(page, /^Жилой комплекс/, /^E2E квартал \(/)
    await chooseDictionary(page, /^Банк/, 'E2E банк')
    await chooseDictionary(page, /^Ипотечная программа/, 'E2E ипотечная программа')
    await page.getByLabel(/^Годовая ставка/).fill('5.75')
    await page.getByLabel(/^Первоначальный взнос/).fill('20')
    await page.getByLabel(/^Максимальная сумма/).fill('10000000')
    await assertNoPageOverflow(page)
    const program = await submitRecord(
      page, '/api/v1/developer-mortgage-programs/', 'Создать программу',
    )
    trackCleanup(`/api/v1/developer-mortgage-programs/${program.id}/`)
    assert.equal(program.realEstateComplexId, fixtureManifest.complexId)
    assert.equal(program.interestRate, '5.75')
    await page.getByRole('heading', { name: 'E2E группа', level: 1 }).waitFor()
    await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
    await page.getByLabel(/^Годовая ставка/).fill('6.25')
    const updatedProgram = await submitRecord(
      page, `/api/v1/developer-mortgage-programs/${program.id}/`,
      'Сохранить изменения', 'PATCH',
    )
    assert.equal(updatedProgram.interestRate, '6.25')
    await deleteDetailRecord(
      page, `/api/v1/developer-mortgage-programs/${program.id}/`,
      'Программы застройщиков',
    )
  })

  writeTest(`location dictionaries preserve dependent relations at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    const suffix = randomUUID().slice(0, 8)
    const regionName = `E2E область ${suffix}`
    const cityName = `E2E город ${suffix}`
    const districtName = `E2E район ${suffix}`
    const stationName = `E2E станция ${suffix}`

    await openRoute(page, 'locations/regions')
    await page.getByRole('button', { name: 'Сохранить' }).click()
    assert.equal(await page.getByLabel('Название *', { exact: true }).evaluate((input) => input.validity.valueMissing), true)
    const region = await saveLocation(page, 'regions', async () => {
      await page.getByLabel('Название *', { exact: true }).fill(regionName)
    })
    trackCleanup(locationEndpoint('regions', region.id))

    await openRoute(page, 'locations/districts')
    const district = await saveLocation(page, 'districts', async () => {
      await page.getByLabel('Название *', { exact: true }).fill(districtName)
      await selectLocationChoice(page, 'Родительская территория *', region.label)
    })
    trackCleanup(locationEndpoint('districts', district.id))
    assert.equal(district.parentId, region.id)

    await openRoute(page, 'locations/cities')
    const city = await saveLocation(page, 'localities', async () => {
      await page.getByLabel('Название *', { exact: true }).fill(cityName)
      await selectLocationChoice(page, 'Родительская территория *', district.label)
    })
    trackCleanup(locationEndpoint('localities', city.id))
    assert.equal(city.parentId, district.id)

    const systemName = `E2E система ${suffix}`
    await openRoute(page, 'locations/metro-systems')
    const system = await saveLocation(page, 'metro-systems', async () => {
      await page.getByLabel('Название системы *', { exact: true }).fill(systemName)
      await selectLocationChoice(page, 'Центр системы *', city.label)
    })
    trackCleanup(locationEndpoint('metro-systems', system.id))

    const lineName = `E2E линия ${suffix}`
    await openRoute(page, 'locations/metro-lines')
    const line = await saveLocation(page, 'metro-lines', async () => {
      await page.getByLabel('Название линии *', { exact: true }).fill(lineName)
      await selectLocationChoice(page, 'Система метро *', systemName)
    })
    trackCleanup(locationEndpoint('metro-lines', line.id))

    await openRoute(page, 'locations/metro')
    const station = await saveLocation(page, 'metro', async () => {
      await page.getByLabel(/^Название станции/).fill(stationName)
      for (const [name, choice] of [
        ['Система метро *', systemName],
        ['Линия метро *', lineName],
      ]) {
        await selectLocationChoice(page, name, choice)
      }
    })
    trackCleanup(locationEndpoint('metro', station.id))
    await openRoute(page, `locations/metro/${station.id}/edit`)
    const updatedStation = await saveLocation(page, 'metro', async () => {
      await page.getByLabel(/^Название станции/).fill(`${stationName} новая`)
    }, station.id)
    assert.equal(updatedStation.metroLine.id, line.id)
    await assertNoPageOverflow(page)

    await deleteLocation(page, 'regions', region, 409)
    await deleteLocation(page, 'metro', updatedStation)
    await deleteLocation(page, 'metro-lines', line)
    await deleteLocation(page, 'metro-systems', system)
    await deleteLocation(page, 'localities', city)
    await deleteLocation(page, 'districts', district)
    await deleteLocation(page, 'regions', region)
  })
}
