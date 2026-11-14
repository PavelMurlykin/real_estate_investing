import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { SectionNavigation } from './SectionNavigation'

const items = [{ to: '/banks', label: 'Банки' }, { to: '/mortgage-programs', label: 'Программы' }, { to: '/key-rate', label: 'Ставка' }]
function Address() { return <output aria-label="Адрес">{useLocation().pathname}</output> }

describe('SectionNavigation', () => {
  it('moves focus with arrows and Home/End, and navigates only after Enter', async () => {
    const user = userEvent.setup()
    renderWithProviders(<><SectionNavigation label="Разделы" items={items} /><Address /></>, { initialRoute: '/banks' })
    const [first, second, last] = screen.getAllByRole('link')
    first.focus()
    await user.keyboard('{ArrowRight}')
    expect(second).toHaveFocus()
    expect(screen.getByLabelText('Адрес')).toHaveTextContent('/banks')
    await user.keyboard('{End}')
    expect(last).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(first).toHaveFocus()
    await user.keyboard('{ArrowLeft}')
    expect(last).toHaveFocus()
    await user.keyboard('{Home}')
    expect(first).toHaveFocus()
    await user.keyboard('{End}{Enter}')
    expect(screen.getByLabelText('Адрес')).toHaveTextContent('/key-rate')
    expect(last).toHaveAttribute('aria-current', 'page')
    expect(first).not.toHaveAttribute('aria-current')
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
  })

  it('retains ordinary Tab and Shift+Tab order through all route links', async () => {
    const user = userEvent.setup()
    renderWithProviders(<><button>До меню</button><SectionNavigation label="Разделы" items={items} /><button>После меню</button></>)
    await user.tab()
    expect(screen.getByRole('button', { name: 'До меню' })).toHaveFocus()
    for (const link of screen.getAllByRole('link')) { await user.tab(); expect(link).toHaveFocus() }
    await user.tab()
    expect(screen.getByRole('button', { name: 'После меню' })).toHaveFocus()
    await user.tab({ shift: true })
    expect(screen.getByRole('link', { name: 'Ставка' })).toHaveFocus()
    await user.keyboard('{Control>}{Home}{/Control}')
    expect(screen.getByRole('link', { name: 'Ставка' })).toHaveFocus()
  })
})
