import { SectionNavigation } from '@/shared/ui/SectionNavigation'

const items = [
  { to: '/banks', label: 'Банки' },
  { to: '/mortgage-programs', label: 'Ипотечные программы' },
  { to: '/developer-programs', label: 'Программы застройщиков' },
  { to: '/key-rate', label: 'Ключевая ставка' },
]

export function BankCatalogNavigation() {
  return <SectionNavigation label="Разделы банков" items={items} />
}
