import { screen, within } from '@testing-library/react'
import type userEvent from '@testing-library/user-event'

/** Choose through the visible search menu, just as a user would. */
export async function chooseOption(user: ReturnType<typeof userEvent.setup>, label: string, option: string) {
  await user.click(screen.getByRole('combobox', { name: label }))
  const list = screen.getByRole('listbox', { name: `Варианты: ${label}` })
  await user.click(await within(list).findByRole('option', { name: option }))
  await user.keyboard('{Escape}')
}
