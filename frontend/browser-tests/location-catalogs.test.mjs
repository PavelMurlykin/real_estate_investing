import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

test('manages canonical dictionaries in React and Django while preserving Pushkin and Strelna identities', {
  skip: isolatedWritesEnabled ? false : 'requires isolated stack', timeout: 180000,
}, async (context) => {
  const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width: 1440, height: 1100 })
  const request = page.context().request
  const url = (path) => new URL(path, isolatedBaseUrl).href
  const headers = { 'X-CSRFToken': await getCsrfToken(page.context()) }
  const read = async (path) => {
    const response = await request.get(url(path))
    assert.equal(response.status(), 200, await response.text())
    return response.json()
  }
  const snapshots = []
  const projectTemplate = await read(`/api/v1/complexes/${fixtureManifest.complexId}/`)
  for (const id of [fixtureManifest.pushkinLocationId, fixtureManifest.strelnaLocationId]) {
    const location = await read(`/api/v1/location-catalogs/localities/${id}/`)
    const created = await request.post(url('/api/v1/complexes/'), { headers, data: {
      name: `E2E справочник ${location.name} ${Date.now()}`, locationId: id,
      developerId: projectTemplate.developerId, realEstateClassId: projectTemplate.realEstateClassId,
      realEstateTypeId: projectTemplate.realEstateTypeId, buildings: [{ number: '1' }],
    } })
    assert.equal(created.status(), 201, await created.text())
    const project = await created.json()
    trackCleanup(`/api/v1/complexes/${project.id}/`)
    const bindings = await read(`/api/v1/complexes/${project.id}/locations/`)
    snapshots.push({ location, project, bindings })
  }
  try {
    const [pushkin, strelna] = snapshots
    await page.goto(url('/app/locations/localities?q=' + encodeURIComponent('Пушкин')))
    await page.getByRole('table', { name: 'Населённые пункты', exact: true }).getByText('Пушкинский район', { exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'Обновить данные' }).count(), 0)
    await page.getByRole('link', { name: 'Изменить: Пушкин', exact: true }).click()
    const editor = page.getByRole('complementary', { name: 'Редактирование записи' })
    await editor.getByLabel('Название *', { exact: true }).fill('Пушкин E2E')
    const renamed = page.waitForResponse((response) => response.request().method() === 'PATCH' && new URL(response.url()).pathname === `/api/v1/location-catalogs/localities/${pushkin.location.id}/`)
    await editor.getByRole('button', { name: 'Сохранить', exact: true }).click()
    assert.equal((await renamed).status(), 200)
    const detail = await read(`/api/v1/location-catalogs/localities/${pushkin.location.id}/`)
    assert.equal(detail.name, 'Пушкин E2E')
    assert.deepEqual(detail.identifiers, pushkin.location.identifiers)
    assert.deepEqual((await read(`/api/v1/complexes/${pushkin.project.id}/locations/`)).locations.map(({ id }) => id), pushkin.bindings.locations.map(({ id }) => id))

    await page.goto(url('/locations/?model=locality&legacy=1&q=' + encodeURIComponent('Стрельна')))
    await page.getByRole('link', { name: 'Изменить: Стрельна', exact: true }).click()
    await page.getByLabel('Название:', { exact: true }).fill('Стрельна E2E')
    const nativeSaved = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/locations/')
    await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
    assert.equal((await nativeSaved).status(), 302)
    const nativeDetail = await read(`/api/v1/location-catalogs/localities/${strelna.location.id}/`)
    assert.equal(nativeDetail.name, 'Стрельна E2E')
    assert.deepEqual(nativeDetail.identifiers, strelna.location.identifiers)
    assert.deepEqual((await read(`/api/v1/complexes/${strelna.project.id}/locations/`)).locations.map(({ id }) => id), strelna.bindings.locations.map(({ id }) => id))
    assert.equal((await request.delete(url(`/api/v1/location-catalogs/localities/${strelna.location.id}/`), { headers })).status(), 409)

    const createdRows = []
    for (const [key, name, type] of [
      ['regions', `E2E субъект ${Date.now()}`, 'Регион'],
      ['districts', `E2E район ${Date.now()}`, 'Административный район'],
      ['localities', `E2E посёлок ${Date.now()}`, 'Поселок'],
    ]) {
      await page.goto(url(`/app/locations/${key}`))
      const form = page.getByRole('complementary', { name: 'Добавление записи' })
      await form.getByLabel('Название *', { exact: true }).fill(name)
      await form.getByRole('combobox', { name: 'Тип *', exact: true }).fill(type)
      await form.getByRole('option', { name: type, exact: true }).first().click()
      if (createdRows.length) {
        const parent = createdRows.at(-1)
        await form.getByRole('combobox', { name: 'Родительская территория *', exact: true }).fill(parent.name)
        await form.getByRole('option', { name: new RegExp(parent.name) }).click()
      }
      const pending = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/v1/location-catalogs/${key}/`)
      await form.getByRole('button', { name: 'Сохранить', exact: true }).click()
      const response = await pending
      assert.equal(response.status(), 201, await response.text())
      const row = await response.json()
      trackCleanup(`/api/v1/location-catalogs/${key}/${row.id}/`)
      createdRows.push(row)
      assert.equal(row.parentId, createdRows.length > 1 ? createdRows.at(-2).id : null)
    }
    const village = createdRows.at(-1)
    await page.goto(url('/app/locations/localities?q=' + encodeURIComponent(village.name)))
    await page.getByRole('button', { name: `Удалить: ${village.name}`, exact: true }).click()
    const removed = page.waitForResponse((response) => response.request().method() === 'DELETE' && new URL(response.url()).pathname === `/api/v1/location-catalogs/localities/${village.id}/`)
    await page.getByRole('alertdialog').getByRole('button', { name: 'Удалить', exact: true }).click()
    assert.equal((await removed).status(), 204)
    for (const width of [1440, 360]) {
      await page.setViewportSize({ width, height: 1000 })
      for (const key of ['regions', 'localities', 'districts']) {
        await page.goto(url(`/app/locations/${key}`))
        await page.getByRole('table').waitFor()
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
      }
    }
    const { page: other } = await createAuthenticatedPage(context, 'other', { width: 1280, height: 900 })
    await other.goto(url('/app/locations/localities?q=' + encodeURIComponent('Пушкин')))
    await other.getByRole('table').waitFor()
    assert.equal(await other.getByRole('button', { name: 'Сохранить', exact: true }).count(), 0)
    assert.equal((await other.request.patch(url(`/api/v1/location-catalogs/localities/${pushkin.location.id}/`), {
      headers: { 'X-CSRFToken': await getCsrfToken(other.context()) }, data: { name: 'Запрещено' },
    })).status(), 403)
  } finally {
    for (const { location } of snapshots) {
      const response = await request.patch(url(`/api/v1/location-catalogs/localities/${location.id}/`), {
        headers, data: { name: location.name, isActive: location.isActive },
      })
      assert.equal(response.status(), 200, await response.text())
    }
  }
})
