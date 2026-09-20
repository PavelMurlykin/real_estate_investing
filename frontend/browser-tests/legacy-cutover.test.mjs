import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  createAuthenticatedPage,
  createIsolatedPage,
  fixtureManifest,
  isolatedBaseUrl,
  isolatedWritesEnabled,
} from './isolated-helpers.mjs'

const cutoverTest = (name, callback) => test(
  name,
  { skip: isolatedWritesEnabled ? false : 'requires isolated cutover stack' },
  callback,
)

const legacyPublicPages = [
  ['/', '/app/', '', 'Инвестиции в недвижимость — в единой системе'],
  ['/property/', '/app/properties/', '', 'Объекты недвижимости'],
  [
    '/property/dictionaries/?model=window_view&page=1',
    '/app/dictionaries/window-views/',
    '?page=1',
    'Справочники объектов',
  ],
  ['/locations/?model=city', '/app/locations/cities/', '', 'Локации'],
  [
    '/bank/?model=mortgage_program',
    '/app/mortgage-programs/',
    '',
    'Ипотечные программы',
  ],
  ['/mortgage/', '/app/mortgage/', '', 'Ипотечный калькулятор'],
  ['/users/register/', '/app/register/', '', 'Регистрация'],
]

for (const width of [360, 1280]) {
  cutoverTest(
    `legacy public pages enter React through temporary redirects at ${width}px`,
    async (context) => {
      const page = await createIsolatedPage(context, { width, height: 900 })
      const pageErrors = []
      page.on('pageerror', (error) => pageErrors.push(error.message))

      for (const [legacyRoute, expectedPath, expectedSearch, heading] of (
        legacyPublicPages
      )) {
        const response = await page.goto(
          new URL(legacyRoute, isolatedBaseUrl).href,
        )
        assert.equal(response?.status(), 200)
        assert.ok(response?.request().redirectedFrom())
        const finalUrl = new URL(page.url())
        assert.equal(finalUrl.pathname, expectedPath)
        assert.equal(finalUrl.search, expectedSearch)
        await page.getByRole('main').getByRole('heading', {
          name: heading,
          exact: true,
        }).waitFor()
        assert.equal(
          await page.evaluate(() => (
            document.documentElement.scrollWidth <= window.innerWidth
          )),
          true,
        )
      }

      assert.deepEqual(pageErrors, [])
    },
  )
}

cutoverTest(
  'legacy authentication and private pages stay inside the React application',
  async (context) => {
    const page = await createIsolatedPage(context, { width: 1280, height: 900 })
    await page.goto(new URL(
      '/users/login/?next=%2Fapp%2Fcustomers',
      isolatedBaseUrl,
    ).href)
    await page.getByRole('heading', { name: 'Вход', exact: true }).waitFor()
    let finalUrl = new URL(page.url())
    assert.equal(finalUrl.pathname, '/app/login/')
    assert.equal(finalUrl.searchParams.get('next'), '/app/customers')

    await page.goto(new URL('/customers/', isolatedBaseUrl).href)
    await page.getByRole('heading', {
      name: 'Войдите, чтобы открыть список клиентов',
      exact: true,
    }).waitFor()
    finalUrl = new URL(page.url())
    assert.equal(finalUrl.pathname, '/app/customers/')

    await page.goto(new URL('/users/profile/edit/', isolatedBaseUrl).href)
    await page.getByRole('heading', { name: 'Вход', exact: true }).waitFor()
    finalUrl = new URL(page.url())
    assert.match(finalUrl.pathname, /^\/app\/login\/?$/)
    assert.equal(finalUrl.searchParams.get('next'), '/app/profile')
  },
)

cutoverTest(
  'legacy catalog edit opens the matching authenticated React form',
  async (context) => {
    const { page } = await createAuthenticatedPage(
      context,
      'moderator',
      { width: 1280, height: 900 },
    )
    const legacyRoute = (
      `/bank/?model=mortgage_program&edit=${fixtureManifest.mortgageProgramId}`
      + '&page=2'
    )
    await page.goto(new URL(legacyRoute, isolatedBaseUrl).href)
    await page.getByRole('heading', {
      name: 'Редактирование ипотечной программы',
      exact: true,
    }).waitFor()
    const finalUrl = new URL(page.url())
    assert.equal(
      finalUrl.pathname,
      `/app/mortgage-programs/${fixtureManifest.mortgageProgramId}/edit/`,
    )
    assert.equal(finalUrl.search, '?page=2')
  },
)

cutoverTest(
  'cutover leaves versioned APIs and unsafe legacy requests untouched',
  async (context) => {
    const page = await createIsolatedPage(
      context,
      { width: 1280, height: 900 },
      { allowedUnsafeRequests: ['POST /'] },
    )
    await page.goto(new URL('/app/', isolatedBaseUrl).href)

    const results = await page.evaluate(async () => {
      const apiResponse = await fetch('/api/v1/auth/session/', {
        redirect: 'manual',
      })
      const unsafeResponse = await fetch('/', {
        method: 'POST',
        redirect: 'manual',
      })
      return {
        apiStatus: apiResponse.status,
        apiPath: new URL(apiResponse.url).pathname,
        apiRedirected: apiResponse.redirected,
        unsafeStatus: unsafeResponse.status,
        unsafeRedirected: unsafeResponse.redirected,
      }
    })

    assert.equal(results.apiStatus, 200)
    assert.equal(results.apiPath, '/api/v1/auth/session/')
    assert.equal(results.apiRedirected, false)
    assert.equal(results.unsafeStatus, 403)
    assert.equal(results.unsafeRedirected, false)
  },
)
