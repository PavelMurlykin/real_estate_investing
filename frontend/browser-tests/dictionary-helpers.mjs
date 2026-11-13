export async function chooseDictionary(page, name, label) {
  const input = page.getByRole('combobox', { name, exact: true }).first()
  await input.fill(typeof label === 'string' ? label : '')
  await page.getByRole('listbox').getByRole('option', { name: label, exact: true }).click()
  await input.press('Escape')
}
