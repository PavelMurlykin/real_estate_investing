import assert from 'node:assert/strict'

export async function assertFeedbackStyles(page) {
  const issues = await page.evaluate(() => {
    const failures = []
    const luminance = (color) => color.match(/[\d.]+/g).slice(0, 3).map(Number).map((value) => {
      const channel = value / 255
      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
    }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0)
    for (const notice of document.querySelectorAll('.notice')) {
      if (!notice.getBoundingClientRect().height) continue
      const style = getComputedStyle(notice)
      if (style.paddingTop !== '16px' || style.borderRadius !== '12px' || style.fontSize !== '14px') failures.push('Inconsistent notice geometry')
      const foreground = luminance(style.color)
      const background = luminance(style.backgroundColor)
      if ((Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05) < 4.5) failures.push('Low notice contrast')
      const dismiss = notice.querySelector('.notice__dismiss')
      if (dismiss && dismiss.getBoundingClientRect().height < 44) failures.push('Small notice close control')
    }
    for (const dialog of document.querySelectorAll('[role=alertdialog], dialog[open]')) {
      if (!dialog.getBoundingClientRect().height) continue
      if (dialog.tagName !== 'DIALOG' || !dialog.matches(':modal')) failures.push('Dialog does not isolate the background')
      if (dialog.classList.contains('sidebar--mobile')) continue
      const style = getComputedStyle(dialog)
      if (style.borderRadius !== '16px' || style.paddingTop !== (innerWidth <= 600 ? '20px' : '24px')) failures.push('Inconsistent dialog geometry')
      const bounds = dialog.getBoundingClientRect()
      if (bounds.left < 0 || bounds.right > innerWidth || bounds.top < 0 || bounds.bottom > innerHeight) failures.push('Dialog extends beyond viewport')
      for (const button of dialog.querySelectorAll('.button')) {
        if (button.getBoundingClientRect().height < 48) failures.push('Small dialog action')
      }
    }
    if (document.documentElement.scrollWidth > innerWidth) failures.push('Feedback causes page overflow')
    return failures
  })
  assert.deepEqual(issues, [], page.url())
}
