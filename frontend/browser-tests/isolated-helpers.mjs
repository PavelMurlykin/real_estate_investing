import assert from 'node:assert/strict'
import { lookup } from 'node:dns/promises'
import { after, before } from 'node:test'
import { chromium } from 'playwright-core'

const expectedDatabaseName = 'react_browser_acceptance'
const allowedWritePathPatterns = [
  /^\/api\/v1\/auth\/(?:login|logout)\/$/,
  /^\/api\/v1\/company-groups\/(?:\d+\/)?$/,
  /^\/api\/v1\/customers\/(?:\d+\/)?$/,
  /^\/api\/v1\/(?:properties|developers|complexes|banks)\/(?:\d+\/)?$/,
  /^\/api\/v1\/(?:mortgage-programs|developer-mortgage-programs)\/(?:\d+\/)?$/,
  /^\/api\/v1\/location-dictionaries\/(?:regions|cities|districts|metro)\/(?:\d+\/)?$/,
  /^\/api\/v1\/property-dictionaries\/(?:real-estate-types|real-estate-classes|apartment-layouts|apartment-decorations|window-views|transport-accessibility-types)\/(?:\d+\/)?$/,
  /^\/api\/v1\/developer-mortgage-programs\/import\/$/,
  /^\/api\/v1\/mortgage\/calculate\/$/,
  /^\/api\/v1\/mortgage\/calculations\/(?:\d+\/)?$/,
  /^\/api\/v1\/mortgage\/trench\/calculate\/$/,
  /^\/api\/v1\/mortgage\/trench\/calculations\/(?:\d+\/)?$/,
]

export const isolatedWritesEnabled = (
  process.env.BROWSER_TEST_ALLOW_WRITES === 'isolated'
)
export const isolatedBaseUrl = process.env.BROWSER_TEST_BASE_URL ?? ''
export const accountPassword = process.env.BROWSER_TEST_ACCOUNT_PASSWORD ?? ''
export const fixtureManifest = isolatedWritesEnabled
  ? validateIsolationConfiguration()
  : null

let browser

function validateIsolationConfiguration() {
  const url = new URL(isolatedBaseUrl)
  assert.ok(
    ['127.0.0.1', 'localhost'].includes(url.hostname) && url.port === '18081',
    'Write-enabled tests require the loopback-only acceptance port 18081',
  )
  assert.ok(accountPassword.length >= 24, 'Generated account password is missing')
  const manifest = JSON.parse(process.env.BROWSER_TEST_FIXTURES ?? '{}')
  assert.equal(manifest.isolated, true)
  assert.equal(manifest.databaseName, expectedDatabaseName)
  assert.ok(Number.isInteger(manifest.propertyId))
  assert.ok(Number.isInteger(manifest.otherCustomerId))
  for (const key of ['mortgageProgramId', 'companyGroupId', 'bankId', 'complexId', 'metroLineId']) {
    assert.ok(Number.isInteger(manifest[key]) && manifest[key] > 0, `Missing fixture: ${key}`)
  }
  for (const role of ['moderator', 'owner', 'other']) {
    assert.match(manifest.accounts?.[role]?.email ?? '', /@react-browser\.invalid$/)
  }
  return manifest
}

before(async () => {
  if (!isolatedWritesEnabled) return
  const argumentsList = []
  if (process.env.BROWSER_TEST_CONNECT_HOST) {
    const { address } = await lookup(process.env.BROWSER_TEST_CONNECT_HOST)
    argumentsList.push(
      `--host-resolver-rules=MAP ${new URL(isolatedBaseUrl).hostname} ${address}`,
    )
  }
  browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || undefined,
    headless: true,
    args: argumentsList,
  })
})

after(async () => {
  await browser?.close()
})

export async function createAuthenticatedPage(testContext, role, viewport) {
  assert.ok(browser, 'Isolated Chromium was not started')
  const context = await browser.newContext({ viewport, acceptDownloads: true })
  const observedWrites = []
  const unexpectedWrites = []
  const cleanupRequests = []
  await context.route('**/*', async (route) => {
    const request = route.request()
    const requestUrl = new URL(request.url())
    if (requestUrl.origin !== new URL(isolatedBaseUrl).origin) {
      await route.abort('blockedbyclient')
      return
    }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      const write = `${request.method()} ${requestUrl.pathname}`
      observedWrites.push(write)
      if (!allowedWritePathPatterns.some((pattern) => pattern.test(requestUrl.pathname))) {
        unexpectedWrites.push(write)
        await route.abort('blockedbyclient')
        return
      }
    }
    await route.continue()
  })
  testContext.after(async () => {
    const csrfToken = await getCsrfToken(context)
    for (const path of cleanupRequests.reverse()) {
      const response = await context.request.delete(
        new URL(path, isolatedBaseUrl).href,
        { headers: { 'X-CSRFToken': csrfToken } },
      )
      assert.ok([204, 404].includes(response.status()), `Cleanup failed: ${path}`)
    }
    await context.close()
    assert.deepEqual(unexpectedWrites, [], 'Unexpected isolated API writes')
    assert.ok(observedWrites.length > 0, 'Authenticated scenario made no writes')
  })

  const page = await context.newPage()
  page.setDefaultTimeout(12000)
  await page.goto(new URL('/app/login', isolatedBaseUrl).href)
  await page.getByLabel('Email или телефон').fill(fixtureManifest.accounts[role].email)
  await page.getByLabel('Пароль').fill(accountPassword)
  const loginResponsePromise = page.waitForResponse((response) => (
    response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/auth/login/'
  ))
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  const loginPayload = await loginResponsePromise.then((response) => {
    assert.equal(response.status(), 200, 'React login failed')
    return response.json()
  })
  assert.equal(
    loginPayload.user?.email,
    fixtureManifest.accounts[role].email,
  )

  return {
    page,
    trackCleanup(path) {
      assert.match(
        path,
        /^\/api\/v1\/(?:company-groups|customers|properties|developers|complexes|banks|mortgage-programs|developer-mortgage-programs|mortgage\/calculations|mortgage\/trench\/calculations|location-dictionaries\/(?:regions|cities|districts|metro)|property-dictionaries\/(?:real-estate-types|real-estate-classes|apartment-layouts|apartment-decorations|window-views|transport-accessibility-types))\/[1-9]\d*\/$/,
        'Cleanup must target an individual synthetic record on the isolated API',
      )
      cleanupRequests.push(path)
    },
  }
}

export async function getCsrfToken(context) {
  const cookie = (await context.cookies()).find(({ name }) => name === 'csrftoken')
  assert.ok(cookie?.value, 'Django CSRF cookie is missing')
  return cookie.value
}
