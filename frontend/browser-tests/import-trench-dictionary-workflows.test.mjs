import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { fileURLToPath } from 'node:url'
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

async function assertNoPageOverflow(page) {
  assert.equal(await page.evaluate(() => (
    document.documentElement.scrollWidth <= document.documentElement.clientWidth
  )), true, 'Page has horizontal overflow')
}

async function saveDictionaryEntry(page, dictionaryKey, name, identifier = null) {
  const path = identifier
    ? `/api/v1/property-dictionaries/${dictionaryKey}/${identifier}/`
    : `/api/v1/property-dictionaries/${dictionaryKey}/`
  const method = identifier ? 'PATCH' : 'POST'
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === method
    && new URL(response.url()).pathname === path
  ))
  await page.getByLabel('Название *', { exact: true }).fill(name)
  if (dictionaryKey === 'real-estate-classes') {
    await page.getByLabel('Коэффициент *', { exact: true }).fill('1.25')
  }
  await page.getByLabel('Описание', { exact: true }).fill('E2E описание')
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  const response = await responsePromise
  assert.equal(response.status(), identifier ? 200 : 201)
  return response.json()
}

const dictionaryKeys = [
  'real-estate-types',
  'real-estate-classes',
  'apartment-layouts',
  'apartment-decorations',
  'window-views',
  'transport-accessibility-types',
]

for (const width of [360, 1280]) {
  writeTest(`all property dictionaries complete CRUD at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    for (const dictionaryKey of dictionaryKeys) {
      const name = `E2E ${dictionaryKey} ${randomUUID().slice(0, 6)}`
      await openRoute(page, `dictionaries/${dictionaryKey}`)
      const created = await saveDictionaryEntry(page, dictionaryKey, name)
      trackCleanup(`/api/v1/property-dictionaries/${dictionaryKey}/${created.id}/`)
      assert.equal(created.name, name)
      await openRoute(page, `dictionaries/${dictionaryKey}/${created.id}/edit`)
      const updatedName = `${name} изменён`
      const updated = await saveDictionaryEntry(
        page, dictionaryKey, updatedName, created.id,
      )
      assert.equal(updated.description, 'E2E описание')
      await assertNoPageOverflow(page)

      await openRoute(page, `dictionaries/${dictionaryKey}?q=${encodeURIComponent(updatedName)}`)
      const deletePath = `/api/v1/property-dictionaries/${dictionaryKey}/${created.id}/`
      const responsePromise = page.waitForResponse((response) => (
        response.request().method() === 'DELETE'
        && new URL(response.url()).pathname === deletePath
      ))
      await page.getByRole('button', { name: `Удалить: ${updatedName}` }).click()
      await page.getByRole('alertdialog').getByRole('button', {
        name: 'Удалить', exact: true,
      }).click()
      assert.equal((await responsePromise).status(), 204)
      await page.waitForFunction(
        (deletedName) => !document.body.innerText.includes(deletedName),
        updatedName,
      )
    }
  })

  writeTest(`owner saves and exports a trench calculation at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'owner', { width, height: 900 },
    )
    await openRoute(page, `mortgage/trench?propertyId=${fixtureManifest.propertyId}`)
    await page.getByLabel('Дата первоначального взноса').fill('2026-10-01')
    await page.getByLabel('Срок ипотеки, месяцев').fill('24')
    await page.getByLabel('Годовая ставка, %').first().fill('7.5')
    await page.getByLabel('Количество траншей').selectOption('2')
    await page.getByLabel('Дата транша').nth(0).fill('2026-10-01')
    await page.getByLabel('Дата транша').nth(1).fill('2027-01-15')
    await page.getByLabel('Сумма транша, %').first().fill('40')
    await page.getByLabel('Годовая ставка, %').nth(1).fill('2')
    await page.getByLabel('Годовая ставка, %').nth(2).fill('7.5')
    await assertNoPageOverflow(page)
    const calculationResponsePromise = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/mortgage/trench/calculate/'
    ))
    await page.getByRole('button', { name: 'Рассчитать траншевую ипотеку' }).click()
    assert.equal((await calculationResponsePromise).status(), 200)
    await page.getByRole('heading', { name: 'Сохранить этот сценарий' }).waitFor()

    const saveResponsePromise = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/mortgage/trench/calculations/'
    ))
    await page.getByRole('button', { name: 'Сохранить расчёт' }).click()
    const saved = await saveResponsePromise.then((response) => response.json())
    trackCleanup(`/api/v1/mortgage/trench/calculations/${saved.id}/`)
    await page.getByRole('link', { name: 'Открыть сохранённый расчёт' }).click()
    await page.getByRole('heading', { name: /Траншевый расчёт от/ }).waitFor()
    for (const [label, extension] of [['Excel', '.xlsx'], ['Word', '.docx']]) {
      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.getByRole('link', { name: label, exact: true }).click(),
      ])
      assert.ok(download.suggestedFilename().endsWith(extension))
      assert.equal(await download.failure(), null)
    }
    await page.getByRole('button', { name: 'Удалить', exact: true }).click()
    await page.getByRole('alertdialog').getByRole('button', {
      name: 'Удалить расчёт', exact: true,
    }).click()
    await page.getByRole('heading', { name: 'История траншевой ипотеки' }).waitFor()
  })
}

writeTest('developer program XLSX import is idempotent and rejects invalid workbooks', async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(
    context, 'moderator', { width: 1280, height: 900 },
  )
  const workbookPath = fileURLToPath(new URL(
    '../../browser_acceptance/fixtures/developer-programs.xlsx', import.meta.url,
  ))
  await openRoute(page, 'developer-programs')
  await page.getByRole('button', { name: 'Импортировать' }).click()
  await page.getByText('Выберите XLSX-файл для импорта.', { exact: true }).waitFor()

  for (const expectedMetric of ['Создано1', 'Без изменений1']) {
    await page.getByLabel('Файл XLSX').setInputFiles(workbookPath)
    const responsePromise = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/developer-mortgage-programs/import/'
    ))
    await page.getByRole('button', { name: 'Импортировать' }).click()
    assert.equal((await responsePromise).status(), 200)
    await page.getByRole('status').filter({ hasText: expectedMetric }).waitFor()
  }

  const listResponse = await page.context().request.get(new URL(
    `/api/v1/developer-mortgage-programs/?companyGroupId=${fixtureManifest.companyGroupId}`,
    isolatedBaseUrl,
  ).href)
  assert.equal(listResponse.status(), 200)
  const programs = (await listResponse.json()).results
  const imported = programs.find((program) => program.interestRate === '7.77')
  assert.ok(imported?.id)
  trackCleanup(`/api/v1/developer-mortgage-programs/${imported.id}/`)

  await page.getByLabel('Файл XLSX').setInputFiles({
    name: 'invalid.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('not an xlsx workbook'),
  })
  await page.getByRole('button', { name: 'Импортировать' }).click()
  await page.getByRole('alert').filter({ hasText: 'Не удалось прочитать XLSX-файл.' }).waitFor()
})
