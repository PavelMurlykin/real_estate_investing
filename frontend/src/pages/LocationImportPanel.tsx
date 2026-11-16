import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiErrorMessage } from '@/api/client'
import { importLocationDictionary } from '@/api/queries'
import type { LocationDictionaryKey } from '@/api/schemas'
import { Notice } from '@/shared/ui/Notice'

type Props = {
  dictionaryKey: LocationDictionaryKey
  regionId: string
  cityId: string
}

export function LocationImportPanel({ dictionaryKey, regionId, cityId }: Props) {
  const queryClient = useQueryClient()
  const needsCity = dictionaryKey === 'districts' || dictionaryKey === 'metro'
  const needsRegion = dictionaryKey !== 'regions'
  const canImport = (!needsRegion || Boolean(regionId)) && (!needsCity || Boolean(cityId))
  const mutation = useMutation({
    mutationFn: () => importLocationDictionary(dictionaryKey, {
      ...(needsRegion ? { regionId: Number(regionId) } : {}),
      ...(needsCity ? { cityId: Number(cityId) } : {}),
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        predicate: (query) => [
          'location-dictionaries', 'location-dictionary',
          'location-dictionary-options', 'catalog-options',
        ].includes(String(query.queryKey[0])),
      })
    },
    retry: false,
  })

  return (
    <section className="filter-panel location-import-panel" aria-labelledby="location-import-title">
      <div>
        <h2 id="location-import-title">Импорт локаций России</h2>
        <p>
          {dictionaryKey === 'regions'
            ? 'Загрузите регионы России, затем перейдите к городам выбранного региона.'
            : needsCity
              ? 'Выберите российские регион и город в фильтрах ниже. При необходимости загрузите их на вкладках «Регионы» и «Города».'
              : 'Выберите российский регион в фильтре ниже. При необходимости загрузите его на вкладке «Регионы».'}
          {' '}Повторный импорт добавляет новые записи и обновляет существующие.
        </p>
        <p className="field-hint">
          Источники: <a href="https://github.com/hflabs/city" target="_blank" rel="noreferrer">HFLabs</a>,{' '}
          <a href="https://www.wikidata.org/wiki/Wikidata:Data_access" target="_blank" rel="noreferrer">Wikidata</a> и Википедия.
          {' '}Полнота зависит от открытых справочников. Записи не удаляются; выбранный вручную статус сохраняется.
        </p>
      </div>
      <button
        type="button"
        className="button button--primary"
        disabled={!canImport || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? 'Импортируем…' : 'Импортировать из API'}
      </button>
      <div className="location-import-panel__feedback" aria-live="polite" aria-atomic="true" hidden={!mutation.isPending && !mutation.data && !mutation.isError}>
        {mutation.isPending ? <p role="status">Получаем данные открытых справочников…</p> : null}
        {mutation.data ? (
          <Notice as="p" tone="success" role="status">
            Импорт завершён. Добавлено: {mutation.data.created}; обновлено: {mutation.data.updated};
            {' '}без изменений: {mutation.data.unchanged}; пропущено: {mutation.data.skipped}.
            {dictionaryKey === 'metro' ? ` Линии: добавлено ${mutation.data.lines.created}, обновлено ${mutation.data.lines.updated}.` : ''}
          </Notice>
        ) : null}
        {mutation.isError ? (
          <Notice as="p" tone="error" role="alert">
            {apiErrorMessage(mutation.error) ?? 'Не удалось импортировать локации. Повторите попытку.'}
          </Notice>
        ) : null}
      </div>
    </section>
  )
}
