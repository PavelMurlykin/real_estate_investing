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

async function saveLocation(page, dictionaryKey, fields, identifier = null) {
  const apiPath = identifier
    ? `/api/v1/location-dictionaries/${dictionaryKey}/${identifier}/`
    : `/api/v1/location-dictionaries/${dictionaryKey}/`
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
  const apiPath = `/api/v1/location-dictionaries/${dictionaryKey}/${entry.id}/`
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
  writeTest(`mortgage program preserves regional limits and aliases at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    const suffix = randomUUID().slice(0, 8)
    const name = `E2E ипотека ${suffix}`
    const alias = `E2E внешнее имя ${suffix}`

    await openRoute(page, 'mortgage-programs/new')
    await page.getByRole('button', { name: 'Создать программу' }).click()
    await page.getByText('Укажите название программы.', { exact: true }).waitFor()
    await page.getByLabel(/^Название/).fill(name)
    await page.getByLabel(/^Федеральный лимит/).fill('12000000')
    await page.getByLabel(/^Условия/).fill('E2E условия программы')
    await page.getByLabel('Льготная программа').check()
    await page.getByRole('button', { name: 'Добавить регион' }).click()
    await page.getByLabel(/^Регион \*/).selectOption({ label: 'E2E регион' })
    await page.getByLabel(/^Лимит, ₽/).fill('15000000')
    await page.getByRole('button', { name: 'Добавить алиас' }).click()
    await page.locator('input[name="aliases.0.sourceName"]').fill(alias)
    await page.locator('input[name="aliases.0.source"]').fill('E2E источник')
    await assertNoPageOverflow(page)
    const program = await submitRecord(
      page, '/api/v1/mortgage-programs/', 'Создать программу',
    )
    trackCleanup(`/api/v1/mortgage-programs/${program.id}/`)
    assert.equal(program.regionalCreditLimits[0].creditLimit, '15000000.00')
    assert.equal(program.aliases[0].sourceName, alias)
    await page.getByRole('heading', { name, level: 1, exact: true }).waitFor()
    await page.getByText(alias, { exact: true }).filter({ visible: true }).waitFor()
    await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
    await page.getByLabel(/^Федеральный лимит/).fill('12500000')
    const updatedProgram = await submitRecord(
      page, `/api/v1/mortgage-programs/${program.id}/`,
      'Сохранить изменения', 'PATCH',
    )
    assert.equal(updatedProgram.creditLimit, '12500000.00')
    assert.equal(updatedProgram.regionalCreditLimits.length, 1)
    assert.equal(updatedProgram.aliases.length, 1)
    await deleteDetailRecord(
      page, `/api/v1/mortgage-programs/${program.id}/`, 'Ипотечные программы',
    )
  })

  writeTest(`developer mortgage program lifecycle at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    await openRoute(page, 'developer-programs/new')
    await page.getByLabel(/^Группа компаний/).selectOption(String(fixtureManifest.companyGroupId))
    await page.getByLabel(/^Жилой комплекс/).selectOption(String(fixtureManifest.complexId))
    await page.getByLabel(/^Банк/).selectOption(String(fixtureManifest.bankId))
    await page.getByLabel(/^Ипотечная программа/).selectOption(String(fixtureManifest.mortgageProgramId))
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
    await page.getByText('Укажите название.', { exact: true }).waitFor()
    const region = await saveLocation(page, 'regions', async () => {
      await page.getByLabel(/^Название региона/).fill(regionName)
      await page.getByLabel(/^Код региона/).fill(`T${suffix.slice(0, 6)}`)
    })
    trackCleanup(`/api/v1/location-dictionaries/regions/${region.id}/`)

    await openRoute(page, 'locations/cities')
    const city = await saveLocation(page, 'cities', async () => {
      await page.getByLabel(/^Название города/).fill(cityName)
      await page.getByLabel(/^Регион \*/).selectOption(String(region.id))
    })
    trackCleanup(`/api/v1/location-dictionaries/cities/${city.id}/`)

    await openRoute(page, 'locations/districts')
    const district = await saveLocation(page, 'districts', async () => {
      await page.getByLabel(/^Название района/).fill(districtName)
      await page.getByLabel(/^Регион \*/).selectOption(String(region.id))
      await page.getByLabel(/^Город \*/).selectOption(String(city.id))
    })
    trackCleanup(`/api/v1/location-dictionaries/districts/${district.id}/`)
    assert.equal(district.city.id, city.id)

    await openRoute(page, 'locations/metro')
    const station = await saveLocation(page, 'metro', async () => {
      await page.getByLabel(/^Название станции/).fill(stationName)
      await page.getByLabel(/^Регион \*/).selectOption({ label: 'E2E регион' })
      await page.getByLabel(/^Город \*/).selectOption({ label: 'E2E город' })
      await page.getByLabel('Линия метро *', { exact: true }).selectOption(
        String(fixtureManifest.metroLineId),
      )
    })
    trackCleanup(`/api/v1/location-dictionaries/metro/${station.id}/`)
    await openRoute(page, `locations/metro/${station.id}/edit`)
    const updatedStation = await saveLocation(page, 'metro', async () => {
      await page.getByLabel(/^Название станции/).fill(`${stationName} новая`)
    }, station.id)
    assert.equal(updatedStation.metroLine.id, fixtureManifest.metroLineId)
    await assertNoPageOverflow(page)

    await deleteLocation(page, 'regions', region, 409)
    await deleteLocation(page, 'metro', updatedStation)
    await deleteLocation(page, 'districts', district)
    await deleteLocation(page, 'cities', city)
    await deleteLocation(page, 'regions', region)
  })
}
