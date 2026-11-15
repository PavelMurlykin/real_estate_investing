import { useState, type FormEvent } from 'react'

import { ModalDialog } from '@/shared/ui/ModalDialog'
import { NumberField } from '@/shared/ui/NumberField'
import { isValidAmountIncrement, percentIncrements, type MortgageModifiers } from './modifiers'

export function MortgageSettingsDialog({ modifiers, onSave, onClose }: {
  modifiers: MortgageModifiers
  onSave: (value: MortgageModifiers) => void
  onClose: () => void
}) {
  const [amount, setAmount] = useState(String(modifiers.amount))
  const [percent, setPercent] = useState(modifiers.percent)
  const [error, setError] = useState('')

  const save = (event: FormEvent) => {
    event.preventDefault()
    if (!isValidAmountIncrement(Number(amount))) {
      setError('Укажите целое число от 1 до 1 000 000 000 ₽.')
      return
    }
    onSave({ amount: Number(amount), percent })
  }

  return (
    <ModalDialog role="dialog" className="mortgage-settings" labelledBy="mortgage-settings-heading"
      describedBy="mortgage-settings-description" onClose={onClose}>
      <h2 id="mortgage-settings-heading">Настройки калькулятора</h2>
      <p id="mortgage-settings-description">Задайте шаг кнопок −/+ и клавиш ↑/↓ для числовых полей калькулятора.</p>
      <form noValidate onSubmit={save}>
        <h3>Модификаторы</h3>
        <NumberField label="Шаг изменения суммы, ₽" value={amount} min="1" max="1000000000"
          step="1" increment={10_000} required onValueChange={(value) => { setAmount(value); setError('') }}
          aria-invalid={Boolean(error)} aria-describedby={error ? 'modifier-amount-help modifier-amount-error' : 'modifier-amount-help'}>
          <small id="modifier-amount-help">Стоимость объекта, взнос, скидка или удорожание и суммы траншей.</small>
          {error ? <span className="field-error" id="modifier-amount-error" role="alert">{error}</span> : null}
        </NumberField>
        <fieldset className="mortgage-settings__percent">
          <legend>Шаг изменения взноса и ставки</legend>
          <p>Для всех полей в процентах, включая корректировку цены и транши. Шаг указан в процентных пунктах.</p>
          <div className="mortgage-settings__options">
            {percentIncrements.map((option) => (
              <label key={option}>
                <input type="radio" name="percent-increment" value={option} checked={percent === option}
                  onChange={() => setPercent(option)} />
                {option.toLocaleString('ru-RU')} п.п.
              </label>
            ))}
          </div>
        </fieldset>
        <p className="mortgage-settings__hint">Настройки общие для рыночного и траншевого режимов и сохраняются в этом браузере. Срок и этаж меняются на 1, площадь — на 0,01 м².</p>
        <div className="confirmation-dialog__actions">
          <button className="button button--secondary" type="button" onClick={onClose}>Отмена</button>
          <button className="button button--primary" type="submit">Сохранить</button>
        </div>
      </form>
    </ModalDialog>
  )
}
