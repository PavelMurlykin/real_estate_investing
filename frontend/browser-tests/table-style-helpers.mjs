import assert from 'node:assert/strict'

export async function assertTableStyles(page) {
  const issues = await page.getByRole('main').evaluate((main) => {
    const failures = []
    for (const table of main.querySelectorAll('table.property-table')) {
      if (!table.getBoundingClientRect().height) continue
      const name = table.caption?.textContent.trim() ?? 'Таблица'
      const region = table.parentElement
      if (!region.classList.contains('table-scroll-area') || region.getAttribute('tabindex') !== '0' || !region.getAttribute('aria-label')) failures.push(name + ': inaccessible scrolling')
      for (const heading of table.querySelectorAll('thead th')) {
        const style = getComputedStyle(heading)
        if (style.fontSize !== '12px') failures.push(name + ': heading text ' + style.fontSize)
        if (style.paddingLeft !== '16px') failures.push(name + ': heading padding ' + style.paddingLeft)
      }
      for (const cell of table.querySelectorAll('tbody td')) {
        const style = getComputedStyle(cell)
        if (style.fontSize !== '14px' || style.paddingLeft !== '16px') failures.push(name + ': cell typography or spacing')
        if (cell.getBoundingClientRect().height < 56) failures.push(name + ': small row')
      }
      for (const button of table.querySelectorAll('.sortable-header, .row-action')) {
        if (button.getBoundingClientRect().height < 44) failures.push(name + ': small table action')
      }
    }
    for (const button of main.querySelectorAll('.pagination button')) {
      if (button.getBoundingClientRect().height < 48) failures.push('Small pagination control')
    }
    if (innerWidth <= 500) {
      for (const pagination of main.querySelectorAll('.pagination')) {
        const area = pagination.getBoundingClientRect()
        const counter = pagination.querySelector('.pagination__status').getBoundingClientRect()
        const previous = pagination.querySelector('button').getBoundingClientRect()
        if (Math.abs(counter.x + counter.width / 2 - area.x - area.width / 2) > 1
          || counter.bottom > previous.top || counter.height > 24) failures.push('Mobile page counter is not centered above the buttons on one line')
      }
    }
    if (main.querySelector('.filter-panel select, .customer-calculation-toolbar select')) failures.push('A table filter still uses a separate native selector')
    if (document.documentElement.scrollWidth > innerWidth) failures.push('Table causes horizontal page overflow')
    return failures
  })
  assert.deepEqual(issues, [], page.url())
}
