import assert from 'node:assert/strict'

export async function assertNavigationStyles(page) {
  const failures = await page.evaluate(() => {
    const issues = []
    const visible = (element) => element.getBoundingClientRect().height > 0
    const luminance = (color) => color.match(/[\d.]+/g).slice(0, 3).map(Number).map((value) => {
      const channel = value / 255
      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
    }).reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index], 0)
    const contrast = (a, b) => (Math.max(luminance(a), luminance(b)) + 0.05) / (Math.min(luminance(a), luminance(b)) + 0.05)
    for (const element of document.querySelectorAll('.navigation-link')) {
      if (!visible(element)) continue
      const style = getComputedStyle(element)
      const label = element.textContent.trim()
      if (element.getBoundingClientRect().height < 48 || style.fontSize !== '14px' || style.borderRadius !== '12px') issues.push('Navigation size: ' + label)
      let background = style.backgroundColor
      let parent = element.parentElement
      while (parent && background === 'rgba(0, 0, 0, 0)') { background = getComputedStyle(parent).backgroundColor; parent = parent.parentElement }
      if (background !== 'rgba(0, 0, 0, 0)' && contrast(style.color, background) < 4.5) issues.push('Navigation contrast: ' + label)
      if (element.hasAttribute('aria-current') && (!style.textDecorationLine.includes('underline') || style.fontWeight !== '700')) issues.push('Navigation current indicator: ' + label)
    }
    const topbar = document.querySelector('.topbar')
    if (topbar) {
      const bounds = topbar.getBoundingClientRect()
      if (topbar.scrollHeight > topbar.clientHeight) issues.push('Header overflow')
      for (const link of topbar.querySelectorAll('.top-navigation a')) {
        const item = link.getBoundingClientRect()
        if (item.left < 0 || item.right > innerWidth || item.top < bounds.top || item.bottom > bounds.bottom || link.scrollHeight > link.clientHeight) issues.push('Header link clipped: ' + link.textContent.trim())
      }
      for (const button of topbar.querySelectorAll('.icon-button')) if (visible(button) && button.getBoundingClientRect().height < 48) issues.push('Small header action')
    }
    for (const heading of document.querySelectorAll('.sidebar-group h2')) if (visible(heading) && getComputedStyle(heading).fontSize !== '12px') issues.push('Sidebar heading size')
    const sections = document.querySelector('.sidebar__content')
    if (sections?.querySelectorAll('[aria-current="page"]').length > 1) issues.push('Multiple current sidebar sections')
    for (const tabs of document.querySelectorAll('.dictionary-tabs')) if (visible(tabs) && tabs.querySelectorAll('[aria-current="page"]').length !== 1) issues.push('Section current indicator')
    if (document.documentElement.scrollWidth > innerWidth) issues.push('Navigation page overflow')
    return issues
  })
  assert.deepEqual(failures, [], page.url())
}

export async function assertCurrentLinkVisible(navigation) {
  await navigation.page().waitForFunction((element) => {
    const current = element.querySelector('[aria-current="page"]')
    if (!current) return false
    const parent = element.getBoundingClientRect()
    const item = current.getBoundingClientRect()
    return item.left >= parent.left - 1 && item.right <= parent.right + 1 && item.top >= parent.top - 1 && item.bottom <= parent.bottom + 1
  }, await navigation.elementHandle())
}
