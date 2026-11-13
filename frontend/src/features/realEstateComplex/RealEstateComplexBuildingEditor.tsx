import { EmptyState } from '@/shared/ui/AsyncState'
import { Notice } from '@/shared/ui/Notice'
import { SearchableSelect } from '@/shared/ui/SearchableSelect'

import type { BuildingFormRow } from './formTypes'

type QuarterOption = {
  value: number
  label: string
}

type RealEstateComplexBuildingEditorProps = {
  rows: BuildingFormRow[]
  quarters: QuarterOption[]
  error?: string
  onAdd: () => void
  onChange: (index: number, row: BuildingFormRow) => void
  onRemove: (index: number) => void
}

export function RealEstateComplexBuildingEditor({
  rows,
  quarters,
  error,
  onAdd,
  onChange,
  onRemove,
}: RealEstateComplexBuildingEditorProps) {
  return (
    <section className="customer-form-section complex-form-section">
      <div className="customer-form-section__heading">
        <span aria-hidden="true">03</span>
        <div>
          <h2>Корпуса</h2>
          <p>Срок можно указать точной датой либо годом и кварталом.</p>
        </div>
      </div>
      <div className="complex-editor">
        <div className="complex-editor__toolbar">
          <p>Корпусов: {rows.length}</p>
          <button
            className="button button--secondary"
            type="button"
            onClick={onAdd}
          >
            Добавить корпус
          </button>
        </div>
        {error ? <Notice as="p" tone="error" role="alert" className="form-error">{error}</Notice> : null}
        {rows.length === 0 ? (
          <EmptyState compact title="Корпуса пока не добавлены." />
        ) : null}
        <div className="complex-editor-grid">
          {rows.map((row, index) => {
            const rowNumber = index + 1
            const fieldPrefix = `complex-building-${row.clientIdentifier}`
            return (
              <article className="complex-editor-card" key={row.clientIdentifier}>
                <div className="complex-editor-card__heading">
                  <h3>Корпус {rowNumber}</h3>
                  <button
                    className="text-button text-button--danger"
                    type="button"
                    disabled={row.propertyCount > 0}
                    title={row.propertyCount > 0
                      ? 'К корпусу привязаны объекты недвижимости'
                      : undefined}
                    onClick={() => onRemove(index)}
                  >
                    Удалить
                  </button>
                </div>
                {row.propertyCount > 0 ? (
                  <p className="complex-editor-card__notice">
                    Объектов недвижимости: {row.propertyCount}. Удаление
                    корпуса недоступно.
                  </p>
                ) : null}
                <div className="field-grid complex-editor-fields">
                  <label className="form-field" htmlFor={`${fieldPrefix}-number`}>
                    Номер корпуса {rowNumber} *
                    <input
                      id={`${fieldPrefix}-number`}
                      value={row.number}
                      maxLength={100}
                      required
                      onChange={(event) => onChange(index, {
                        ...row,
                        number: event.target.value,
                      })}
                    />
                  </label>
                  <label className="form-field" htmlFor={`${fieldPrefix}-address`}>
                    Адрес
                    <input
                      id={`${fieldPrefix}-address`}
                      value={row.address}
                      maxLength={255}
                      onChange={(event) => onChange(index, {
                        ...row,
                        address: event.target.value,
                      })}
                    />
                  </label>
                  <label className="form-field" htmlFor={`${fieldPrefix}-commissioning-date`}>
                    Дата ввода
                    <input
                      id={`${fieldPrefix}-commissioning-date`}
                      type="date"
                      value={row.commissioningDate}
                      onChange={(event) => onChange(index, {
                        ...row,
                        commissioningDate: event.target.value,
                        commissioningYear: event.target.value
                          ? '' : row.commissioningYear,
                        commissioningQuarter: event.target.value
                          ? '' : row.commissioningQuarter,
                      })}
                    />
                  </label>
                  <label className="form-field" htmlFor={`${fieldPrefix}-commissioning-year`}>
                    Год ввода
                    <input
                      id={`${fieldPrefix}-commissioning-year`}
                      type="number"
                      min="2000"
                      max="2100"
                      value={row.commissioningYear}
                      onChange={(event) => onChange(index, {
                        ...row,
                        commissioningDate: event.target.value
                          ? '' : row.commissioningDate,
                        commissioningYear: event.target.value,
                      })}
                    />
                  </label>
                  <SearchableSelect label="Квартал ввода" value={row.commissioningQuarter}
                    emptyLabel="Не указан"
                    options={quarters.map((quarter) => ({ value: String(quarter.value), label: quarter.label }))}
                    onChange={(value) => onChange(index, {
                      ...row,
                      commissioningDate: value ? '' : row.commissioningDate,
                      commissioningQuarter: value,
                    })} />
                  <label className="form-field" htmlFor={`${fieldPrefix}-keys-date`}>
                    Дата выдачи ключей
                    <input
                      id={`${fieldPrefix}-keys-date`}
                      type="date"
                      value={row.keyHandoverDate}
                      onChange={(event) => onChange(index, {
                        ...row,
                        keyHandoverDate: event.target.value,
                        keyHandoverYear: event.target.value
                          ? '' : row.keyHandoverYear,
                        keyHandoverQuarter: event.target.value
                          ? '' : row.keyHandoverQuarter,
                      })}
                    />
                  </label>
                  <label className="form-field" htmlFor={`${fieldPrefix}-keys-year`}>
                    Год выдачи ключей
                    <input
                      id={`${fieldPrefix}-keys-year`}
                      type="number"
                      min="2000"
                      max="2100"
                      value={row.keyHandoverYear}
                      onChange={(event) => onChange(index, {
                        ...row,
                        keyHandoverDate: event.target.value
                          ? '' : row.keyHandoverDate,
                        keyHandoverYear: event.target.value,
                      })}
                    />
                  </label>
                  <SearchableSelect label="Квартал выдачи ключей" value={row.keyHandoverQuarter}
                    emptyLabel="Не указан"
                    options={quarters.map((quarter) => ({ value: String(quarter.value), label: quarter.label }))}
                    onChange={(value) => onChange(index, {
                      ...row,
                      keyHandoverDate: value ? '' : row.keyHandoverDate,
                      keyHandoverQuarter: value,
                    })} />
                </div>
                <label className="developer-active-field">
                  <input
                    type="checkbox"
                    checked={row.isActive}
                    onChange={(event) => onChange(index, {
                      ...row,
                      isActive: event.target.checked,
                    })}
                  />
                  <span>Корпус активен</span>
                </label>
              </article>
            )
          })}
        </div>
      </div>
    </section>
  )
}
