import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiErrorMessage } from '@/api/client'
import { locationImportJobQueryOptions, startNationalLocationImport } from '@/api/queries'
import { Notice } from '@/shared/ui/Notice'

const countLabels = {
  regions: 'Регионы',
  cities: 'Населённые пункты',
  districts: 'Административные районы',
} as const

export function NationalLocationUpdateAction() {
  const queryClient = useQueryClient()
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

  useEffect(() => {
    if (job?.status === 'completed' || job?.status === 'failed') {
      void queryClient.invalidateQueries({ predicate: (item) => [
        'location-catalogs', 'location-catalog', 'location-dictionaries', 'location-dictionary',
        'catalog-options', 'geography', 'overview', 'homepage-complexes',
      ].includes(String(item.queryKey[0])) })
    }
  }, [job?.id, job?.status, queryClient])

  return (
    <div className="location-update">
      <div className="location-update__action">
        <button className="button button--primary" type="button" disabled={pending}
          aria-busy={pending} onClick={() => mutation.mutate()}>
          Обновить данные
        </button>
      </div>
      {pending ? (
        <span className="visually-hidden" role="status">
          {job?.status === 'running' ? `Импорт выполняется. Обработано населённых пунктов ${job.processedCities}.` : 'Ожидаем запуска импорта.'}
        </span>
      ) : null}
      {!pending && !mutation.isError && job?.status === 'completed' ? (
        <Notice as="div" tone="success">
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
      {!pending && !mutation.isError && job?.status === 'failed' ? (
        <Notice tone="error">{job.errorMessage} Прогресс сохранён. Нажмите «Обновить данные», чтобы продолжить.</Notice>
      ) : null}
      {mutation.isError ? (
        <Notice tone="error">{apiErrorMessage(mutation.error) ?? 'Не удалось запустить импорт. Повторите попытку.'}</Notice>
      ) : null}
      {query.isError && !mutation.isError ? <Notice tone="error">Не удалось получить состояние импорта.</Notice> : null}
    </div>
  )
}
