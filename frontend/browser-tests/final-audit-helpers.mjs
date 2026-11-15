import assert from 'node:assert/strict'

export async function assertControlSemantics(page) {
  const issues = await page.getByRole('main').evaluate((main) => {
    const failures = []
    const ids = new Set()
    for (const element of document.querySelectorAll('[id]')) {
      if (ids.has(element.id)) failures.push('Duplicate ID: ' + element.id)
      ids.add(element.id)
    }
    const text = (element) => element.getAttribute('aria-label')?.trim()
      || element.getAttribute('aria-labelledby')?.split(/\s+/).map((id) => document.getElementById(id)?.textContent).join(' ').trim()
      || [...element.labels ?? []].map((label) => label.textContent).join(' ').trim()
      || (element.matches('button, a') ? element.textContent.trim() || element.querySelector('img')?.alt : '')
    for (const element of main.querySelectorAll('input:not([type=hidden]), select, textarea, button, a[href]')) {
      if (!element.getBoundingClientRect().height) continue
      if (!text(element)) failures.push('Unnamed control: ' + element.tagName + '#' + element.id)
      for (const attribute of ['aria-describedby', 'aria-labelledby', 'aria-controls', 'aria-activedescendant']) {
        for (const id of element.getAttribute(attribute)?.split(/\s+/).filter(Boolean) ?? []) {
          if (!document.getElementById(id)) failures.push('Missing ' + attribute + ' target: ' + id)
        }
      }
    }
    for (const image of main.querySelectorAll('img')) if (!image.hasAttribute('alt')) failures.push('Image without an alternative')
    return failures
  })
  assert.deepEqual(issues, [], page.url())
}

export async function assertFocusedControlVisible(page) {
  try { await page.waitForFunction(() => {
    const active = document.activeElement
    if (!active?.closest('main') || active.tagName === 'MAIN') return true
    let target = active
    if (active.getBoundingClientRect().height < 10) target = active.labels?.[0] ?? active
    const bounds = target.getBoundingClientRect()
    if (bounds.height < 10) return true
    const header = document.querySelector('.topbar').getBoundingClientRect()
    return bounds.top >= header.bottom - 1 && bounds.bottom <= innerHeight + 1
  }) } catch (error) {
    const detail = await page.evaluate(() => {
      const active = document.activeElement
      const bounds = active?.getBoundingClientRect()
      return { tag: active?.tagName, label: active?.labels?.[0]?.textContent.trim(), top: bounds?.top, bottom: bounds?.bottom,
        header: document.querySelector('.topbar').getBoundingClientRect().bottom, height: innerHeight, scroll: scrollY }
    })
    throw new Error('Focused control is obscured: ' + JSON.stringify(detail), { cause: error })
  }
}

export async function assertFormTraversal(page, steps = 12) {
  const controls = page.locator('main form input:not([type=hidden]):not(:disabled), main form select:not(:disabled), main form textarea:not(:disabled), main form button:not(:disabled), main form a[href]').filter({ visible: true })
  const count = await controls.count()
  if (!count) return
  const previous = await page.evaluateHandle(() => document.activeElement)
  const scroll = await page.evaluate(() => ({ x: scrollX, y: scrollY }))
  try {
    await controls.last().focus()
    await assertFocusedControlVisible(page)
    for (let index = 0; index < Math.min(count, steps); index++) {
      await page.keyboard.press('Shift+Tab')
      await assertFocusedControlVisible(page)
    }
  } finally {
    await previous.evaluate((element, position) => {
      if (element?.isConnected) element.focus({ preventScroll: true })
      window.scrollTo(position.x, position.y)
    }, scroll)
    await previous.dispose()
  }
}
