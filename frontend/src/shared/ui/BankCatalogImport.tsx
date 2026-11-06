import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'

import { ApiError } from '@/api/client'
import { importBankCatalog } from '@/api/queries'

const catalogQueries = new Set([
  'banks', 'bank', 'bank-options', 'mortgage-programs', 'mortgage-program',
  'mortgage-program-options', 'mortgage-options', 'mortgage-developer-options',
  'developer-mortgage-program-options', 'overview',
])

export function BankCatalogImport({ section }: { section: 'banks' | 'mortgage-programs' }) {
  const inputId = useId()
  const [file, setFile] = useState<File | null>(null)
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (upload: File) => importBankCatalog(section, upload),
    onSuccess: () => queryClient.invalidateQueries({
      predicate: (query) => catalogQueries.has(String(query.queryKey[0])),
    }),
  })
  const details = mutation.error instanceof ApiError ? mutation.error.details : null
  const error = details && typeof details === 'object'
    && 'detail' in details && typeof details.detail === 'string'
    ? details.detail : 'Не удалось импортировать файл. Повторите попытку.'

  return (
    <details className="bank-catalog-import">
      <summary>{section === 'banks' ? 'Импорт банков из JSON' : 'Импорт ипотечных программ из JSON'}</summary>
      <form onSubmit={(event) => {
        event.preventDefault()
        if (file && !mutation.isPending) mutation.mutate(file)
      }}>
        <label className="visually-hidden" htmlFor={inputId}>Файл JSON</label>
        <input
          id={inputId}
          type="file"
          accept=".json,application/json"
          disabled={mutation.isPending}
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null)
            mutation.reset()
          }}
        />
        <button className="button button--secondary" type="submit" disabled={!file || mutation.isPending}>
          {mutation.isPending ? 'Загружаем…' : 'Импортировать'}
        </button>
      </form>
      {mutation.isError ? <p className="form-error" role="alert">{error}</p> : null}
      {mutation.isSuccess ? (
        <p role="status">
          Создано {mutation.data.created}, обновлено {mutation.data.updated}, без изменений {mutation.data.unchanged}.
        </p>
      ) : null}
    </details>
  )
}
