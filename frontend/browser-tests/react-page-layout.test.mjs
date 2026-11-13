import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { test } from 'node:test'

import {
  createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'
import { screenshot } from './helpers.mjs'
import { assertReactPageLayout } from './page-layout-helpers.mjs'
import { assertFormKeyboard } from './form-style-helpers.mjs'

for (const width of [360, 768, 1280]) {
  test(`React forms and cards have clear spacing and no Django links at ${width}px`, {
    skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack',
  }, async (context) => {
    const { page, trackCleanup } = await createAuthenticatedPage(context, 'moderator', { width, height: 900 })
    let phase = 'ready'
    let releaseLoading
    let loadingGate
    let dataRequests = new Set()
    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      if (request.method() === 'GET' && path !== '/api/v1/auth/session/' && !path.startsWith('/api/v1/catalog-options/')) {
        dataRequests.add(path)
        if (phase === 'loading') await loadingGate
        if (phase === 'error') return route.fulfill({ status: 503, json: { detail: 'Временный сбой.' } })
      }
      return route.fallback()
    })
    const csrfToken = await getCsrfToken(page.context())
    const createRecord = async (resource, data) => {
      const response = await page.request.post(isolatedBaseUrl + '/api/v1/' + resource + '/', {
        data, headers: { 'X-CSRFToken': csrfToken },
      })
      assert.equal(response.status(), 201, resource)
      const record = await response.json()
      trackCleanup(`/api/v1/${resource}/${record.id}/`)
      return record
    }
    const group = await createRecord('company-groups', { name: 'E2E layout ' + randomUUID() })
    const program = await createRecord('developer-mortgage-programs', {
      companyGroupId: group.id, bankId: fixtureManifest.bankId, mortgageProgramId: fixtureManifest.mortgageProgramId,
    })
    const customer = await createRecord('customers', { firstName: 'E2E layout ' + randomUUID() })
    const property = await page.request.get(isolatedBaseUrl + `/api/v1/properties/${fixtureManifest.propertyId}/`)
      .then((response) => response.json())
    const classes = await page.request.get(isolatedBaseUrl + '/api/v1/property-dictionaries/real-estate-classes/')
      .then((response) => response.json())
    assert.ok(classes.results.length)

    const openAndCheck = async (route, checkRecovery = false) => {
      dataRequests = new Set()
      const response = await page.goto(isolatedBaseUrl + '/app/' + route)
      assert.equal(response.status(), 200, route)
      await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor()
      assert.doesNotMatch(await page.getByRole('main').getByRole('heading', { level: 1 }).innerText(), /не найден|недоступ|недостаточно|не удалось/i, route)
      await page.waitForFunction(() => !document.querySelector('main .async-state--loading'))
      await assertReactPageLayout(page)
      await assertFormKeyboard(page)
      if (checkRecovery && dataRequests.size) {
        const title = await page.getByRole('main').getByRole('heading', { level: 1 }).innerText()
        phase = 'loading'
        loadingGate = new Promise((resolve) => { releaseLoading = resolve })
        await page.reload()
        await page.getByRole('main').locator('.async-state--loading').first().waitFor()
        await assertReactPageLayout(page)
        phase = 'error'
        releaseLoading()
        const error = page.getByRole('main').locator('.async-state--error').first()
        await error.waitFor()
        await assertReactPageLayout(page)
        phase = 'ready'
        await error.getByRole('button', { name: 'Повторить', exact: true }).focus()
        await page.keyboard.press('Enter')
        await page.getByRole('main').getByRole('heading', { level: 1, name: title, exact: true }).waitFor()
        await page.waitForFunction(() => {
          const active = document.activeElement
          return active === document.querySelector('main h1')
            || Boolean(active?.closest('main form') && active.matches('input, select, textarea, button, a[href]'))
        }).catch(async (error) => {
          const active = await page.evaluate(() => ({ tag: document.activeElement?.tagName, id: document.activeElement?.id }))
          throw new Error(route + ': focus after recovery ' + JSON.stringify(active), { cause: error })
        })
        await assertReactPageLayout(page)
      }
    }
    const routes = [
      'company-groups', 'company-groups/new', `company-groups/${group.id}/edit`,
      'developers', 'developers/new', `developers/${property.developerId}/edit`,
      'properties/new', `properties/${property.id}`, `properties/${property.id}/edit`,
      'complexes/new', `complexes/${fixtureManifest.complexId}`, `complexes/${fixtureManifest.complexId}/edit`,
      'banks/new', `banks/${fixtureManifest.bankId}`, `banks/${fixtureManifest.bankId}/edit`,
      'mortgage-programs/new', `mortgage-programs/${fixtureManifest.mortgageProgramId}`, `mortgage-programs/${fixtureManifest.mortgageProgramId}/edit`,
      'developer-programs/new', `developer-programs/${program.id}`, `developer-programs/${program.id}/edit`,
      'customers', 'customers/new', `customers/${customer.id}`, `customers/${customer.id}/edit`,
      'dictionaries/real-estate-types', 'dictionaries/real-estate-classes', 'dictionaries/apartment-layouts',
      'dictionaries/apartment-decorations', 'dictionaries/window-views', 'dictionaries/transport-accessibility-types',
      `dictionaries/real-estate-classes/${classes.results[0].id}/edit`,
      'profile', 'password/change', 'mortgage/calculations', 'mortgage/trench/calculations',
      `mortgage/calculations?customerId=${customer.id}`, `mortgage/trench/calculations?customerId=${customer.id}`,
    ]
    for (const route of routes) {
      await openAndCheck(route, true)
      if (['customers/new', 'properties/new', 'profile'].includes(route)) {
        await screenshot(page, 'react-' + route.replaceAll('/', '-') + '-' + width + '.png')
      }
    }
    for (const mode of ['market', 'trench']) {
      const path = 'mortgage/' + (mode === 'trench' ? 'trench/' : '')
      await openAndCheck(path + '?propertyId=' + fixtureManifest.propertyId)
      const calculation = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/v1/' + path + 'calculate/')
      await page.getByRole('button', { name: mode === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку', exact: true }).click()
      assert.equal((await calculation).status(), 200)
      const saving = page.waitForResponse((response) => response.request().method() === 'POST'
        && new URL(response.url()).pathname === '/api/v1/' + path + 'calculations/')
      await page.getByRole('button', { name: 'Сохранить расчёт', exact: true }).click()
      const savedResponse = await saving
      assert.equal(savedResponse.status(), 201)
      const saved = await savedResponse.json()
      trackCleanup('/api/v1/' + path + 'calculations/' + saved.id + '/')
      await openAndCheck(path + 'calculations/' + saved.id)
      await screenshot(page, 'react-' + mode + '-detail-' + width + '.png')
    }
  })
}
