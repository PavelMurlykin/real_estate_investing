import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiErrorMessage } from '@/api/client'
import { importComplexCatalog } from '@/api/queries'

export function ComplexImport() {
  const [file, setFile] = useState<File | null>(null)
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: importComplexCatalog,
    onSuccess: () => queryClient.invalidateQueries({
      predicate: (query) => [
        'real-estate-complexes', 'real-estate-complex', 'real-estate-complex-options',
        'homepage-complexes', 'homepage', 'catalog-options', 'overview',
      ].includes(String(query.queryKey[0])),
    }),
  })
  return (
    <details className="bank-catalog-import">
      <summary>Импорт жилых комплексов из JSON</summary>
      <form onSubmit={(event) => {
        event.preventDefault()
        if (file && !mutation.isPending) mutation.mutate(file)
      }}>
        <label>Файл JSON
          <input type="file" accept=".json,application/json" disabled={mutation.isPending}
            onChange={(event) => { setFile(event.target.files?.[0] ?? null); mutation.reset() }} />
        </label>
        <button className="button button--secondary" type="submit" disabled={!file || mutation.isPending}>
          {mutation.isPending ? 'Загружаем…' : 'Импортировать'}
        </button>
      </form>
      {mutation.isError ? <p className="form-error" role="alert">{apiErrorMessage(mutation.error) ?? 'Не удалось импортировать файл.'}</p> : null}
      {mutation.isSuccess ? <p role="status">
        Создано ЖК {mutation.data.created}, обновлено {mutation.data.updated}, добавлено фото {mutation.data.photos}.
        Корпусов обработано {mutation.data.buildings}, станций {mutation.data.metro}.
      </p> : null}
    </details>
  )
}
