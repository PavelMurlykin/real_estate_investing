import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import {
  deleteMortgageProgram,
  mortgageProgramDetailQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import { formatCurrency, formatDateTime, formatInteger } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

export function MortgageProgramDetailPage() {
  const { mortgageProgramId } = useParams()
  const mortgageProgramIdentifier = Number(mortgageProgramId)
  const hasValidIdentifier = (
    Number.isInteger(mortgageProgramIdentifier)
    && mortgageProgramIdentifier > 0
  )
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const sessionQuery = useQuery(sessionQueryOptions)
  const programQuery = useQuery({
    ...mortgageProgramDetailQueryOptions(mortgageProgramIdentifier),
    enabled: hasValidIdentifier,
  })
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const deleteTriggerRef = useRef<HTMLButtonElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: () => deleteMortgageProgram(mortgageProgramIdentifier),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['mortgage-programs'] })
      queryClient.removeQueries({
        queryKey: ['mortgage-program', mortgageProgramIdentifier],
      })
      navigate('/mortgage-programs')
    },
  })
  useDocumentTitle(programQuery.data?.name ?? 'Ипотечная программа')

  useEffect(() => {
    if (!isDeleteDialogOpen) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setIsDeleteDialogOpen(false)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, isDeleteDialogOpen])

  if (!hasValidIdentifier) {
    return (
      <EmptyState
        title="Ипотечная программа не найдена"
        description="Проверьте адрес или вернитесь к списку программ."
        action={(
          <Link className="button button--secondary" to="/mortgage-programs">
            К списку
          </Link>
        )}
      />
    )
  }
  if (programQuery.isLoading) return <PageLoadingState />
  if (programQuery.isError || !programQuery.data) {
    return (
      <ErrorState
        title="Ипотечная программа не найдена или недоступна"
        onRetry={() => void programQuery.refetch()}
      />
    )
  }

  const mortgageProgram = programQuery.data
  const canManageCatalogs = (
    sessionQuery.data?.capabilities.manageCatalogs === true
  )

  return (
    <div className="page-stack mortgage-program-detail-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Карточка ипотечной программы</span>
          <h1>{mortgageProgram.name}</h1>
          <p>Канонические условия, лимиты по регионам и имена из источников.</p>
        </div>
        <div className="page-header__actions">
          <Link className="button button--secondary" to="/mortgage-programs">
            К списку
          </Link>
          {canManageCatalogs ? (
            <>
              <Link
                className="button button--secondary"
                to={`/mortgage-programs/${mortgageProgram.id}/edit`}
              >
                Редактировать
              </Link>
              <button
                className="button button--danger"
                type="button"
                ref={deleteTriggerRef}
                onClick={() => {
                  deleteMutation.reset()
                  setIsDeleteDialogOpen(true)
                }}
              >
                Удалить
              </button>
            </>
          ) : null}
        </div>
      </header>

      <section className="mortgage-program-summary-card">
        <div className="mortgage-program-summary-card__heading">
          <div>
            <span className={mortgageProgram.isActive
              ? 'catalog-status'
              : 'catalog-status catalog-status--inactive'}>
              {mortgageProgram.isActive ? 'Активна' : 'Неактивна'}
            </span>
            <h2>{mortgageProgram.name}</h2>
            <p>{mortgageProgram.condition}</p>
          </div>
          <span className="mortgage-program-type-badge">
            {mortgageProgram.isPreferential ? 'Льготная' : 'Рыночная'}
          </span>
        </div>
        <dl className="property-detail-facts mortgage-program-facts">
          <div>
            <dt>Федеральный лимит</dt>
            <dd>
              {mortgageProgram.creditLimit
                ? formatCurrency(mortgageProgram.creditLimit)
                : 'Не задан'}
            </dd>
          </div>
          <div>
            <dt>Банков</dt>
            <dd>{formatInteger(mortgageProgram.bankCount)}</dd>
          </div>
          <div>
            <dt>Программ застройщиков</dt>
            <dd>{formatInteger(mortgageProgram.developerProgramCount)}</dd>
          </div>
          <div>
            <dt>Региональных исключений</dt>
            <dd>{formatInteger(mortgageProgram.regionalCreditLimits.length)}</dd>
          </div>
        </dl>
      </section>

      <section
        className="saved-property-card"
        aria-labelledby="regional-credit-limits-title"
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">География</span>
            <h2 id="regional-credit-limits-title">Региональные лимиты</h2>
          </div>
        </div>
        {mortgageProgram.regionalCreditLimits.length ? (
          <>
            <div className="property-table-wrapper">
              <table className="property-table mortgage-program-related-table">
                <caption className="visually-hidden">
                  Региональные лимиты программы {mortgageProgram.name}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Регион</th>
                    <th scope="col">Кредитный лимит</th>
                    <th scope="col">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {mortgageProgram.regionalCreditLimits.map((regionalLimit) => (
                    <tr key={regionalLimit.id}>
                      <td><strong>{regionalLimit.regionName}</strong></td>
                      <td>{formatCurrency(regionalLimit.creditLimit)}</td>
                      <td>
                        {regionalLimit.isActive ? 'Активен' : 'Неактивен'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="property-mobile-list">
              {mortgageProgram.regionalCreditLimits.map((regionalLimit) => (
                <article className="property-mobile-card" key={regionalLimit.id}>
                  <div className="property-mobile-card__heading">
                    <div><span>Регион</span><h2>{regionalLimit.regionName}</h2></div>
                    <span>{regionalLimit.isActive ? 'Активен' : 'Неактивен'}</span>
                  </div>
                  <dl>
                    <div>
                      <dt>Кредитный лимит</dt>
                      <dd>{formatCurrency(regionalLimit.creditLimit)}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </>
        ) : (
          <p className="complex-copy">Региональные исключения не заданы.</p>
        )}
      </section>

      <section
        className="saved-property-card"
        aria-labelledby="mortgage-program-aliases-title"
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">Сопоставление данных</span>
            <h2 id="mortgage-program-aliases-title">Алиасы программы</h2>
          </div>
        </div>
        {mortgageProgram.aliases.length ? (
          <>
            <div className="property-table-wrapper">
              <table className="property-table mortgage-program-related-table">
                <caption className="visually-hidden">
                  Алиасы программы {mortgageProgram.name}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Имя из источника</th>
                    <th scope="col">Ключ сопоставления</th>
                    <th scope="col">Источник</th>
                    <th scope="col">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {mortgageProgram.aliases.map((alias) => (
                    <tr key={alias.id}>
                      <td><strong>{alias.sourceName}</strong></td>
                      <td><code>{alias.normalizedName}</code></td>
                      <td>{alias.source || '—'}</td>
                      <td>{alias.isActive ? 'Активен' : 'Неактивен'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="property-mobile-list">
              {mortgageProgram.aliases.map((alias) => (
                <article className="property-mobile-card" key={alias.id}>
                  <div className="property-mobile-card__heading">
                    <div><span>Алиас</span><h2>{alias.sourceName}</h2></div>
                    <span>{alias.isActive ? 'Активен' : 'Неактивен'}</span>
                  </div>
                  <dl>
                    <div><dt>Ключ</dt><dd>{alias.normalizedName}</dd></div>
                    <div><dt>Источник</dt><dd>{alias.source || '—'}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          </>
        ) : (
          <p className="complex-copy">Алиасы для импорта не добавлены.</p>
        )}
      </section>

      <section
        className="property-system-information"
        aria-label="Системная информация"
      >
        <span>Создано: {formatDateTime(mortgageProgram.createdAt)}</span>
        <span>Обновлено: {formatDateTime(mortgageProgram.updatedAt)}</span>
      </section>
      <p className="legacy-fallback">
        Нужен прежний экран?{' '}
        <a className="text-link" href={mortgageProgram.legacyEditUrl}>
          Открыть Django-форму
        </a>
      </p>

      {isDeleteDialogOpen ? (
        <div
          className="confirmation-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (
              event.currentTarget === event.target
              && !deleteMutation.isPending
            ) {
              setIsDeleteDialogOpen(false)
            }
          }}
        >
          <section
            className="confirmation-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="mortgage-program-detail-delete-title"
            aria-describedby="mortgage-program-detail-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="mortgage-program-detail-delete-title">
              Удалить программу?
            </h2>
            <p id="mortgage-program-detail-delete-description">
              «{mortgageProgram.name}», её лимиты и алиасы будут удалены.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                {deleteMutation.error instanceof ApiError
                  && deleteMutation.error.status === 409
                  ? 'Программа используется банком или программой застройщика. Сначала переназначьте эти связи.'
                  : 'Не удалось удалить программу. Повторите попытку.'}
              </p>
            ) : null}
            <div className="confirmation-dialog__actions">
              <button
                className="button button--secondary"
                type="button"
                ref={cancelButtonRef}
                disabled={deleteMutation.isPending}
                onClick={() => setIsDeleteDialogOpen(false)}
              >
                Отмена
              </button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
              >
                {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
