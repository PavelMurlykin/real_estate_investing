import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { MouseEventHandler } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'

import { requestWithoutResponse } from '@/api/client'
import { sessionQueryOptions } from '@/api/queries'

import { MobileSidebar } from './MobileSidebar'

type SidebarProps = {
  isOpen: boolean
  isMobile?: boolean
  onClose: () => void
}

type NavigationItem = {
  label: string
  href: string
  symbol: string
  reactRoute?: boolean
  activePath?: string
  excludedPaths?: string[]
}

type NavigationGroupProps = {
  title: string
  items: NavigationItem[]
  onNavigate: MouseEventHandler<HTMLAnchorElement>
}

const primaryItems: NavigationItem[] = [
  {
    label: 'Главная',
    href: '/',
    activePath: '/',
    symbol: 'Г',
    reactRoute: true,
  },
]

const realEstateItems: NavigationItem[] = [
  {
    label: 'Объекты недвижимости',
    href: '/properties',
    symbol: 'Н',
    reactRoute: true,
  },
  {
    label: 'Группы компаний',
    href: '/company-groups',
    symbol: 'Г',
    reactRoute: true,
  },
  {
    label: 'Застройщики',
    href: '/developers',
    symbol: 'З',
    reactRoute: true,
  },
  {
    label: 'Жилые комплексы',
    href: '/complexes',
    symbol: 'Ж',
    reactRoute: true,
  },
  {
    label: 'Справочники объектов',
    href: '/dictionaries/real-estate-types',
    activePath: '/dictionaries/*',
    symbol: 'О',
    reactRoute: true,
  },
]

const catalogItems: NavigationItem[] = [
  {
    label: 'Локации',
    href: '/locations/regions',
    activePath: '/locations/*',
    symbol: 'Л',
    reactRoute: true,
  },
  {
    label: 'Банки',
    href: '/banks',
    symbol: 'Б',
    reactRoute: true,
  },
  {
    label: 'Ипотечные программы',
    href: '/mortgage-programs',
    symbol: 'И',
    reactRoute: true,
  },
  {
    label: 'Программы застройщиков',
    href: '/developer-programs',
    symbol: 'П',
    reactRoute: true,
  },
  {
    label: 'Ключевая ставка',
    href: '/key-rate',
    symbol: '%',
    reactRoute: true,
  },
]

const calculationItems: NavigationItem[] = [
  {
    label: 'Ипотечный калькулятор',
    href: '/mortgage',
    activePath: '/mortgage',
    symbol: 'И',
    reactRoute: true,
  },
  {
    label: 'Траншевая ипотека',
    href: '/mortgage/trench',
    activePath: '/mortgage/trench',
    symbol: 'Т',
    reactRoute: true,
  },
]

const privateItems: NavigationItem[] = [
  {
    label: 'Добавить клиента',
    href: '/customers/new',
    activePath: '/customers/new',
    symbol: '+',
    reactRoute: true,
  },
  {
    label: 'Клиенты',
    href: '/customers',
    excludedPaths: ['/customers/new'],
    symbol: 'К',
    reactRoute: true,
  },
  {
    label: 'Расчёты ипотеки',
    href: '/mortgage/calculations',
    symbol: 'И',
    reactRoute: true,
  },
  {
    label: 'История траншей',
    href: '/mortgage/trench/calculations',
    symbol: 'Э',
    reactRoute: true,
  },
]

function NavigationGroup({ title, items, onNavigate }: NavigationGroupProps) {
  const { pathname } = useLocation()
  return (
    <section className="sidebar-group">
      <h2>{title}</h2>
      <ul>
        {items.map((item) => (
          <li key={item.href}>
            {item.reactRoute ? (
              <Link
                to={item.href}
                onClick={onNavigate}
                aria-current={
                  !item.excludedPaths?.some((path) => matchPath(path, pathname))
                  && matchPath(item.activePath ?? `${item.href}/*`, pathname)
                    ? 'page'
                    : undefined
                }
              >
                <span className="sidebar-link__symbol" aria-hidden="true">
                  {item.symbol}
                </span>
                <span>{item.label}</span>
              </Link>
            ) : (
              <a href={item.href} onClick={onNavigate}>
                <span className="sidebar-link__symbol" aria-hidden="true">
                  {item.symbol}
                </span>
                <span>{item.label}</span>
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

export function Sidebar({ isOpen, isMobile = false, onClose }: SidebarProps) {
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const logoutMutation = useMutation({
    mutationFn: () =>
      requestWithoutResponse('/api/v1/auth/logout/', { method: 'POST' }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['session'] })
      window.location.assign('/app/')
    },
  })

  const content = (
    <>
      {isMobile ? (
        <div className="sidebar__mobile-header">
          <span>Разделы</span>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть меню">
            ×
          </button>
        </div>
      ) : null}

      <nav className="sidebar__content" aria-label="Разделы приложения">
        <NavigationGroup title="Основное" items={primaryItems} onNavigate={onClose} />
        <NavigationGroup title="Недвижимость" items={realEstateItems} onNavigate={onClose} />
        <NavigationGroup title="Справочники" items={catalogItems} onNavigate={onClose} />
        <NavigationGroup title="Расчёты" items={calculationItems} onNavigate={onClose} />
        {sessionQuery.data?.capabilities.viewPrivateRecords ? (
          <NavigationGroup title="Работа с клиентами" items={privateItems} onNavigate={onClose} />
        ) : null}
      </nav>

      <div className="sidebar__account">
        {sessionQuery.isLoading ? (
          <div className="account-loading" aria-label="Загрузка профиля" />
        ) : sessionQuery.data?.isAuthenticated && sessionQuery.data.user ? (
          <>
            <div className="account-card">
              <span className="account-card__avatar" aria-hidden="true">
                {sessionQuery.data.user.displayName.slice(0, 1).toUpperCase()}
              </span>
              <div>
                <strong>{sessionQuery.data.user.displayName}</strong>
                <span>{sessionQuery.data.user.agencyName || sessionQuery.data.user.email}</span>
              </div>
            </div>
            <div className="account-actions">
              <Link to="/profile" onClick={onClose}>Профиль</Link>
              <button
                type="button"
                disabled={logoutMutation.isPending}
                onClick={() => logoutMutation.mutate()}
              >
                {logoutMutation.isPending ? 'Выходим…' : 'Выйти'}
              </button>
            </div>
            {logoutMutation.isError ? (
              <p className="account-error" role="alert">Не удалось выйти. Повторите попытку.</p>
            ) : null}
          </>
        ) : (
          <div className="account-actions account-actions--anonymous">
            <Link to="/login" onClick={onClose}>Войти</Link>
            <Link
              className="account-actions__primary"
              to="/register"
              onClick={onClose}
            >
              Регистрация
            </Link>
          </div>
        )}
      </div>
    </>
  )

  return isMobile ? (
    <MobileSidebar isOpen={isOpen} onClose={onClose}>
      {content}
    </MobileSidebar>
  ) : (
    <aside
      id="application-sidebar"
      className="sidebar"
      aria-label="Навигация по разделам"
    >
      {content}
    </aside>
  )
}
