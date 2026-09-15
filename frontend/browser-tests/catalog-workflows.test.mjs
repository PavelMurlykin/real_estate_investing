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
  const payload = await response.json()
  assert.ok(Number.isInteger(payload.id) && payload.id > 0)
  return payload
}

async function selectLocation(page) {
  await page.getByLabel(/^Регион \*/).selectOption({ label: 'E2E регион' })
  await page.getByLabel(/^Город \*/).selectOption({ label: 'E2E город' })
  await page.getByLabel(/^Район \*/).selectOption({ label: 'E2E район' })
}

async function deleteDetailRecord(page, apiPath, status = 204) {
  await page.getByRole('button', { name: 'Удалить', exact: true }).click()
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === 'DELETE'
    && new URL(response.url()).pathname === apiPath
  ))
  await page.getByRole('alertdialog').getByRole('button', {
    name: 'Удалить', exact: true,
  }).click()
  assert.equal((await responsePromise).status(), status)
}

for (const width of [360, 1280]) {
  writeTest(`developer, complex and property lifecycle at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    const suffix = randomUUID().slice(0, 8)
    const developerName = `E2E застройщик ${suffix}`
    const complexName = `E2E квартал ${suffix}`
    const apartmentNumber = `E2E-${suffix}`

    await openRoute(page, 'developers/new')
    await page.getByLabel(/^Название/).fill(developerName)
    await page.getByLabel('Регионы', { exact: true }).selectOption({ label: 'E2E регион' })
    const developer = await submitRecord(page, '/api/v1/developers/', 'Создать застройщика')
    trackCleanup(`/api/v1/developers/${developer.id}/`)
    await openRoute(page, `developers?q=${encodeURIComponent(developerName)}`)
    await page.getByText(developerName, { exact: true }).filter({ visible: true }).waitFor()
    await page.getByRole('link', { name: /Редактировать/ }).click()
    await page.getByRole('textbox', { name: 'Описание', exact: true }).fill(
      'E2E описание после редактирования',
    )
    const updatedDeveloper = await submitRecord(
      page, `/api/v1/developers/${developer.id}/`, 'Сохранить изменения', 'PATCH',
    )
    assert.equal(updatedDeveloper.regions.length, 1)

    await openRoute(page, 'complexes/new')
    await page.getByLabel(/^Название ЖК/).fill(complexName)
    await page.getByLabel(/^Застройщик \*/).selectOption({ label: developerName })
    await page.getByLabel(/^Класс ЖК/).selectOption({ label: 'E2E комфорт' })
    await page.getByLabel(/^Тип недвижимости/).selectOption({ label: 'E2E квартира' })
    await selectLocation(page)
    await page.getByRole('button', { name: 'Добавить корпус' }).click()
    await page.getByLabel(/^Номер корпуса 1/).fill('E2E-1')
    await page.getByLabel(/^Номер корпуса 2/).fill('E2E-2')
    await page.getByLabel('Год ввода', { exact: true }).first().fill('2027')
    await page.getByLabel(/^Квартал ввода/).first().selectOption('2')
    const complex = await submitRecord(page, '/api/v1/complexes/', 'Создать ЖК')
    trackCleanup(`/api/v1/complexes/${complex.id}/`)
    await page.getByRole('heading', { name: complexName, level: 1, exact: true }).waitFor()
    await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
    await page.getByLabel('Описание', { exact: true }).fill('E2E обновлённый ЖК')
    await submitRecord(page, `/api/v1/complexes/${complex.id}/`, 'Сохранить изменения', 'PATCH')
    await page.getByRole('heading', { name: complexName, level: 1, exact: true }).waitFor()

    await openRoute(page, 'properties/new')
    await selectLocation(page)
    await page.getByLabel(/^Застройщик \*/).selectOption({ label: developerName })
    await page.getByLabel(/^Жилой комплекс/).selectOption({ label: complexName })
    await page.getByLabel(/^Корпус \*/).selectOption({ label: 'E2E-1' })
    await page.getByLabel(/^Номер квартиры/).fill(apartmentNumber)
    await page.getByLabel(/^Площадь/).fill('54.25')
    await page.getByLabel(/^Этаж \*/).fill('5')
    await page.getByLabel(/^Стоимость/).fill('5100000')
    await page.getByLabel(/^Планировка \*/).selectOption({ label: 'E2E планировка' })
    await page.getByLabel(/^Отделка \*/).selectOption({ label: 'E2E отделка' })
    const property = await submitRecord(page, '/api/v1/properties/', 'Создать объект')
    trackCleanup(`/api/v1/properties/${property.id}/`)
    await page.getByRole('heading', { name: `${complexName}, квартира ${apartmentNumber}` }).waitFor()
    await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
    await page.getByLabel(/^Стоимость/).fill('5200000')
    const updatedProperty = await submitRecord(
      page, `/api/v1/properties/${property.id}/`, 'Сохранить изменения', 'PATCH',
    )
    assert.equal(updatedProperty.propertyCost, '5200000.00')
    assert.equal(updatedProperty.building, 'E2E-1')

    await openRoute(page, `complexes/${complex.id}`)
    await deleteDetailRecord(page, `/api/v1/complexes/${complex.id}/`, 409)
    await page.getByRole('alertdialog').getByRole('alert').waitFor()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Отмена' }).click()

    await openRoute(page, `properties/${property.id}`)
    await deleteDetailRecord(page, `/api/v1/properties/${property.id}/`)
    await page.getByRole('heading', { name: 'Объекты недвижимости', exact: true }).waitFor()
    await openRoute(page, `complexes/${complex.id}`)
    await deleteDetailRecord(page, `/api/v1/complexes/${complex.id}/`)
    await page.getByRole('heading', { name: 'Жилые комплексы', exact: true }).waitFor()
    await openRoute(page, `developers?q=${encodeURIComponent(developerName)}`)
    await page.getByText(developerName, { exact: true }).filter({ visible: true }).waitFor()
    await page.getByRole('button', { name: /Удалить/ }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Удалить', exact: true }).click()
    await page.waitForFunction((value) => !document.body.innerText.includes(value), developerName)
  })

  writeTest(`bank lifecycle preserves nested program conditions at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    const name = `E2E банк ${randomUUID().slice(0, 8)}`
    await openRoute(page, 'banks/new')
    await page.getByLabel(/^Название/).fill(name)
    await page.getByRole('button', { name: 'Добавить программу' }).click()
    await page.getByLabel(/^Ипотечная программа/).selectOption(String(fixtureManifest.mortgageProgramId))
    await page.getByLabel(/^Ставка/).fill('8.5')
    await page.getByLabel(/^Первый взнос/).fill('20')
    await page.getByLabel(/^Максимальный срок/).fill('30')
    const bank = await submitRecord(page, '/api/v1/banks/', 'Создать банк')
    trackCleanup(`/api/v1/banks/${bank.id}/`)
    assert.equal(bank.programs.length, 1)
    await page.getByRole('heading', { name, level: 1, exact: true }).waitFor()
    await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
    await page.getByLabel(/^Ставка/).fill('9.25')
    const updatedBank = await submitRecord(
      page, `/api/v1/banks/${bank.id}/`, 'Сохранить изменения', 'PATCH',
    )
    assert.equal(updatedBank.programs[0].interestRate, '9.25')
    assert.equal(updatedBank.programs[0].minimumInitialPaymentPercent, '20.00')
    await page.getByRole('heading', { name, level: 1, exact: true }).waitFor()
    await page.reload()
    await page.getByRole('heading', { name, level: 1, exact: true }).waitFor()
    await deleteDetailRecord(page, `/api/v1/banks/${bank.id}/`)
    await page.getByRole('heading', { name: 'Банки и программы', level: 1, exact: true }).waitFor()
  })
}
