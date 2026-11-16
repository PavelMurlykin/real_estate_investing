import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiErrorMessage } from '@/api/client'
import { locationImportJobQueryOptions, startNationalLocationImport } from '@/api/queries'
import { Notice } from '@/shared/ui/Notice'

export function NationalLocationImportPanel() {
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
  useEffect(() => {
    if (job?.status === 'completed') {
      void queryClient.invalidateQueries({ predicate: (item) => [
        'location-dictionaries', 'location-dictionary-options', 'catalog-options',
      ].includes(String(item.queryKey[0])) })
    }
  }, [job?.id, job?.status, queryClient])

  return (
    <section className="filter-panel location-national-import" aria-labelledby="national-import-title">
      <h2 id="national-import-title">Все города и районы России</h2>
      <p>Один запуск загружает регионы, все города России и доступные в источнике городские районы. Фильтры ниже не ограничивают импорт. Работа продолжается после закрытия страницы.</p>
      <button className="button button--primary" type="button" disabled={active || mutation.isPending}
        onClick={() => mutation.mutate()}>
        {active || mutation.isPending ? 'Общий импорт выполняется…' : job?.status === 'failed'
          ? 'Продолжить импорт России' : 'Импортировать все города и районы России'}
      </button>
      {job ? (
        <div aria-live="polite" aria-atomic="true">
          {active ? <p role="status">{job.status === 'queued' ? 'Ожидаем запуска.' : job.phase === 'preparing' ? 'Подготавливаем сведения о районах.' : 'Импортируем районы.'} Городов обработано: {job.processedCities} из {job.totalCities}. {job.currentCity}</p> : null}
          {active && job.totalCities > 0 ? <progress aria-label="Прогресс общего импорта" value={job.processedCities} max={job.totalCities} /> : null}
          {job.status === 'completed' ? <Notice as="p" tone="success" role="status">Общий импорт завершён. Обработано городов: {job.processedCities}.</Notice> : null}
          {Object.entries(job.counts).map(([key, counts]) => counts ? (
            <p key={key}>{({ regions: 'Регионы', cities: 'Города', districts: 'Районы' })[key as 'regions' | 'cities' | 'districts']}: добавлено {counts.created}, обновлено {counts.updated}, без изменений {counts.unchanged}.</p>
          ) : null)}
          {job.coverage.withoutDistricts ? <p className="field-hint">Без сведений о районах в источнике: {job.coverage.withoutDistricts} городов. Существующие районы сохранены.</p> : null}
          {job.coverage.unresolvedCities?.length ? <p className="field-hint">Не удалось однозначно сопоставить с Wikidata: {job.coverage.unresolvedCities.length} городов. Все города загружены из российского справочника.</p> : null}
          {job.status === 'failed' ? <Notice as="p" tone="error" role="alert">{job.errorMessage} Прогресс сохранён. Нажмите «Продолжить импорт России».</Notice> : null}
        </div>
      ) : null}
      {mutation.isError ? <Notice as="p" tone="error" role="alert">{apiErrorMessage(mutation.error) ?? 'Не удалось запустить импорт. Повторите попытку.'}</Notice> : null}
      {query.isError ? <Notice as="p" tone="error" role="alert">Не удалось получить состояние импорта. <button type="button" className="text-button" onClick={() => { void query.refetch() }}>Обновить состояние</button></Notice> : null}
    </section>
  )
}
