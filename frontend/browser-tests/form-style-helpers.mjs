import assert from 'node:assert/strict'

/** Check the rendered controls, including dictionary popups and nested forms. */
export async function assertFormStyles(page) {
  const issues = await page.getByRole('main').evaluate((main) => {
    const failures = []
    const visible = (element) => element.getBoundingClientRect().height > 0
    const description = (element) => element.labels?.[0]?.textContent.trim().slice(0, 50) || element.textContent.trim().slice(0, 50) || element.tagName
    for (const input of main.querySelectorAll('.form-field input:not([type=checkbox]):not([type=radio]):not([type=file]):not([type=hidden]), .form-field select, .form-field textarea')) {
      if (!visible(input)) continue
      const style = getComputedStyle(input)
      const height = input.getBoundingClientRect().height
      if (style.fontSize !== '16px') failures.push(description(input) + ': text ' + style.fontSize)
      if (style.borderRadius !== '12px') failures.push(description(input) + ': radius ' + style.borderRadius)
      if (input.getAttribute('role') === 'combobox' && parseFloat(style.paddingRight) < 32) failures.push(description(input) + ': text overlaps the dropdown arrow')
      if (input.tagName === 'TEXTAREA' ? height < 128 : Math.abs(height - 48) > 1) failures.push(description(input) + ': height ' + height)
    }
    for (const button of main.querySelectorAll('form .button, .page-header__actions .button')) {
      if (!visible(button)) continue
      const style = getComputedStyle(button)
      if (button.getBoundingClientRect().height < 48) failures.push(description(button) + ': small button')
      if (style.fontSize !== '14px') failures.push(description(button) + ': button text ' + style.fontSize)
    }
    for (const button of main.querySelectorAll('form .text-button')) {
      if (visible(button) && button.getBoundingClientRect().height < 44) failures.push(description(button) + ': small action target')
    }
    for (const heading of main.querySelectorAll('.page-header h1, .auth-card__header h1')) {
      if (getComputedStyle(heading).fontSize !== (innerWidth <= 600 ? '28px' : '36px')) failures.push(heading.textContent.trim() + ': page heading size')
    }
    for (const heading of main.querySelectorAll('.customer-form-section__heading h2, .calculator-section__heading h2, .dictionary-form-card h2')) {
      if (getComputedStyle(heading).fontSize !== '20px') failures.push(heading.textContent.trim() + ': section heading size')
    }
    for (const heading of main.querySelectorAll('.nested-editor-card__heading > strong, .bank-program-editor__heading > strong, .complex-editor-card__heading h3')) {
      if (getComputedStyle(heading).fontSize !== '16px') failures.push(heading.textContent.trim() + ': nested heading size')
    }
    return failures
  })
  assert.deepEqual(issues, [], page.url())
}

export async function assertFormKeyboard(page) {
  const first = page.locator('main form input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([role=combobox]):not(:disabled)').filter({ visible: true }).first()
  if (!await first.count()) return
  await first.focus()
  await first.press('Tab')
  assert.equal(await page.locator(':focus').evaluate((element) => Boolean(element.closest('form'))), true, 'Tab must reach the next form control')
  await page.keyboard.press('Shift+Tab')
  assert.equal(await first.evaluate((element) => element === document.activeElement), true, 'Shift+Tab must return to the previous field')
  const focus = await first.evaluate((element) => {
    const style = getComputedStyle(element)
    return { width: parseFloat(style.outlineWidth), style: style.outlineStyle }
  })
  assert.ok(focus.width >= 2 && focus.style !== 'none', 'Keyboard focus must remain visible')
  await first.press('Escape')
}
