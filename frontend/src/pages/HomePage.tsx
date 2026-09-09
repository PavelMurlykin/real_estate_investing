import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { overviewQueryOptions } from '@/api/queries'
import { formatArea, formatCurrency, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function HomePage() {
  useDocumentTitle('Главная')
  const overviewQuery = useQuery(overviewQueryOptions)

  if (overviewQuery.isLoading) {
    return <PageLoadingState />
  }

  if (overviewQuery.isError || !overviewQuery.data) {
    return <ErrorState onRetry={() => void overviewQuery.refetch()} />
  }

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div className="hero-panel__content">
          <span className="eyebrow">Рабочее пространство</span>
          <h1>Инвестиции в недвижимость — в единой системе</h1>
          <p>
            Сравнивайте объекты, работайте с клиентами и рассчитывайте ипотеку,
            не теряя контекст между разделами.
          </p>
          <div className="hero-panel__actions">
            <Link className="button button--primary" to="/properties">
              Смотреть объекты
            </Link>
            <a className="button button--secondary" href="/mortgage/">
              Рассчитать ипотеку
            </a>
          </div>
        </div>
        <div className="hero-panel__visual" aria-hidden="true">
          <div className="building building--back" />
          <div className="building building--middle" />
          <div className="building building--front" />
          <span className="hero-panel__sun" />
        </div>
      </section>

      <section aria-labelledby="statistics-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Актуальные данные</span>
            <h2 id="statistics-title">Портфель платформы</h2>
          </div>
        </div>
        <div className="statistics-grid">
          {overviewQuery.data.statistics.map((statistic) => (
            <article className="statistic-card" key={statistic.key}>
              <span>{statistic.label}</span>
              <strong>{formatInteger(statistic.value)}</strong>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="recent-properties-title">
        <div className="section-heading section-heading--with-action">
          <div>
            <span className="eyebrow">Недавно обновлены</span>
            <h2 id="recent-properties-title">Объекты недвижимости</h2>
          </div>
          <Link to="/properties">
            Все объекты <span aria-hidden="true">→</span>
          </Link>
        </div>

        {overviewQuery.data.recentProperties.length === 0 ? (
          <EmptyState
            title="Объектов пока нет"
            description="После добавления недвижимости последние объекты появятся здесь."
          />
        ) : (
          <div className="property-preview-grid">
            {overviewQuery.data.recentProperties.map((property) => (
              <article className="property-preview" key={property.id}>
                <div className="property-preview__image" aria-hidden="true">
                  <span>{property.realEstateComplex.slice(0, 1)}</span>
                </div>
                <div className="property-preview__body">
                  <span className="property-preview__location">{property.city}</span>
                  <h3>{property.realEstateComplex}</h3>
                  <p>
                    Корпус {property.building}, квартира {property.apartmentNumber}
                  </p>
                  <div className="property-preview__meta">
                    <span>{formatArea(property.area)}</span>
                    <strong>{formatCurrency(property.propertyCost)}</strong>
                  </div>
                  <a href={property.detailUrl}>Открыть объект</a>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="workflow-panel" aria-labelledby="workflow-title">
        <div>
          <span className="eyebrow">Быстрый старт</span>
          <h2 id="workflow-title">От объекта до ипотечного предложения</h2>
        </div>
        <ol>
          <li>
            <span>01</span>
            <strong>Выберите объект</strong>
            <p>Найдите подходящую квартиру в общем каталоге.</p>
          </li>
          <li>
            <span>02</span>
            <strong>Сравните условия</strong>
            <p>Проверьте программы банков и параметры сделки.</p>
          </li>
          <li>
            <span>03</span>
            <strong>Сохраните расчёт</strong>
            <p>Свяжите результат с клиентом и вернитесь к нему позже.</p>
          </li>
        </ol>
      </section>
    </div>
  )
}
