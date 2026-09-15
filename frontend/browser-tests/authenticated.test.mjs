import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { test } from 'node:test'

import {
  accountPassword,
  createAuthenticatedPage,
  fixtureManifest,
  getCsrfToken,
  isolatedBaseUrl,
  isolatedWritesEnabled,
} from './isolated-helpers.mjs'

const writeTest = (name, callback) => test(
  name,
  { skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack' },
  callback,
)

for (const width of [360, 1280]) {
  writeTest(`moderator completes company group CRUD at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'moderator', { width, height: 900 },
    )
    const name = `E2E группа ${randomUUID()}`
    await page.goto(new URL('/app/company-groups/new', isolatedBaseUrl).href)
    await page.getByLabel(/^Название/).fill(name)
    const createResponsePromise = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/company-groups/'
    ))
    await page.getByRole('button', { name: 'Сохранить' }).click()
    const created = await createResponsePromise.then((response) => response.json())
    trackCleanup(`/api/v1/company-groups/${created.id}/`)
    await page.getByText(name, { exact: true }).filter({ visible: true }).waitFor()

    const updatedName = `${name} изменена`
    await page.getByRole('link', { name: /Редактировать/ }).click()
    await page.getByLabel(/^Название/).fill(updatedName)
    await page.getByRole('button', { name: 'Сохранить' }).click()
    await page.getByText(updatedName, { exact: true }).filter({
      visible: true,
    }).waitFor()
    await page.getByRole('button', { name: /Удалить/ }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Удалить' }).click()
    await page.waitForFunction(
      (deletedName) => !document.body.innerText.includes(deletedName),
      updatedName,
    )
  })

  writeTest(`owner completes customer CRUD at ${width}px`, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(
      context, 'owner', { width, height: 900 },
    )
    const name = `E2E клиент ${randomUUID()}`
    await page.goto(new URL('/app/customers/new', isolatedBaseUrl).href)
    await page.getByLabel(/^Имя/).fill(name)
    const createResponsePromise = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/customers/'
    ))
    await page.getByRole('button', { name: 'Сохранить клиента' }).click()
    const created = await createResponsePromise.then((response) => response.json())
    trackCleanup(`/api/v1/customers/${created.id}/`)
    await page.getByRole('heading', { name, exact: true }).waitFor()
    await page.getByRole('link', { name: 'Редактировать' }).click()
    await page.getByLabel(/^Фамилия/).fill('Проверен')
    await page.getByRole('button', { name: 'Сохранить клиента' }).click()
    await page.getByRole('heading', { name: `${name} Проверен` }).waitFor()
    await page.getByRole('button', { name: 'Удалить', exact: true }).click()
    await page.getByRole('alertdialog').getByRole('button', {
      name: 'Удалить клиента',
    }).click()
    await page.getByRole('heading', { name: 'Клиенты' }).waitFor()
  })
}

writeTest('owner saves a calculation and downloads both exports', async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(
    context, 'owner', { width: 1280, height: 900 },
  )
  await page.goto(new URL(
    `/app/mortgage?propertyId=${fixtureManifest.propertyId}`,
    isolatedBaseUrl,
  ).href)
  await page.getByLabel('Дата первого взноса').fill('2026-10-01')
  await page.getByLabel('Срок ипотеки, месяцев').fill('12')
  await page.getByRole('button', { name: 'Рассчитать ипотеку' }).click()
  await page.getByRole('heading', { name: 'Сохранить этот сценарий' }).waitFor()
  const saveResponsePromise = page.waitForResponse((response) => (
    response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/mortgage/calculations/'
  ))
  await page.getByRole('button', { name: 'Сохранить расчёт' }).click()
  const saved = await saveResponsePromise.then((response) => response.json())
  trackCleanup(`/api/v1/mortgage/calculations/${saved.id}/`)
  await page.getByRole('link', { name: 'Открыть сохранённый расчёт' }).click()
  await page.getByRole('heading', { name: /Расчёт от/ }).waitFor()
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
    name: 'Удалить расчёт',
  }).click()
  await page.getByRole('heading', { name: 'История расчётов' }).waitFor()
})

writeTest('regular owner is denied catalog writes and other private data', async (context) => {
  const { page } = await createAuthenticatedPage(
    context, 'owner', { width: 360, height: 900 },
  )
  await page.goto(new URL('/app/company-groups/new', isolatedBaseUrl).href)
  await page.getByRole('heading', { name: 'Недостаточно прав' }).waitFor()
  const csrfToken = await getCsrfToken(page.context())
  const status = await page.evaluate(async ({ csrfTokenValue }) => {
    const response = await fetch('/api/v1/company-groups/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfTokenValue },
      body: JSON.stringify({ name: 'E2E запрещённая группа' }),
    })
    return response.status
  }, { csrfTokenValue: csrfToken })
  assert.equal(status, 403)
  await page.goto(new URL(
    `/app/customers/${fixtureManifest.otherCustomerId}`,
    isolatedBaseUrl,
  ).href)
  await page.getByRole('heading', {
    name: 'Клиент не найден или недоступен',
  }).waitFor()
})

writeTest('unsafe request without CSRF token is rejected', async (context) => {
  const { page } = await createAuthenticatedPage(
    context, 'owner', { width: 1280, height: 900 },
  )
  const status = await page.evaluate(async () => {
    const response = await fetch('/api/v1/customers/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ firstName: 'E2E CSRF rejection' }),
    })
    return response.status
  })
  assert.equal(status, 403)
})

writeTest('logout clears the Django session', async (context) => {
  const { page } = await createAuthenticatedPage(
    context, 'owner', { width: 1280, height: 900 },
  )
  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.getByRole('link', { name: 'Войти', exact: true }).last().waitFor()
  const session = await page.context().request.get(
    new URL('/api/v1/auth/session/', isolatedBaseUrl).href,
  ).then((response) => response.json())
  assert.equal(session.isAuthenticated, false)
  assert.equal(session.user, null)
  assert.notEqual(accountPassword, '')
})
