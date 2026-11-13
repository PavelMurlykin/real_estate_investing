import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  createIsolatedPage, fixtureManifest, isolatedBaseUrl, isolatedWritesEnabled,
} from './isolated-helpers.mjs'

for (const width of [360, 1280]) {
  for (const mode of ['market', 'trench']) {
    test(mode + ' searches bank and mortgage program at ' + width + 'px', {
      skip: isolatedWritesEnabled ? false : 'requires isolated acceptance stack',
    }, async (context) => {
      const prefix = '/api/v1/mortgage/' + (mode === 'trench' ? 'trench/' : '')
      const page = await createIsolatedPage(context, { width, height: 1000 }, {
        allowedUnsafeRequests: ['POST ' + prefix + 'calculate/'],
      })
      const options = await page.request.get(isolatedBaseUrl + '/api/v1/mortgage/options/').then((response) => response.json())
      const bank = options.banks.find((entry) => entry.id === fixtureManifest.bankId)
      const program = options.programs.find((entry) => entry.bankId === bank.id && entry.programId === fixtureManifest.mortgageProgramId)
      assert.ok(program)
      await page.goto(isolatedBaseUrl + '/app/mortgage' + (mode === 'trench' ? '/trench' : ''))
      await page.getByRole('heading', { name: 'Ипотечный калькулятор', exact: true }).waitFor()
      const bankInput = page.getByRole('combobox', { name: 'Банк', exact: true })
      const programInput = page.getByRole('combobox', { name: 'Ипотечная программа', exact: true })
      assert.equal(await programInput.isDisabled(), true)
      const searchAndChoose = async (input, label, query, matches) => {
        await input.fill(query.toLocaleLowerCase('ru-RU'))
        const list = page.getByRole('listbox', { name: `Варианты: ${label}`, exact: true })
        await list.getByRole('option').filter({ hasText: matches }).first().waitFor()
        await page.waitForFunction((label) => {
          const list = [...document.querySelectorAll('[role=listbox]')]
            .find((element) => element.getAttribute('aria-label') === `Варианты: ${label}`)
          const bounds = list?.getBoundingClientRect()
          return bounds && bounds.top >= 0 && bounds.bottom <= innerHeight
        }, label)
        const labels = await list.getByRole('option').allTextContents()
        const index = labels.findIndex((value) => matches.test(value))
        assert.ok(index > 0)
        for (let number = 1; number < index; number += 1) await input.press('ArrowDown')
        await input.press('Enter')
      }
      const escapedBank = bank.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      await searchAndChoose(bankInput, 'Банк', bank.name, new RegExp('^' + escapedBank + '$'))
      assert.equal(await bankInput.inputValue(), bank.name)
      await searchAndChoose(programInput, 'Ипотечная программа', program.programName, /E2E ипотечная программа —/)
      await page.waitForFunction((expected) => {
        const input = [...document.querySelectorAll('input')].find((input) =>
          input.labels?.[0]?.textContent.trim() === 'Годовая ставка, %')
        return input && Number(input.value) === expected
      }, Number(program.interestRate))
      assert.equal(Number(await page.getByLabel('Годовая ставка, %', { exact: true }).first().inputValue()), Number(program.interestRate))
      assert.equal(Number(await page.getByLabel('Первоначальный взнос, %', { exact: true }).inputValue()), Number(program.minimumInitialPaymentPercent))
      const [response] = await Promise.all([
        page.waitForResponse((response) => new URL(response.url()).pathname === prefix + 'calculate/'),
        page.getByRole('button', { name: mode === 'market' ? 'Рассчитать ипотеку' : 'Рассчитать траншевую ипотеку', exact: true }).click(),
      ])
      assert.equal(response.status(), 200)
      assert.equal(Number(response.request().postDataJSON().annualRate), Number(program.interestRate))
      // The rendered result receives focus after the response is processed by React.
      // Wait for that transition before starting another dropdown interaction.
      await page.getByRole('heading', {
        name: mode === 'market' ? 'Параметры кредита' : 'Параметры траншевого кредита', exact: true,
      }).and(page.locator(':focus')).waitFor()
      await programInput.click()
      await page.getByRole('listbox', { name: 'Варианты: Ипотечная программа', exact: true })
        .getByRole('option', { name: 'Ручные параметры', exact: true }).click()
      assert.equal(await programInput.inputValue(), '')
      await bankInput.click()
      await page.getByRole('listbox', { name: 'Варианты: Банк', exact: true })
        .getByRole('option', { name: 'Без выбора', exact: true }).click()
      assert.equal(await programInput.isDisabled(), true)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    })
  }
}
