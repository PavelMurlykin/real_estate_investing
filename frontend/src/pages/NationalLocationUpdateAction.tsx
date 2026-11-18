import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiErrorMessage } from '@/api/client'
import { locationImportJobQueryOptions, startNationalLocationImport } from '@/api/queries'
import { Notice } from '@/shared/ui/Notice'

const countLabels = {
  regions: 'Регионы',
  cities: 'Населённые пункты',
  districts: 'Административные районы',
} as const

export function NationalLocationUpdateAction({ children }: { children?: ReactNode }) {
  const queryClient = useQueryClient()
  const actionRef = useRef<HTMLButtonElement>(null)
  const [showFeedback, setShowFeedback] = useState(false)
  const query = useQuery({
    ...locationImportJobQueryOptions,
    refetchInterval: (state) => ['queued', 'running'].includes(state.state.data?.job?.status ?? '') ? 2000 : false,
    refetchIntervalInBackground: true,
  })
  const job = query.data?.job
  const mutation = useMutation({
    mutationFn: startNationalLocationImport,
    onSuccess: (data) => { queryClient.setQueryData(locationImportJobQueryOptions.queryKey, data) },
    retry: false,
  })
  const active = job?.status === 'queued' || job?.status === 'running'
  const pending = active || mutation.isPending
  const showJob = showFeedback && !pending && job && job.id === mutation.data?.job?.id
  const dismiss = () => setShowFeedback(false)

  useEffect(() => {
    if (job?.status === 'completed' || job?.status === 'failed') {
      void queryClient.invalidateQueries({ predicate: (item) => [
        'location-catalogs', 'location-catalog', 'location-dictionaries', 'location-dictionary',
        'catalog-options', 'geography', 'legacy-location', 'overview', 'homepage-complexes',
      ].includes(String(item.queryKey[0])) })
    }
  }, [job?.id, job?.status, queryClient])

  return (
    <div className="location-update">
      <div className="location-update__toolbar">
        {children}
        <div className="location-update__action">
          <button ref={actionRef} className="button button--primary" type="button" disabled={pending}
            aria-busy={pending} onClick={() => { setShowFeedback(true); mutation.mutate() }}>
            Обновить данные
          </button>
        </div>
      </div>
      {pending ? (
        <span className="visually-hidden" role="status">
          {job?.status === 'running' ? `Импорт выполняется. Обработано населённых пунктов ${job.processedCities}.` : 'Ожидаем запуска импорта.'}
        </span>
      ) : null}
      {showJob && job?.status === 'completed' ? (
        <Notice as="div" tone="success" onDismiss={dismiss} returnFocusRef={actionRef}>
          <p>Справочники обновлены. Обработано населённых пунктов {job.processedCities}.
            {job.sourceVersion ? ` Версия ГАР ${job.sourceVersion}.` : ''}</p>
          {Object.entries(job.counts).map(([key, counts]) => counts ? (
            <p key={key}>{countLabels[key as keyof typeof countLabels]} — добавлено {counts.created},
              обновлено {counts.updated}, без изменений {counts.unchanged}.</p>
          ) : null)}
          {job.coverage.withoutDistricts ? <p>В источнике нет сведений о районах для {job.coverage.withoutDistricts} городов. Существующие районы сохранены.</p> : null}
          {job.coverage.unresolvedCities?.length ? <p>Не удалось сопоставить с Wikidata {job.coverage.unresolvedCities.length} городов. Они загружены из российского справочника.</p> : null}
        </Notice>
      ) : null}
      {showJob && job?.status === 'failed' ? (
        <Notice tone="error" onDismiss={dismiss} returnFocusRef={actionRef}>{job.errorMessage} Прогресс сохранён. Нажмите «Обновить данные», чтобы продолжить.</Notice>
      ) : null}
      {showFeedback && mutation.isError ? (
        <Notice tone="error" onDismiss={dismiss} returnFocusRef={actionRef}>{apiErrorMessage(mutation.error) ?? 'Не удалось запустить импорт. Повторите попытку.'}</Notice>
      ) : null}
      {showFeedback && query.isError && !mutation.isError && !showJob
        ? <Notice tone="error" onDismiss={dismiss} returnFocusRef={actionRef}>Не удалось получить состояние импорта.</Notice> : null}
    </div>
  )
}
