type PaginationProps = {
  label: string
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function Pagination({ label, page, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null
  return (
    <nav className="pagination" aria-label={label}>
      <button type="button" className="button button--secondary" disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}>
        <span aria-hidden="true">←</span> Назад
      </button>
      <span className="pagination__status" aria-live="polite" aria-atomic="true">
        Страница <strong>{page}</strong> из {totalPages}
      </span>
      <button type="button" className="button button--secondary" disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}>
        Далее <span aria-hidden="true">→</span>
      </button>
    </nav>
  )
}
