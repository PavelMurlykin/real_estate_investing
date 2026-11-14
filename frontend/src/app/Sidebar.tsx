import { Notice } from '@/shared/ui/Notice'
import { ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, type MouseEventHandler } from 'react'
import { useLocation } from 'react-router-dom'
import { NavigationLink, type NavigationItem } from '@/shared/ui/NavigationLink'
import { NavigationIcon, type NavigationIconName } from './NavigationIcon'

import { requestWithoutResponse } from '@/api/client'
import { sessionQueryOptions } from '@/api/queries'

import { MobileSidebar } from './MobileSidebar'

type SidebarProps = {
  isOpen: boolean
  isMobile?: boolean
  onClose: () => void
}

type SidebarNavigationItem = NavigationItem & { icon: NavigationIconName }

type NavigationGroupProps = {
  title: string
  items: SidebarNavigationItem[]
  onNavigate: MouseEventHandler<HTMLAnchorElement>
}

const primaryItems: SidebarNavigationItem[] = [
  {
    label: 'Главная',
    to: '/',
    end: true,
    icon: 'home',
  },
]

const realEstateItems: SidebarNavigationItem[] = [
  {
    label: 'Объекты недвижимости',
    to: '/properties',
    icon: 'property',
  },
  {
    label: 'Группы компаний',
    to: '/company-groups',
    icon: 'company',
  },
  {
    label: 'Застройщики',
    to: '/developers',
    icon: 'developer',
  },
  {
    label: 'Жилые комплексы',
    to: '/complexes',
    icon: 'complex',
  },
  {
    label: 'Справочники объектов',
    to: '/dictionaries/real-estate-types',
    activePaths: ['/dictionaries/*'],
    icon: 'dictionary',
  },
]

const catalogItems: SidebarNavigationItem[] = [
  {
    label: 'Локации',
    to: '/locations/regions',
    activePaths: ['/locations/*'],
    icon: 'location',
  },
  {
    label: 'Банки',
    to: '/banks',
    icon: 'bank',
  },
  {
    label: 'Ипотечные программы',
    to: '/mortgage-programs',
    icon: 'program',
  },
  {
    label: 'Программы застройщиков',
    to: '/developer-programs',
    icon: 'offer',
  },
  {
    label: 'Ключевая ставка',
    to: '/key-rate',
    icon: 'rate',
  },
]

const calculationItems: SidebarNavigationItem[] = [
  {
    label: 'Ипотечный калькулятор',
    to: '/mortgage',
    end: true,
    icon: 'calculator',
  },
  {
    label: 'Траншевая ипотека',
    to: '/mortgage/trench',
    end: true,
    icon: 'trench',
  },
]

const privateItems: SidebarNavigationItem[] = [
  {
    label: 'Добавить клиента',
    to: '/customers/new',
    end: true,
    icon: 'addCustomer',
  },
  {
    label: 'Клиенты',
    to: '/customers',
    excludedPaths: ['/customers/new'],
    icon: 'customer',
  },
  {
    label: 'Расчёты ипотеки',
    to: '/mortgage/calculations',
    icon: 'history',
  },
  {
    label: 'История траншей',
    to: '/mortgage/trench/calculations',
    icon: 'history',
  },
]

function NavigationGroup({ title, items, onNavigate }: NavigationGroupProps) {
  return <section className="sidebar-group">
    <h2>{title}</h2>
    <ul>{items.map(({ icon, ...item }) => <li key={item.to}>
      <NavigationLink {...item} icon={<NavigationIcon name={icon} />} onNavigate={onNavigate} />
    </li>)}</ul>
  </section>
}

export function Sidebar({ isOpen, isMobile = false, onClose }: SidebarProps) {
  const navigationRef = useRef<HTMLElement>(null)
  const { pathname } = useLocation()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  useEffect(() => {
    if (isMobile && !isOpen) return
    let frame = 0
    const revealCurrent = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        const navigation = navigationRef.current
        const current = navigation?.querySelector<HTMLElement>('[aria-current="page"]')
        if (!navigation || !current) return
        const bounds = navigation.getBoundingClientRect()
        const item = current.getBoundingClientRect()
        if (item.top < bounds.top + 6) navigation.scrollTop += item.top - bounds.top - 6
        else if (item.bottom > bounds.bottom - 6) navigation.scrollTop += item.bottom - bounds.bottom + 6
      })
    }
    revealCurrent()
    window.addEventListener('resize', revealCurrent)
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener('resize', revealCurrent) }
  }, [pathname, isOpen, isMobile, sessionQuery.data?.capabilities.viewPrivateRecords])
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
            <NavigationIcon name="close" />
          </button>
        </div>
      ) : null}

      <nav ref={navigationRef} className="sidebar__content" aria-label="Разделы приложения">
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
          <PageLoadingState compact title="Загрузка профиля" />
        ) : sessionQuery.isError ? (
          <ErrorState compact title="Не удалось загрузить аккаунт" isRetrying={sessionQuery.isFetching} onRetry={() => sessionQuery.refetch()} />
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
              <NavigationLink to="/profile" label="Профиль" activePaths={['/password/change']} onNavigate={onClose} />
              <button
                className="navigation-link"
                type="button"
                disabled={logoutMutation.isPending}
                onClick={() => logoutMutation.mutate()}
              >
                {logoutMutation.isPending ? 'Выходим…' : 'Выйти'}
              </button>
            </div>
            {logoutMutation.isError ? (
              <Notice as="p" tone="error" role="alert" className="account-error">Не удалось выйти. Повторите попытку.</Notice>
            ) : null}
          </>
        ) : (
          <div className="account-actions account-actions--anonymous">
            <NavigationLink to="/login" label="Войти" onNavigate={onClose} />
            <NavigationLink className="account-actions__primary" to="/register" label="Регистрация" onNavigate={onClose} />
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
