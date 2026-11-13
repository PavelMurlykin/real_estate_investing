import assert from 'node:assert/strict'

export async function assertAsyncStates(page) {
  const issues = await page.evaluate(() => {
    const failures = []
    const luminance = (color) => color.match(/[\d.]+/g).slice(0, 3).map(Number).map((value) => {
      const channel = value / 255
      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
    }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0)
    for (const panel of document.querySelectorAll('.async-state')) {
      if (!panel.getBoundingClientRect().height) continue
      const compact = panel.classList.contains('async-state--compact')
      const style = getComputedStyle(panel)
      const heading = panel.querySelector('.async-state__body > h1, .async-state__body > h2, .async-state__body > h3')
      if (!heading || getComputedStyle(heading).fontSize !== (compact ? '16px' : '20px')) failures.push('State heading size')
      if (style.fontSize !== '14px' || style.borderRadius !== (compact ? '0px' : '16px')) failures.push('State typography or corners')
      if (style.paddingTop !== (compact ? '0px' : innerWidth <= 600 ? '20px' : '24px')) failures.push('State padding')
      if (!compact) {
        for (const text of panel.querySelectorAll('.async-state__body > h1, .async-state__body > h2, .async-state__body > p')) {
          const foreground = luminance(getComputedStyle(text).color)
          const background = luminance(style.backgroundColor)
          if ((Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05) < 4.5) failures.push('State contrast')
        }
      }
      for (const button of panel.querySelectorAll('.button')) {
        if (button.getBoundingClientRect().height < 48) failures.push('Small state action')
      }
      if (panel.classList.contains('async-state--loading') && panel.getAttribute('aria-busy') !== 'true') failures.push('Loading is not announced')
      if (panel.classList.contains('async-state--error') && panel.getAttribute('role') !== 'alert') failures.push('Error is not announced')
    }
    if (document.documentElement.scrollWidth > innerWidth) failures.push('State causes page overflow')
    return failures
  })
  assert.deepEqual(issues, [], page.url())
}
