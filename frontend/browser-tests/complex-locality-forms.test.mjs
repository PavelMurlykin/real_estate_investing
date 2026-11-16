import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createAuthenticatedPage, fixtureManifest, isolatedBaseUrl, isolatedWritesEnabled } from './isolated-helpers.mjs'

test('creates and edits a complex by locality without a legacy district', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 90000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  const base = (path) => new URL(path, isolatedBaseUrl).href
  const name = `E2E населённый пункт ${Date.now()}`
  await page.goto(base('/app/complexes/new'))
  await page.getByLabel('Название ЖК *', { exact: true }).fill(name)
  for (const [label, option] of [['Застройщик *', /^E2E застройщик \(E2E группа\)$/], ['Класс ЖК *', /E2E комфорт/], ['Тип недвижимости *', /E2E квартира/]]) {
    await page.getByRole('combobox', { name: label, exact: true }).click()
    await page.getByRole('option', { name: option }).click()
  }
  assert.equal(await page.getByRole('combobox', { name: 'Район *', exact: true }).count(), 0)
  await page.getByRole('combobox', { name: 'Населённый пункт *', exact: true }).fill('Пушкин')
  await page.getByRole('option', { name: /г\. Пушкин · Пушкинский район/ }).click()
  await page.getByLabel('Номер корпуса 1 *', { exact: true }).fill('1')
  const created = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/complexes/')
  await page.getByRole('button', { name: 'Создать ЖК', exact: true }).click()
  const response = await created
  assert.equal(response.status(), 201, await response.text())
  const data = await response.json()
  trackCleanup(`/api/v1/complexes/${data.id}/`)
  assert.equal(data.districtId, null)
  assert.equal(data.location.id, fixtureManifest.pushkinLocationId)
  await page.getByRole('heading', { name, exact: true }).waitFor()
  await page.getByRole('link', { name: 'Редактировать', exact: true }).click()
  const locality = page.getByRole('combobox', { name: 'Населённый пункт *', exact: true })
  await locality.waitFor()
  await page.waitForFunction((input) => input.value.includes('Пушкин'), await locality.elementHandle())
  assert.match(await locality.inputValue(), /Пушкин/)
  await locality.fill('Стрельна')
  await page.getByRole('option', { name: /п\. Стрельна · Петродворцовый район/ }).click()
  const updated = page.waitForResponse((reply) => reply.request().method() === 'PATCH' && new URL(reply.url()).pathname === `/api/v1/complexes/${data.id}/`)
  await page.getByRole('button', { name: 'Сохранить изменения', exact: true }).click()
  const saved = await updated
  assert.equal(saved.status(), 200, await saved.text())
  const final = await saved.json()
  assert.equal(final.districtId, null)
  assert.equal(final.location.id, fixtureManifest.strelnaLocationId)
  assert.deepEqual(final.buildings.map((row) => row.id), data.buildings.map((row) => row.id))
  await page.getByRole('heading', { name, exact: true }).waitFor()
  await page.reload()
  await page.getByRole('heading', { name, exact: true }).waitFor()
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true)
  }
  await page.goto(base('/app/properties/new'))
  for (const [label, option] of [['Застройщик *', /^E2E застройщик \(E2E группа\)$/], ['Жилой комплекс *', name], ['Корпус *', '1'], ['Планировка *', 'E2E планировка'], ['Отделка *', 'E2E отделка']]) {
    await page.getByRole('combobox', { name: label, exact: true }).click()
    await page.getByRole('option', { name: option, exact: true }).click()
  }
  for (const [label, value] of [['Номер квартиры *', '2'], ['Площадь, м² *', '45'], ['Этаж *', '2'], ['Стоимость, ₽ *', '5000000']]) {
    await page.getByLabel(label, { exact: true }).fill(value)
  }
  const propertyResponse = page.waitForResponse((reply) => reply.request().method() === 'POST' && new URL(reply.url()).pathname === '/api/v1/properties/')
  await page.getByRole('button', { name: 'Создать объект', exact: true }).click()
  const apartment = await propertyResponse
  assert.equal(apartment.status(), 201, await apartment.text())
  const property = await apartment.json()
  trackCleanup(`/api/v1/properties/${property.id}/`)
  assert.equal(property.districtId, null)
  assert.equal(property.city, 'Стрельна')
})
