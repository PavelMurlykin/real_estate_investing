import assert from 'node:assert/strict'
import { lookup } from 'node:dns/promises'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { after, before } from 'node:test'
import { chromium } from 'playwright-core'

export const baseUrl = process.env.BROWSER_TEST_BASE_URL ?? 'http://127.0.0.1:18080'
const screenshotDirectory = process.env.BROWSER_TEST_SCREENSHOTS
let browser

before(async () => {
  const argumentsList = []
  if (process.env.BROWSER_TEST_CONNECT_HOST) {
    const { address } = await lookup(process.env.BROWSER_TEST_CONNECT_HOST)
    argumentsList.push(`--host-resolver-rules=MAP ${new URL(baseUrl).hostname} ${address}`)
  }
  browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || undefined,
    headless: true,
    args: argumentsList,
  })
  if (screenshotDirectory) await mkdir(screenshotDirectory, { recursive: true })
})

after(async () => {
  await browser?.close()
})

export async function createPage(testContext, viewport) {
  const context = await browser.newContext({ viewport })
  const unexpectedWrites = []
  // These acceptance tests must never create or change application records.
  await context.route('**/api/**', async (route) => {
    const request = route.request()
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      unexpectedWrites.push(`${request.method()} ${new URL(request.url()).pathname}`)
      await route.abort('blockedbyclient')
      return
    }
    await route.continue()
  })
  testContext.after(async () => {
    await context.close()
    assert.deepEqual(unexpectedWrites, [], 'Read-only acceptance attempted an API write')
  })
  const page = await context.newPage()
  page.setDefaultTimeout(10000)
  return page
}

export async function openPage(testContext, viewport, route = '/app/', heading) {
  const page = await createPage(testContext, viewport)
  const response = await page.goto(new URL(route, baseUrl).href)
  assert.equal(response?.status(), 200, `Direct route failed: ${route}`)
  await page.getByRole('main').getByRole('heading', heading
    ? { name: heading, exact: true }
    : { level: 1 }).waitFor()
  return page
}

export async function screenshot(page, name) {
  if (screenshotDirectory) {
    await page.screenshot({ path: path.join(screenshotDirectory, name) })
  }
}
