import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createAuthenticatedPage, fixtureManifest, getCsrfToken, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

test('Location limit editor and both calculators use the same subject for Pushkin and Strelna', {
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
    const row = await response.json()
    trackCleanup(`${path}${row.id}/`)
    return row
  }
  const choose = async (field, query, option) => {
    await page.getByRole('combobox', { name: field, exact: true }).fill(query)
    await page.getByRole('option', { name: option }).click()
  }
  const programId = fixtureManifest.mortgageProgramId
  const programPath = `/api/v1/mortgage-programs/${programId}/`
  const original = await read(programPath)
  const template = await read(`/api/v1/properties/${fixtureManifest.propertyId}/`)
  const projectTemplate = await read(`/api/v1/complexes/${template.realEstateComplexId}/`)
  const options = await read('/api/v1/mortgage/options/')
  const bank = options.banks.find((item) => item.id === fixtureManifest.bankId)
  try {
    await page.goto(url(`/app/mortgage-programs/${programId}/edit`))
    await page.getByRole('checkbox', { name: /Льготная программа/ }).check()
    await page.locator('input[name="creditLimit"]').fill('6000000')
    await page.getByRole('button', { name: 'Добавить регион', exact: true }).click()
    await choose('Регион *', 'Санкт-Петербург', /Санкт-Петербург/)
    await page.getByLabel('Лимит, ₽ *', { exact: true }).fill('3000000')
    const saved = page.waitForResponse((response) => response.request().method() === 'PATCH'
      && new URL(response.url()).pathname === programPath)
    await page.getByRole('button', { name: 'Сохранить изменения', exact: true }).click()
    const saveResponse = await saved
    assert.equal(saveResponse.status(), 200)
    const sent = saveResponse.request().postDataJSON().regionalCreditLimits[0]
    assert.ok(sent.regionLocationId && !sent.regionId)
    const [limit] = (await read(`${programPath}?canonicalLocations=true`)).regionalCreditLimits
    assert.equal(limit.regionLocationId, sent.regionLocationId)
    assert.equal(limit.creditLimit, '3000000.00')
    assert.ok((await read(programPath)).regionalCreditLimits[0].regionId)

    for (const [town, locality] of [['Пушкин', fixtureManifest.pushkinLocationId], ['Стрельна', fixtureManifest.strelnaLocationId]]) {
      const project = await create('/api/v1/complexes/', {
        name: `E2E финансовый регион ${town}`, locationId: locality,
        developerId: template.developerId, realEstateClassId: projectTemplate.realEstateClassId,
        realEstateTypeId: projectTemplate.realEstateTypeId, buildings: [{ number: '1' }],
      })
      const apartment = await create('/api/v1/properties/', {
        buildingId: project.buildings[0].id, apartmentNumber: '1', area: '45.00', floor: 2,
        propertyCost: '5500000.00', layoutId: template.layoutId, decorationId: template.decorationId,
      })
      const customer = await create('/api/v1/customers/', {
        firstName: `E2E ${town}`, desiredLocalityId: locality, preferentialProgramIds: [programId],
      })
      const profile = await read(`/api/v1/customers/${customer.id}/`)
      assert.equal(profile.desiredFinancialRegionLocationId, limit.regionLocationId)
      assert.equal(profile.calculated.preferentialCreditLimit, '3000000.00')
      await page.goto(url(`/app/customers/${customer.id}`))
      await page.getByText('Регион лимита', { exact: true }).waitFor()
      for (const [path, action] of [['', 'Рассчитать ипотеку'], ['/trench', 'Рассчитать траншевую ипотеку']]) {
        await page.goto(url(`/app/mortgage${path}?propertyId=${apartment.id}`))
        await page.waitForFunction(() => Number(document.querySelector('input[name="propertyCost"]')?.value) === 5500000)
        for (const [label, name] of [['Банк', bank.name], ['Ипотечная программа', original.name]]) {
          const input = page.getByRole('combobox', { name: label, exact: true })
          await input.fill(name)
          await page.getByRole('listbox', { name: `Варианты: ${label}` })
            .getByRole('option').filter({ hasText: name }).waitFor()
          await input.press('Enter')
        }
        const notice = page.getByRole('heading', { name: 'Сумма кредита превышает лимит программы' }).locator('..')
        const regionalText = notice.getByText(/Лимит кредита: 3\s000\s000/)
        await regionalText.waitFor()
        const calculated = page.waitForResponse((response) => response.request().method() === 'POST'
          && new URL(response.url()).pathname === `/api/v1/mortgage${path}/calculate/`)
        await page.getByRole('button', { name: action, exact: true }).click()
        const result = await calculated
        assert.equal(result.status(), 200, await result.text())
        assert.ok(Number((await result.json()).summary.loanAmount) > Number(limit.creditLimit))
      }
    }
  } finally {
    const restored = await request.patch(url(programPath), { headers, data: {
      isPreferential: original.isPreferential, creditLimit: original.creditLimit,
      regionalCreditLimits: original.regionalCreditLimits,
    } })
    assert.equal(restored.status(), 200, await restored.text())
  }
})
