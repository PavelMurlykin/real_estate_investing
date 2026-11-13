import assert from 'node:assert/strict'

export async function assertDetailStyles(page) {
  const issues = await page.getByRole('main').evaluate((main) => {
    const detail = main.querySelector('.detail-page')
    if (!detail) return []
    const failures = []
    const visible = (element) => element.getBoundingClientRect().height > 0
    const mobile = matchMedia('(max-width: 600px)').matches
    const padding = mobile ? '20px' : '24px'
    if (getComputedStyle(detail).rowGap !== '24px') failures.push('Page spacing')
    const title = detail.querySelector('.page-header h1')
    if (title && getComputedStyle(title).fontSize !== (mobile ? '28px' : '36px')) failures.push('Page title size')
    for (const card of detail.querySelectorAll('.detail-card')) {
      const style = getComputedStyle(card)
      if (style.borderRadius !== '16px' || style.borderTopWidth !== '1px') failures.push('Card border')
      if (style.paddingTop !== (card.classList.contains('detail-card--flush') ? '0px' : padding)) failures.push('Card padding')
    }
    for (const heading of detail.querySelectorAll('h2')) {
      if (visible(heading) && getComputedStyle(heading).fontSize !== '20px') failures.push('Section heading size')
    }
    for (const label of detail.querySelectorAll('dt')) {
      if (visible(label) && getComputedStyle(label).fontSize !== '12px') failures.push('Fact label size')
    }
    for (const button of detail.querySelectorAll('.button')) {
      if (visible(button) && button.getBoundingClientRect().height < 48) failures.push('Small button: ' + button.textContent.trim())
    }
    const actions = detail.querySelector(':scope > .page-header .page-header__actions')
    if (actions && actions.getBoundingClientRect().top < title.getBoundingClientRect().bottom) failures.push('Title competes with actions')
    if (document.documentElement.scrollWidth > innerWidth) failures.push('Horizontal page overflow')
    return failures
  })
  assert.deepEqual(issues, [], page.url())
}

export async function assertDetailKeyboard(page) {
  const actions = page.locator('.detail-page > .page-header .page-header__actions').locator('a, button')
  await actions.first().focus()
  for (let index = 1; index < await actions.count(); index++) {
    await page.keyboard.press('Tab')
    assert.equal(await actions.nth(index).evaluate((element) => element === document.activeElement), true)
    assert.equal(await actions.nth(index).evaluate((element) => parseFloat(getComputedStyle(element).outlineWidth) >= 2), true)
  }
}
