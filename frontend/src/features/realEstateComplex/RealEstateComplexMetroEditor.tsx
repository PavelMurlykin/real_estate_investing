import type { RealEstateComplexOptions } from '@/api/schemas'

import type { MetroAvailabilityFormRow } from './formTypes'

type RealEstateComplexMetroEditorProps = {
  rows: MetroAvailabilityFormRow[]
  options: RealEstateComplexOptions
  error?: string
  onAdd: () => void
  onChange: (index: number, row: MetroAvailabilityFormRow) => void
  onRemove: (index: number) => void
}

export function RealEstateComplexMetroEditor({
  rows,
  options,
  error,
  onAdd,
  onChange,
  onRemove,
}: RealEstateComplexMetroEditorProps) {
  return (
    <section className="customer-form-section complex-form-section">
      <div className="customer-form-section__heading">
        <span aria-hidden="true">04</span>
        <div>
          <h2>Доступность метро</h2>
          <p>Добавьте ближайшие станции, способ и время в пути.</p>
        </div>
      </div>
      <div className="complex-editor">
        <div className="complex-editor__toolbar">
          <p>Станций: {rows.length}</p>
          <button
            className="button button--secondary"
            type="button"
            disabled={options.metroStations.length === 0}
            onClick={onAdd}
          >
            Добавить станцию
          </button>
        </div>
        {options.metroStations.length === 0 ? (
          <p className="complex-editor__empty">
            Выберите город, чтобы получить список станций метро.
          </p>
        ) : null}
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <div className="complex-editor-grid complex-editor-grid--metro">
          {rows.map((row, index) => {
            const rowNumber = index + 1
            const fieldPrefix = `complex-metro-${row.clientIdentifier}`
            const selectedStation = options.metroStations.find(
              (station) => station.id.toString() === row.metroId,
            )
            return (
              <article className="complex-editor-card" key={row.clientIdentifier}>
                <div className="complex-editor-card__heading">
                  <h3>Станция {rowNumber}</h3>
                  <button
                    className="text-button text-button--danger"
                    type="button"
                    onClick={() => onRemove(index)}
                  >
                    Удалить
                  </button>
                </div>
                <div className="field-grid complex-editor-fields">
                  <label className="form-field" htmlFor={`${fieldPrefix}-station`}>
                    Станция метро {rowNumber} *
                    <select
                      id={`${fieldPrefix}-station`}
                      value={row.metroId}
                      required
                      onChange={(event) => onChange(index, {
                        ...row,
                        metroId: event.target.value,
                      })}
                    >
                      <option value="">Выберите станцию</option>
                      {options.metroStations.map((station) => (
                        <option key={station.id} value={station.id}>
                          {station.station} · {station.line}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="form-field" htmlFor={`${fieldPrefix}-transport`}>
                    Способ *
                    <select
                      id={`${fieldPrefix}-transport`}
                      value={row.transportAccessibilityTypeId}
                      required
                      onChange={(event) => onChange(index, {
                        ...row,
                        transportAccessibilityTypeId: event.target.value,
                      })}
                    >
                      <option value="">Выберите способ</option>
                      {options.transportAccessibilityTypes.map((type) => (
                        <option key={type.id} value={type.id}>{type.name}</option>
                      ))}
                    </select>
                  </label>
                  <label className="form-field" htmlFor={`${fieldPrefix}-time`}>
                    Время, мин. *
                    <input
                      id={`${fieldPrefix}-time`}
                      type="number"
                      min="1"
                      max="1440"
                      value={row.walkingTimeMinutes}
                      required
                      onChange={(event) => onChange(index, {
                        ...row,
                        walkingTimeMinutes: event.target.value,
                      })}
                    />
                  </label>
                </div>
                {selectedStation ? (
                  <p className="complex-metro-line">
                    <span
                      className="metro-dot"
                      style={{ backgroundColor: selectedStation.lineColor }}
                      aria-hidden="true"
                    />
                    {selectedStation.line}
                  </p>
                ) : null}
                <label className="developer-active-field">
                  <input
                    type="checkbox"
                    checked={row.isActive}
                    onChange={(event) => onChange(index, {
                      ...row,
                      isActive: event.target.checked,
                    })}
                  />
                  <span>Связь со станцией активна</span>
                </label>
              </article>
            )
          })}
        </div>
      </div>
    </section>
  )
}
