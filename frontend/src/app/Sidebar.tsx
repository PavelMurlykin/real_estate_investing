import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { MouseEventHandler } from 'react'
import { Link } from 'react-router-dom'

import { requestWithoutResponse } from '@/api/client'
import { sessionQueryOptions } from '@/api/queries'

type SidebarProps = {
  isOpen: boolean
  onClose: () => void
}

type NavigationItem = {
  label: string
  href: string
  symbol: string
  reactRoute?: boolean
}

type NavigationGroupProps = {
  title: string
  items: NavigationItem[]
  onNavigate: MouseEventHandler<HTMLAnchorElement>
}

const realEstateItems: NavigationItem[] = [
  { label: 'Группы компаний', href: '/property/company-groups/', symbol: 'Г' },
  { label: 'Застройщики', href: '/property/developers/', symbol: 'З' },
  { label: 'Жилые комплексы', href: '/property/complexes/', symbol: 'Ж' },
  { label: 'Справочники объектов', href: '/property/dictionaries/', symbol: 'О' },
]

const catalogItems: NavigationItem[] = [
  { label: 'Локации', href: '/locations/', symbol: 'Л' },
  { label: 'Банки и программы', href: '/bank/', symbol: 'Б' },
  { label: 'Ключевая ставка', href: '/bank/key-rate/', symbol: '%' },
]

const privateItems: NavigationItem[] = [
  {
    label: 'Клиенты',
    href: '/customers',
    symbol: 'К',
    reactRoute: true,
  },
  {
    label: 'Расчёты ипотеки',
    href: '/mortgage/calculations',
    symbol: 'И',
    reactRoute: true,
  },
  { label: 'Траншевая ипотека', href: '/mortgage/trench-calculations/', symbol: 'Т' },
]

function NavigationGroup({ title, items, onNavigate }: NavigationGroupProps) {
  return (
    <section className="sidebar-group">
      <h2>{title}</h2>
      <ul>
        {items.map((item) => (
          <li key={item.href}>
            {item.reactRoute ? (
              <Link to={item.href} onClick={onNavigate}>
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

export function Sidebar({ isOpen, onClose }: SidebarProps) {
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

  return (
    <>
      <button
        className={`sidebar-backdrop ${isOpen ? 'sidebar-backdrop--visible' : ''}`}
        type="button"
        tabIndex={isOpen ? 0 : -1}
        aria-label="Закрыть меню разделов"
        onClick={onClose}
      />
      <aside
        id="application-sidebar"
        className={`sidebar ${isOpen ? 'sidebar--open' : ''}`}
        aria-label="Навигация по разделам"
      >
        <div className="sidebar__mobile-header">
          <span>Разделы</span>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть меню">
            ×
          </button>
        </div>

        <div className="sidebar__content">
          <NavigationGroup title="Недвижимость" items={realEstateItems} onNavigate={onClose} />
          <NavigationGroup title="Справочники" items={catalogItems} onNavigate={onClose} />
          {sessionQuery.data?.capabilities.viewPrivateRecords ? (
            <NavigationGroup title="Работа с клиентами" items={privateItems} onNavigate={onClose} />
          ) : null}
        </div>

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
                <a href="/users/profile/edit/">Профиль</a>
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
              <a href="/users/login/">Войти</a>
              <a className="account-actions__primary" href="/users/register/">Регистрация</a>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
