import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId } from 'react'

import { apiErrorMessage } from '@/api/client'
import { importMetroStations } from '@/api/queries'
import { Notice } from '@/shared/ui/Notice'

export function MetroUpdateAction({ systemId }: { systemId: string }) {
  const queryClient = useQueryClient()
  const hintId = useId()
  const mutation = useMutation({
    mutationFn: () => importMetroStations(Number(systemId)),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        predicate: (query) => ['location-dictionaries', 'location-dictionary', 'catalog-options']
          .includes(String(query.queryKey[0])),
      })
    },
    retry: false,
  })

  const result = mutation.data
  return (
    <div className="location-update">
      <div className="location-update__action" title={!systemId ? 'Выберите систему метро в фильтре' : undefined}>
        <button className="button button--primary" type="button"
          disabled={!systemId || mutation.isPending} aria-busy={mutation.isPending}
          aria-describedby={!systemId ? hintId : undefined}
          onClick={() => mutation.mutate()}>
          Обновить данные
        </button>
      </div>
      <span id={hintId} className="visually-hidden">Выберите систему метро в фильтре.</span>
      {mutation.isPending ? <span className="visually-hidden" role="status">Импорт метро выполняется.</span> : null}
      {result ? (
        <Notice tone="success">
          Станции обновлены. Добавлено {result.created}, обновлено {result.updated}, без изменений {result.unchanged},
          пропущено {result.skipped}. Линий добавлено {result.lines.created}, обновлено {result.lines.updated}.
        </Notice>
      ) : null}
      {mutation.isError ? (
        <Notice tone="error">{apiErrorMessage(mutation.error) ?? 'Не удалось обновить метро. Повторите попытку.'}</Notice>
      ) : null}
    </div>
  )
}
