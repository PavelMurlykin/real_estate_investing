import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { useRef, useState } from 'react'

import { ApiError } from '@/api/client'
import { importDeveloperRegistry } from '@/api/queries'
import { formatInteger } from '@/shared/lib/formatters'

const maximumSourceFileSize = 20 * 1024 * 1024
const supportedSourceFilePattern = /\.(csv|json|xlsx)$/i

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
    return firstMessage(details.sourceFile)
      ?? firstMessage(details.detail)
      ?? error.message
  }
  return 'Не удалось импортировать реестр. Повторите попытку.'
}

export function DeveloperRegistryImportPanel() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [clientError, setClientError] = useState<string | null>(null)
  const importMutation = useMutation({
    mutationFn: importDeveloperRegistry,
    onSuccess: async () => {
      setSourceFile(null)
      setClientError(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['developers'] }),
        queryClient.invalidateQueries({ queryKey: ['developer-options'] }),
        queryClient.invalidateQueries({ queryKey: ['company-groups'] }),
      ])
    },
  })

  const submitImport = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    importMutation.reset()
    if (!sourceFile) {
      setClientError('Выберите файл реестра ЕРЗ.')
      return
    }
    if (!supportedSourceFilePattern.test(sourceFile.name)) {
      setClientError('Поддерживаются файлы CSV, JSON и XLSX.')
      return
    }
    if (sourceFile.size > maximumSourceFileSize) {
      setClientError('Размер файла не должен превышать 20 МБ.')
      return
    }
    setClientError(null)
    importMutation.mutate(sourceFile)
  }

  const importResult = importMutation.data
  const errorMessage = clientError
    ?? (importMutation.isError
      ? importErrorMessage(importMutation.error)
      : null)

  return (
    <section
      className="catalog-import-card"
      aria-labelledby="developer-registry-import-title"
    >
      <div className="catalog-import-card__heading">
        <div>
          <span className="eyebrow">Обновление справочника</span>
          <h2 id="developer-registry-import-title">Импорт реестра ЕРЗ</h2>
          <p>
            Загрузите выгрузку реестра в формате CSV, JSON или XLSX.
            Повторная загрузка обновит существующих застройщиков без
            создания дубликатов.
          </p>
        </div>
        <span className="catalog-import-card__limit">До 20 МБ</span>
      </div>

      <form className="catalog-import-form" onSubmit={submitImport}>
        <div className="form-field catalog-import-form__file">
          <label htmlFor="developer-registry-source-file">Файл ЕРЗ</label>
          <input
            id="developer-registry-source-file"
            ref={fileInputRef}
            type="file"
            name="sourceFile"
            accept=".csv,.json,.xlsx,text/csv,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            aria-invalid={Boolean(errorMessage)}
            aria-describedby={errorMessage
              ? 'developer-registry-source-help developer-registry-source-error'
              : 'developer-registry-source-help'}
            disabled={importMutation.isPending}
            onChange={(event) => {
              setSourceFile(event.target.files?.[0] ?? null)
              setClientError(null)
              importMutation.reset()
            }}
          />
          <small id="developer-registry-source-help">
            Названия, реквизиты, группы компаний и регионы нормализуются
            существующим импортёром.
          </small>
          {errorMessage ? (
            <span
              id="developer-registry-source-error"
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
          className={importResult.skippedRecords || importResult.errors.length
            ? 'catalog-import-result catalog-import-result--warning'
            : 'catalog-import-result'}
          role="status"
        >
          <div className="catalog-import-result__heading">
            <div>
              <span className="eyebrow">Результат импорта</span>
              <h3>Реестр обработан</h3>
            </div>
            <strong>{formatInteger(importResult.sourceRecords)} записей</strong>
          </div>
          <dl className="catalog-import-metrics">
            <div>
              <dt>Нормализовано</dt>
              <dd>{formatInteger(importResult.normalizedRecords)}</dd>
            </div>
            <div>
              <dt>Создано</dt>
              <dd>{formatInteger(importResult.createdDevelopers)}</dd>
            </div>
            <div>
              <dt>Обновлено</dt>
              <dd>{formatInteger(importResult.updatedDevelopers)}</dd>
            </div>
            <div>
              <dt>Без изменений</dt>
              <dd>{formatInteger(importResult.unchangedDevelopers)}</dd>
            </div>
            <div>
              <dt>Создано ГК</dt>
              <dd>{formatInteger(importResult.createdCompanyGroups)}</dd>
            </div>
            <div>
              <dt>Связей с регионами</dt>
              <dd>{formatInteger(importResult.createdDeveloperRegionLinks)}</dd>
            </div>
            <div>
              <dt>Пропущено</dt>
              <dd>{formatInteger(importResult.skippedRecords)}</dd>
            </div>
          </dl>
          {importResult.errors.length ? (
            <details className="catalog-import-issues">
              <summary>Ошибки источника</summary>
              <ul>
                {importResult.errors.map((message) => (
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
