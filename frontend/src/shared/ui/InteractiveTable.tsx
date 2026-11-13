import { TableScrollArea } from '@/shared/ui/TableScrollArea'
import { EmptyState } from '@/shared/ui/AsyncState'
import type { Key, ReactNode } from 'react'
import { useId, useState } from 'react'

type TableColumn<Row> = {
  id: string
  label: string
  value: (row: Row) => string | number | null | undefined
  searchValue?: (row: Row) => string
  render?: (row: Row) => ReactNode
}

type InteractiveTableProps<Row> = {
  rows: readonly Row[]
  columns: TableColumn<Row>[]
  getRowKey: (row: Row) => Key
  caption: string
  className?: string
  previewLimit?: number
}

function searchText(value: unknown) {
  return String(value ?? '').normalize('NFKC').toLocaleLowerCase('ru-RU').replace(/[\s₽%]/g, '').replace(/,/g, '.')
}

export function InteractiveTable<Row>({ rows, columns, getRowKey, caption, className = 'property-table', previewLimit }: InteractiveTableProps<Row>) {
  const identifier = useId()
  const [search, setSearch] = useState('')
  const [ordering, setOrdering] = useState({ field: '', descending: false })
  const query = searchText(search)
  const filteredRows = query ? rows.filter((row) => columns.some((column) => (
    searchText(column.value(row)).includes(query) || (column.searchValue && searchText(column.searchValue(row)).includes(query))
  ))) : rows
  const selectedColumn = columns.find((column) => column.id === ordering.field)
  const sortedRows = selectedColumn ? [...filteredRows].sort((left, right) => {
    const leftValue = selectedColumn.value(left)
    const rightValue = selectedColumn.value(right)
    if (leftValue == null) return rightValue == null ? 0 : 1
    if (rightValue == null) return -1
    const comparison = typeof leftValue === 'number' && typeof rightValue === 'number'
      ? leftValue - rightValue : String(leftValue).localeCompare(String(rightValue), 'ru-RU', { numeric: true })
    return ordering.descending ? -comparison : comparison
  }) : filteredRows
  const visibleRows = previewLimit && !query ? sortedRows.slice(0, previewLimit) : sortedRows
  return (
    <div className="interactive-table">
      <label className="form-field" htmlFor={identifier}>
        <span>Поиск в таблице</span>
        <input id={identifier} type="search" aria-label={`Поиск в таблице: ${caption}`} value={search}
          placeholder="Введите значение" onChange={(event) => setSearch(event.target.value)} />
      </label>
      {query ? <p className="table-search-count" role="status">Найдено строк: {filteredRows.length}</p> : null}
      <TableScrollArea className="interactive-table__scroll" label={caption}>
        <table className={className}>
          <caption className="visually-hidden">{caption}</caption>
          <thead><tr>{columns.map((column) => {
            const active = ordering.field === column.id
            return (
              <th key={column.id} scope="col" aria-sort={active ? ordering.descending ? 'descending' : 'ascending' : 'none'}>
                <button type="button" className="sortable-header" onClick={() => setOrdering({ field: column.id, descending: active && !ordering.descending })}>
                  <span>{column.label}</span><span aria-hidden="true">{active ? ordering.descending ? '↓' : '↑' : '↕'}</span>
                </button>
              </th>
            )
          })}</tr></thead>
          <tbody>{visibleRows.length ? visibleRows.map((row) => (
            <tr key={getRowKey(row)}>{columns.map((column) => <td key={column.id}>{column.render ? column.render(row) : column.value(row)}</td>)}</tr>
          )) : <tr><td colSpan={columns.length}><EmptyState compact title="Нет строк, соответствующих поиску."
            action={query ? <button type="button" className="button button--secondary" onClick={() => setSearch('')}>Сбросить поиск</button> : undefined} />
          </td></tr>}</tbody>
        </table>
      </TableScrollArea>
    </div>
  )
}
