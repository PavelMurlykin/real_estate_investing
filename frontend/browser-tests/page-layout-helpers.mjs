import assert from 'node:assert/strict'
import { assertFormStyles } from './form-style-helpers.mjs'
import { assertTableStyles } from './table-style-helpers.mjs'
import { assertDetailStyles } from './detail-style-helpers.mjs'
import { assertFeedbackStyles } from './feedback-style-helpers.mjs'

export async function assertReactPageLayout(page) {
  const issues = await page.getByRole('main').evaluate((main) => {
    const failures = []
    const visible = (element) => element.getBoundingClientRect().height > 0
    for (const link of main.querySelectorAll('a[href]')) {
      if (new URL(link.href).searchParams.has('legacy') || /Django|Прежняя версия/i.test(link.textContent)) {
        failures.push('Legacy link: ' + link.textContent.trim())
      }
    }
    for (const actions of main.querySelectorAll('.page-header__actions, .auth-card__links')) {
      if (![...actions.children].some(visible)) failures.push('Empty actions: ' + actions.className)
    }
    for (const field of main.querySelectorAll('.form-field')) {
      const input = field.querySelector('input:not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea')
      if (!input || !visible(input)) continue
      let label = [...field.children].find((element) => element.tagName === 'LABEL')
      if (!label && field.tagName === 'LABEL') {
        const text = [...field.childNodes].find((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
        if (text) { label = document.createRange(); label.selectNodeContents(text) }
      }
      if (!label) continue
      const bounds = label.getBoundingClientRect()
      const gap = input.getBoundingClientRect().top - bounds.bottom
      if (bounds.height > 0 && gap < 6) failures.push('Label spacing: ' + field.textContent.trim().slice(0, 60) + ' (' + gap + 'px)')
    }
    for (const section of main.querySelectorAll('.customer-form-section')) {
      const heading = section.querySelector(':scope > .customer-form-section__heading')
      const fields = section.querySelector(':scope > .field-grid')
      if (!heading || !fields || !visible(fields)) continue
      const title = heading.getBoundingClientRect()
      const controls = fields.getBoundingClientRect()
      const horizontalOverlap = Math.min(title.right, controls.right) - Math.max(title.left, controls.left)
      if (horizontalOverlap > 1 && controls.top - title.bottom < 16) failures.push('Section spacing: ' + heading.textContent.trim())
    }
    if (document.documentElement.scrollWidth > innerWidth) failures.push('Horizontal page overflow')
    return failures
  })
  assert.deepEqual(issues, [], page.url())
  await assertFormStyles(page)
  await assertTableStyles(page)
  await assertDetailStyles(page)
  await assertFeedbackStyles(page)
}
