import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useRef, useState } from 'react'

import { ApiError } from '@/api/client'
import { importDeveloperMortgagePrograms } from '@/api/queries'
import { formatInteger } from '@/shared/lib/formatters'

const maximumWorkbookSize = 15 * 1024 * 1024

function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstMessage(item)
      if (message) return message
    }
  }
  return null
}

function importErrorMessage(error: unknown): string {
  if (
    error instanceof ApiError
    && error.details
    && typeof error.details === 'object'
    && !Array.isArray(error.details)
  ) {
    const details = error.details as Record<string, unknown>
    return firstMessage(details.workbookFile)
      ?? firstMessage(details.detail)
      ?? error.message
  }
  return 'Не удалось импортировать файл. Повторите попытку.'
}

export function DeveloperMortgageProgramImportPanel() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [workbookFile, setWorkbookFile] = useState<File | null>(null)
  const [clientError, setClientError] = useState<string | null>(null)
  const importMutation = useMutation({
    mutationFn: importDeveloperMortgagePrograms,
    onSuccess: async () => {
      setWorkbookFile(null)
      setClientError(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await queryClient.invalidateQueries({
        queryKey: ['developer-mortgage-programs'],
      })
    },
  })

  const submitImport = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    importMutation.reset()
    if (!workbookFile) {
      setClientError('Выберите XLSX-файл для импорта.')
      return
    }
    if (!workbookFile.name.toLocaleLowerCase('ru-RU').endsWith('.xlsx')) {
      setClientError('Поддерживаются только файлы XLSX.')
      return
    }
    if (workbookFile.size > maximumWorkbookSize) {
      setClientError('Размер файла не должен превышать 15 МБ.')
      return
    }
    setClientError(null)
    importMutation.mutate(workbookFile)
  }

  const importResult = importMutation.data
  const errorMessage = clientError
    ?? (importMutation.isError
      ? importErrorMessage(importMutation.error)
      : null)

  return (
    <section
      className="developer-program-import-card"
      aria-labelledby="developer-program-import-title"
    >
      <div className="developer-program-import-card__heading">
        <div>
          <span className="eyebrow">Пакетное обновление</span>
          <h2 id="developer-program-import-title">Импорт из XLSX</h2>
          <p>
            Загрузите нормализованный файл с листом <code>db_import</code>.
            Справочники должны быть заполнены заранее.
          </p>
        </div>
        <span className="developer-program-import-card__limit">
          До 15 МБ · до 20&nbsp;000 строк
        </span>
      </div>

      <form className="developer-program-import-form" onSubmit={submitImport}>
        <div className="form-field developer-program-import-form__file">
          <label htmlFor="developer-program-workbook">Файл XLSX</label>
          <input
            id="developer-program-workbook"
            ref={fileInputRef}
            type="file"
            name="workbookFile"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            aria-invalid={Boolean(errorMessage)}
            aria-describedby={errorMessage
              ? 'developer-program-workbook-help developer-program-workbook-error'
              : 'developer-program-workbook-help'}
            disabled={importMutation.isPending}
            onChange={(event) => {
              setWorkbookFile(event.target.files?.[0] ?? null)
              setClientError(null)
              importMutation.reset()
            }}
          />
          <small id="developer-program-workbook-help">
            Повторный импорт обновляет найденные записи и не создаёт дубликаты.
          </small>
          {errorMessage ? (
            <span
              id="developer-program-workbook-error"
              className="field-error"
              role="alert"
            >
              {errorMessage}
            </span>
          ) : null}
        </div>
        <button
          className="button button--primary"
          type="submit"
          disabled={importMutation.isPending}
        >
          {importMutation.isPending ? 'Импортируем…' : 'Импортировать'}
        </button>
      </form>

      {importResult ? (
        <div
          className={importResult.skipped
            ? 'developer-program-import-result developer-program-import-result--warning'
            : 'developer-program-import-result'}
          role="status"
        >
          <div className="developer-program-import-result__heading">
            <div>
              <span className="eyebrow">Результат импорта</span>
              <h3>Файл обработан</h3>
            </div>
            <strong>{formatInteger(importResult.totalRows)} строк</strong>
          </div>
          <dl className="developer-program-import-metrics">
            <div><dt>Корректных</dt><dd>{formatInteger(importResult.parsedRows)}</dd></div>
            <div><dt>Создано</dt><dd>{formatInteger(importResult.created)}</dd></div>
            <div><dt>Обновлено</dt><dd>{formatInteger(importResult.updated)}</dd></div>
            <div><dt>Без изменений</dt><dd>{formatInteger(importResult.unchanged)}</dd></div>
            <div><dt>Пропущено</dt><dd>{formatInteger(importResult.skipped)}</dd></div>
            <div><dt>Дубликатов</dt><dd>{formatInteger(importResult.duplicateRows)}</dd></div>
            <div><dt>На стопе</dt><dd>{formatInteger(importResult.inactiveRows)}</dd></div>
            <div>
              <dt>С предупреждениями</dt>
              <dd>{formatInteger(importResult.sourceWarningRows)}</dd>
            </div>
          </dl>
          {importResult.issueMessages.length ? (
            <details className="developer-program-import-issues">
              <summary>Причины пропуска</summary>
              <ul>
                {importResult.issueMessages.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
