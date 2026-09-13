import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  deleteDeveloperMortgageProgram,
  developerMortgageProgramListQueryOptions,
  developerMortgageProgramOptionsQueryOptions,
  sessionQueryOptions,
} from '@/api/queries'
import type { DeveloperMortgageProgram } from '@/api/schemas'
import { formatCurrency, formatInteger, formatPercent } from '@/shared/lib/formatters'
import { useDocumentTitle } from '@/shared/lib/useDocumentTitle'
import { EmptyState, ErrorState, PageLoadingState } from '@/shared/ui/AsyncState'

import { DeveloperMortgageProgramImportPanel } from './DeveloperMortgageProgramImportPanel'

const orderingOptions = [
  { value: 'companyGroup', label: 'По группе компаний' },
  { value: 'realEstateComplex', label: 'По ЖК' },
  { value: 'bank', label: 'По банку' },
  { value: 'mortgageProgram', label: 'По программе' },
  { value: 'interestRate', label: 'Сначала низкая ставка' },
  { value: '-interestRate', label: 'Сначала высокая ставка' },
  { value: '-updatedAt', label: 'Недавно изменённые' },
]

function scopeName(program: DeveloperMortgageProgram) {
  return program.realEstateComplexName ?? 'Все ЖК группы'
}

function valueOrDash(value: string | null, formatter = formatPercent) {
  return value === null ? '—' : formatter(value)
}

export function DeveloperMortgageProgramListPage() {
  useDocumentTitle('Программы застройщиков')
  const [searchParameters, setSearchParameters] = useSearchParams()
  const selectedCompanyGroup = Number(
    searchParameters.get('companyGroupId') ?? 0,
  ) || null
  const programQuery = useQuery(
    developerMortgageProgramListQueryOptions(searchParameters),
  )
  const optionsQuery = useQuery(
    developerMortgageProgramOptionsQueryOptions(selectedCompanyGroup),
  )
  const sessionQuery = useQuery(sessionQueryOptions)
  const queryClient = useQueryClient()
  const [selectedProgram, setSelectedProgram] = (
    useState<DeveloperMortgageProgram | null>(null)
  )
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const deleteMutation = useMutation({
    mutationFn: (identifier: number) => deleteDeveloperMortgageProgram(identifier),
    onSuccess: async () => {
      setSelectedProgram(null)
      await queryClient.invalidateQueries({
        queryKey: ['developer-mortgage-programs'],
      })
      window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
    },
  })

  useEffect(() => {
    if (!selectedProgram) return
    cancelButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleteMutation.isPending) {
        setSelectedProgram(null)
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [deleteMutation.isPending, selectedProgram])

  const updateParameters = (updates: Record<string, string | null>) => {
    const nextParameters = new URLSearchParams(searchParameters)
    for (const [fieldName, value] of Object.entries(updates)) {
      if (!value || value === 'all') nextParameters.delete(fieldName)
      else nextParameters.set(fieldName, value)
    }
    setSearchParameters(nextParameters)
  }
  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const input = event.currentTarget.elements.namedItem('q')
    updateParameters({
      q: input instanceof HTMLInputElement ? input.value.trim() || null : null,
      page: null,
    })
  }
  const canManage = sessionQuery.data?.capabilities.manageCatalogs === true

  if (programQuery.isLoading || optionsQuery.isLoading) {
    return <PageLoadingState />
  }
  if (programQuery.isError || !programQuery.data) {
    return <ErrorState onRetry={() => void programQuery.refetch()} />
  }
  if (optionsQuery.isError || !optionsQuery.data) {
    return (
      <ErrorState
        title="Не удалось загрузить фильтры программ"
        onRetry={() => void optionsQuery.refetch()}
      />
    )
  }

  const { results, page, totalCount, totalPages } = programQuery.data
  const options = optionsQuery.data
  return (
    <div className="page-stack developer-program-list-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Специальные условия</span>
          <h1>Программы застройщиков</h1>
          <p>
            Ипотечные условия групп компаний и отдельных жилых комплексов.
          </p>
        </div>
        <div className="page-header__actions">
          <a className="button button--secondary" href="/bank/developer-programs/">
            Прежняя версия
          </a>
          {canManage ? (
            <Link className="button button--primary" to="/developer-programs/new">
              Добавить программу
            </Link>
          ) : null}
        </div>
      </header>

      <nav className="dictionary-tabs" aria-label="Разделы банков">
        <Link to="/banks">Банки</Link>
        <Link to="/mortgage-programs">Ипотечные программы</Link>
        <Link to="/developer-programs" aria-current="page">
          Программы застройщиков
        </Link>
        <Link to="/key-rate">Ключевая ставка</Link>
      </nav>

      {canManage ? <DeveloperMortgageProgramImportPanel /> : null}

      <section
        className="filter-panel developer-program-filter-panel"
        aria-label="Фильтры программ застройщиков"
      >
        <form className="search-form" role="search" onSubmit={submitSearch}>
          <label htmlFor="developer-program-search">Поиск</label>
          <div className="search-control">
            <span aria-hidden="true">⌕</span>
            <input
              id="developer-program-search"
              name="q"
              type="search"
              key={searchParameters.get('q') ?? ''}
              defaultValue={searchParameters.get('q') ?? ''}
              placeholder="Группа, ЖК, банк или программа"
            />
            <button className="button button--dark" type="submit">Найти</button>
          </div>
        </form>
        <div className="sort-control">
          <label htmlFor="developer-program-group">Группа компаний</label>
          <select
            id="developer-program-group"
            value={searchParameters.get('companyGroupId') ?? ''}
            onChange={(event) => updateParameters({
              companyGroupId: event.target.value || null,
              realEstateComplexId: null,
              page: null,
            })}
          >
            <option value="">Все группы</option>
            {options.companyGroups.map((option) => (
              <option value={option.id} key={option.id}>{option.name}</option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="developer-program-complex">Жилой комплекс</label>
          <select
            id="developer-program-complex"
            value={searchParameters.get('realEstateComplexId') ?? ''}
            disabled={!selectedCompanyGroup}
            onChange={(event) => updateParameters({
              realEstateComplexId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все ЖК группы</option>
            {options.realEstateComplexes.map((option) => (
              <option value={option.id} key={option.id}>{option.name}</option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="developer-program-bank">Банк</label>
          <select
            id="developer-program-bank"
            value={searchParameters.get('bankId') ?? ''}
            onChange={(event) => updateParameters({
              bankId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все банки</option>
            {options.banks.map((option) => (
              <option value={option.id} key={option.id}>{option.name}</option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="developer-program-canonical">Программа</label>
          <select
            id="developer-program-canonical"
            value={searchParameters.get('mortgageProgramId') ?? ''}
            onChange={(event) => updateParameters({
              mortgageProgramId: event.target.value || null,
              page: null,
            })}
          >
            <option value="">Все программы</option>
            {options.mortgagePrograms.map((option) => (
              <option value={option.id} key={option.id}>{option.name}</option>
            ))}
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="developer-program-status">Статус</label>
          <select
            id="developer-program-status"
            value={searchParameters.get('status') ?? 'all'}
            onChange={(event) => updateParameters({
              status: event.target.value,
              page: null,
            })}
          >
            <option value="all">Все</option>
            <option value="active">Активные</option>
            <option value="inactive">На стопе</option>
          </select>
        </div>
        <div className="sort-control">
          <label htmlFor="developer-program-ordering">Сортировка</label>
          <select
            id="developer-program-ordering"
            value={searchParameters.get('ordering') ?? 'companyGroup'}
            onChange={(event) => updateParameters({
              ordering: event.target.value,
              page: null,
            })}
          >
            {orderingOptions.map((option) => (
              <option value={option.value} key={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        {Object.values(options.truncated).some(Boolean) ? (
          <p className="filter-panel__notice" role="status">
            Часть значений скрыта из-за размера справочников. Уточните группу
            компаний или используйте сохранённый Django-интерфейс.
          </p>
        ) : null}
      </section>

      <div className="results-heading" aria-live="polite">
        <p>Программ: <strong>{formatInteger(totalCount)}</strong></p>
        {programQuery.isFetching ? <span>Обновляем…</span> : null}
      </div>
      {results.length === 0 ? (
        <EmptyState
          title="Программы застройщиков не найдены"
          description="Измените фильтры или добавьте новую программу."
          action={canManage ? (
            <Link className="button button--primary" to="/developer-programs/new">
              Добавить программу
            </Link>
          ) : undefined}
        />
      ) : (
        <>
          <div className="table-card property-table-wrapper">
            <table className="property-table developer-program-table">
              <caption className="visually-hidden">
                Список программ застройщиков
              </caption>
              <thead>
                <tr>
                  <th scope="col">Группа и область</th>
                  <th scope="col">Банк и программа</th>
                  <th scope="col">Ставка</th>
                  <th scope="col">Льготный период</th>
                  <th scope="col">Первый взнос</th>
                  <th scope="col">Лимит и срок</th>
                  <th scope="col">Корректировки</th>
                  <th scope="col">Статус</th>
                  {canManage ? <th scope="col"><span className="visually-hidden">Действия</span></th> : null}
                </tr>
              </thead>
              <tbody>
                {results.map((program) => (
                  <tr key={program.id}>
                    <td>
                      <Link className="text-link" to={`/developer-programs/${program.id}`}>
                        {program.companyGroupName}
                      </Link>
                      <small className="table-cell-note">{scopeName(program)}</small>
                    </td>
                    <td>
                      <strong>{program.bankName}</strong>
                      <small className="table-cell-note">{program.mortgageProgramName}</small>
                    </td>
                    <td>{valueOrDash(program.interestRate)}</td>
                    <td>
                      {program.gracePeriodMonths === null
                        ? '—'
                        : `${formatInteger(program.gracePeriodMonths)} мес.`}
                      <small className="table-cell-note">
                        {valueOrDash(program.gracePeriodInterestRate)}
                      </small>
                    </td>
                    <td>{valueOrDash(program.minimumInitialPaymentPercent)}</td>
                    <td>
                      {valueOrDash(program.maximumLoanAmount, formatCurrency)}
                      <small className="table-cell-note">
                        {program.maximumLoanTermYears === null
                          ? 'Срок не задан'
                          : `${formatInteger(program.maximumLoanTermYears)} лет`}
                      </small>
                    </td>
                    <td>
                      Удорожание: {valueOrDash(program.priceIncreasePercent)}
                      <small className="table-cell-note">
                        Дисконт: {valueOrDash(program.rateDiscountPercent)}
                      </small>
                    </td>
                    <td>
                      <span className={program.isActive
                        ? 'catalog-status'
                        : 'catalog-status catalog-status--inactive'}>
                        {program.isActive ? 'Активна' : 'На стопе'}
                      </span>
                    </td>
                    {canManage ? (
                      <td>
                        <div className="row-actions">
                          <Link
                            className="row-action"
                            to={`/developer-programs/${program.id}/edit`}
                            aria-label={`Редактировать: ${program.companyGroupName}, ${program.mortgageProgramName}`}
                          >✎</Link>
                          <button
                            className="row-action row-action--danger"
                            type="button"
                            aria-label={`Удалить: ${program.companyGroupName}, ${program.mortgageProgramName}`}
                            onClick={(event) => {
                              deleteMutation.reset()
                              deleteTriggerRef.current = event.currentTarget
                              setSelectedProgram(program)
                            }}
                          >×</button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="property-mobile-list">
            {results.map((program) => (
              <article className="property-mobile-card" key={program.id}>
                <div className="property-mobile-card__heading">
                  <div>
                    <span>{program.bankName}</span>
                    <h2><Link className="text-link" to={`/developer-programs/${program.id}`}>
                      {program.companyGroupName}
                    </Link></h2>
                  </div>
                  <span className={program.isActive
                    ? 'catalog-status'
                    : 'catalog-status catalog-status--inactive'}>
                    {program.isActive ? 'Активна' : 'На стопе'}
                  </span>
                </div>
                <p className="mortgage-program-mobile-condition">
                  {scopeName(program)} · {program.mortgageProgramName}
                </p>
                <dl>
                  <div><dt>Ставка</dt><dd>{valueOrDash(program.interestRate)}</dd></div>
                  <div><dt>Первый взнос</dt><dd>{valueOrDash(program.minimumInitialPaymentPercent)}</dd></div>
                  <div><dt>Максимальная сумма</dt><dd>{valueOrDash(program.maximumLoanAmount, formatCurrency)}</dd></div>
                  <div><dt>Удорожание</dt><dd>{valueOrDash(program.priceIncreasePercent)}</dd></div>
                </dl>
                <div className="property-mobile-card__actions">
                  <Link className="text-link" to={`/developer-programs/${program.id}`}>Открыть</Link>
                  {canManage ? (
                    <Link className="text-link" to={`/developer-programs/${program.id}/edit`}>Редактировать</Link>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
      {totalPages > 1 ? (
        <nav className="pagination" aria-label="Страницы программ застройщиков">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => updateParameters({ page: String(page - 1) })}
          ><span aria-hidden="true">←</span> Назад</button>
          <span>Страница <strong>{page}</strong> из {totalPages}</span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => updateParameters({ page: String(page + 1) })}
          >Далее <span aria-hidden="true">→</span></button>
        </nav>
      ) : null}
      {selectedProgram ? (
        <div
          className="confirmation-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target && !deleteMutation.isPending) {
              setSelectedProgram(null)
            }
          }}
        >
          <section
            className="confirmation-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="developer-program-delete-title"
            aria-describedby="developer-program-delete-description"
          >
            <span className="eyebrow">Подтверждение</span>
            <h2 id="developer-program-delete-title">Удалить программу?</h2>
            <p id="developer-program-delete-description">
              Условия «{selectedProgram.companyGroupName} —{' '}
              {selectedProgram.mortgageProgramName}» будут удалены.
            </p>
            {deleteMutation.isError ? (
              <p className="form-error" role="alert">
                Не удалось удалить программу. Повторите попытку.
              </p>
            ) : null}
            <div className="confirmation-dialog__actions">
              <button
                className="button button--secondary"
                type="button"
                ref={cancelButtonRef}
                disabled={deleteMutation.isPending}
                onClick={() => {
                  setSelectedProgram(null)
                  window.setTimeout(() => deleteTriggerRef.current?.focus(), 0)
                }}
              >Отмена</button>
              <button
                className="button button--danger"
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(selectedProgram.id)}
              >{deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}</button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
