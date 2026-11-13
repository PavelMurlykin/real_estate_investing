import { EmptyState } from '@/shared/ui/AsyncState'
import { Notice } from '@/shared/ui/Notice'
import { RemoteSelect } from '@/shared/ui/RemoteSelect'
import type { RealEstateComplexOptions } from '@/api/schemas'

import type { MetroAvailabilityFormRow } from './formTypes'

type RealEstateComplexMetroEditorProps = {
  rows: MetroAvailabilityFormRow[]
  options: RealEstateComplexOptions
  cityId: number | null
  error?: string
  onAdd: () => void
  onChange: (index: number, row: MetroAvailabilityFormRow) => void
  onRemove: (index: number) => void
}

export function RealEstateComplexMetroEditor({
  rows,
  options,
  cityId,
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
            disabled={!cityId}
            onClick={onAdd}
          >
            Добавить станцию
          </button>
        </div>
        {options.metroStations.length === 0 ? (
          <EmptyState compact title="Выберите город, чтобы получить список станций метро." />
        ) : null}
        {error ? <Notice as="p" tone="error" role="alert" className="form-error">{error}</Notice> : null}
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
                  <RemoteSelect searchable
                    dictionary="metro" label={`Станция метро ${rowNumber}`}
                    value={row.metroId} onChange={(value) => onChange(index, {
                        ...row,
                        metroId: value,
                      })}
                    initialOptions={(options.metroStations ?? []).map((option) => ({ id: option.id, label: `${option.station} · ${option.line}` }))}
                    truncated={options.truncated.metroStations}
                    filters={{ cityId }}
                    disabled={!cityId}
                    required
                  />
                  <RemoteSelect searchable
                    dictionary="transport-accessibility-types" label={"Способ"}
                    value={row.transportAccessibilityTypeId} onChange={(value) => onChange(index, {
                        ...row,
                        transportAccessibilityTypeId: value,
                      })}
                    initialOptions={(options.transportAccessibilityTypes ?? []).map((option) => ({ id: option.id, label: option.name }))}
                    truncated={options.truncated.transportAccessibilityTypes}
                    required
                  />
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
