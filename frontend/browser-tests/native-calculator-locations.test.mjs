import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

test('native mortgage and tranche selectors calculate in Pushkin and Strelna', {
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
  const create = async (path, data) => {
    const response = await request.post(url(path), { headers, data })
    assert.equal(response.status(), 201, await response.text())
    const result = await response.json()
    trackCleanup(`${path}${result.id}/`)
    return result
  }
  const choose = async (field, label) => {
    const input = page.locator(`#${field}_search`)
    await input.fill(label)
    const menu = page.locator(`#${await input.getAttribute('aria-controls')}`)
    await menu.locator('.searchable-select-option:visible').filter({ hasText: label }).first().click()
  }
  const template = await read(`/api/v1/properties/${fixtureManifest.propertyId}/`)
  const sourceProject = await read(`/api/v1/complexes/${template.realEstateComplexId}/`)
  const programPath = `/api/v1/mortgage-programs/${fixtureManifest.mortgageProgramId}/`
  const originalProgram = await read(programPath)
  const locality = await read(`/api/v1/location-catalogs/localities/${fixtureManifest.pushkinLocationId}/`)
  const financialRegion = (await read(`/mortgage/financial-region/?regionLocationId=${locality.regionId}`)).financialRegionId
  assert.ok(financialRegion)
  const changed = await request.patch(url(programPath), { headers, data: {
    isPreferential: true, creditLimit: '6000000.00',
    regionalCreditLimits: [{ regionId: financialRegion, creditLimit: '12000000.00', isActive: true }],
  } })
  assert.equal(changed.status(), 200, await changed.text())
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  try {
    for (const [name, identifier] of [
      ['Пушкин', fixtureManifest.pushkinLocationId], ['Стрельна', fixtureManifest.strelnaLocationId],
    ]) {
      const project = await create('/api/v1/complexes/', {
        name: `E2E калькулятор ${name} ${Date.now()}`, locationId: identifier,
        developerId: template.developerId, realEstateClassId: sourceProject.realEstateClassId,
        realEstateTypeId: sourceProject.realEstateTypeId, buildings: [{ number: 'CALC-1' }],
      })
      const apartment = await create('/api/v1/properties/', {
        buildingId: project.buildings[0].id, apartmentNumber: 'NC-1', area: '45.00', floor: 3,
        propertyCost: '5000000.00', layoutId: template.layoutId, decorationId: template.decorationId,
      })
      await page.goto(url(`/mortgage/?legacy=1&property_id=${apartment.id}`))
      assert.match(await page.locator('#id_OBJECT_LOCALITY_search').inputValue(), new RegExp(name))
      await page.locator('#clear-object-data-fields').click()
      await choose('id_OBJECT_LOCALITY', name)
      await choose('developer-select', template.developer)
      await choose('complex-select', project.name)
      await choose('id_building', 'CALC-1')
      await page.waitForFunction((id) => document.querySelector('#id_OBJECT_LOCALITY').value === String(id)
        && document.querySelector('[data-property-location-status]').textContent.includes('соответствует'), identifier)
      await page.locator('#id_OBJECT_APARTMENT_NUMBER').fill('NC-1')
      await page.waitForFunction((id) => document.querySelector('#id_PROPERTY').value === String(id), apartment.id)
      assert.equal(await page.locator('#property_cost_input').inputValue(), '5000000.00')
      await page.locator('#mortgage-bank-select').selectOption(String(fixtureManifest.bankId), { force: true })
      await page.locator('#mortgage-program-select').selectOption(String(fixtureManifest.mortgageProgramId), { force: true })
      await page.locator('#property_cost_input').fill('18000000')
      await page.locator('#initial_payment_percent').fill('20')
      await page.waitForFunction(() => document.querySelector('#mortgage-program-limit-options').textContent.replace(/\s/g, '').includes('лимит12000000'))
      await page.locator('#property_cost_input').fill('5000000')
      await page.locator('#id_INITIAL_PAYMENT_DATE').fill('2026-01-01')
      await page.locator('#mortgage_term_months').fill('240')
      await page.locator('#id_ANNUAL_RATE').fill('12')
      for (const mode of ['market', 'trench']) {
        const endpoint = mode === 'market' ? '/api/v1/mortgage/calculations/' : '/api/v1/mortgage/trench/calculations/'
        const before = new Set((await read(endpoint)).results.map((row) => row.id))
        if (mode === 'trench') await page.locator('#trench-mortgage-tab').click()
        for (let repetition = 0; repetition < 2; repetition += 1) {
          await Promise.all([
            page.waitForNavigation(), page.locator(`button[name="calculate"][value="${mode}"]`).click(),
          ])
          assert.equal(await page.locator('.invalid-feedback.d-block').count(), 0)
          assert.match(await page.locator('#id_OBJECT_LOCALITY_search').inputValue(), new RegExp(name))
        }
        const saved = (await read(endpoint)).results.filter((row) => !before.has(row.id))
        assert.equal(saved.length, 2)
        for (const row of saved) trackCleanup(`${endpoint}${row.id}/`)
      }
      for (const width of [1440, 360]) {
        await page.setViewportSize({ width, height: 1000 })
        const overflow = await page.evaluate(() => {
          const width = document.documentElement.clientWidth
          if (document.documentElement.scrollWidth <= width) return []
          return [...document.querySelectorAll('body *')].filter((element) => {
            const box = element.getBoundingClientRect()
            return box.right > width + 1 && box.width > 0 && getComputedStyle(element).position !== 'fixed'
              && !element.closest('.table-responsive')
          }).slice(0, 8).map((element) => `${element.tagName}.${element.className}: ${element.getBoundingClientRect().right}`)
        })
        assert.deepEqual(overflow, [])
      }
      await page.setViewportSize({ width: 1440, height: 1100 })
      const preserved = await read(`/api/v1/properties/${apartment.id}/`)
      assert.equal(preserved.propertyCost, apartment.propertyCost)
      assert.equal(preserved.buildingId, apartment.buildingId)
    }
    assert.deepEqual(errors, [])
  } finally {
    const restored = await request.patch(url(programPath), { headers, data: {
      isPreferential: originalProgram.isPreferential, creditLimit: originalProgram.creditLimit,
      regionalCreditLimits: originalProgram.regionalCreditLimits,
    } })
    assert.equal(restored.status(), 200)
  }
})
