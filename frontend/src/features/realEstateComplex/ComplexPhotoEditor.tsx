import { Notice } from '@/shared/ui/Notice'
import { useEffect, useRef } from 'react'

import type { RealEstateComplexDetail } from '@/api/schemas'
import { complexPhotoItems } from './photoItems'

function UploadedPhotoPreview({ file, number }: { file: File; number: number }) {
  const imageRef = useRef<HTMLImageElement>(null)
  useEffect(() => {
    const url = URL.createObjectURL(file)
    if (imageRef.current) imageRef.current.src = url
    return () => URL.revokeObjectURL(url)
  }, [file])
  return <img ref={imageRef} alt={'Фото ЖК ' + number} />
}

export function ComplexPhotoEditor({ complex, files, primarySelection, removedPhotoKeys, onRemovalChange, onFilesChange, onPrimaryChange, disabled, error }: {
  complex?: RealEstateComplexDetail
  files: File[]
  primarySelection: string
  removedPhotoKeys: string[]
  onRemovalChange: (keys: string[]) => void
  onFilesChange: (files: File[]) => void
  onPrimaryChange: (selection: string) => void
  disabled: boolean
  error?: string
}) {
  const existing = complexPhotoItems(complex)
  const currentPrimary = existing.find((photo) => photo.isPrimary)
  const requestedSelection = primarySelection || (currentPrimary
    ? 'existing:' + (currentPrimary.id ?? 'legacy')
    : files.length ? 'new:0' : '')
  const choices = [
    ...existing.map((photo) => ({ value: 'existing:' + (photo.id ?? 'legacy'), url: photo.url, file: null, removed: removedPhotoKeys.includes('existing:' + (photo.id ?? 'legacy')) })),
    ...files.map((file, index) => ({ value: 'new:' + index, url: null, file, removed: false })),
  ]
  const currentSelection = choices.find((choice) => !choice.removed && choice.value === requestedSelection)?.value
    ?? choices.find((choice) => !choice.removed)?.value ?? ''

  const toggleRemoval = (value: string, index: number) => {
    if (removedPhotoKeys.includes(value)) {
      onRemovalChange(removedPhotoKeys.filter((key) => key !== value))
      return
    }
    onRemovalChange([...removedPhotoKeys, value])
    if (currentSelection === value) {
      const next = [...choices.slice(index + 1), ...choices.slice(0, index)]
        .find((choice) => !choice.removed)
      onPrimaryChange(next?.value ?? '')
    }
  }

  return (
    <fieldset className="property-upload-card complex-photo-upload form-field--wide" disabled={disabled}>
      <legend>Фотографии ЖК</legend>
      <p id="complex-photo-hint">До 30 фотографий. Главное фото отображается на главной странице. Изменения сохранятся вместе с ЖК.</p>
      <div className="complex-gallery">
        {choices.map((choice, index) => (
          <div className={'complex-photo-choice' + (choice.removed ? ' complex-photo-choice--removed' : '')} key={choice.value}>
            {choice.url ? <img src={choice.url} alt={'Фото ЖК ' + (index + 1)} loading="lazy" /> : null}
            {choice.file ? <UploadedPhotoPreview file={choice.file} number={index + 1} /> : null}
            <label><input type="radio" name="primary-complex-photo" value={choice.value}
              aria-label={'Главное фото ' + (index + 1)}
              disabled={disabled || choice.removed}
              checked={currentSelection === choice.value} onChange={() => onPrimaryChange(choice.value)} />
              Главное фото {index + 1}
            </label>
            {choice.file ? <small>{choice.file.name}</small> : null}
            {complex && !choice.file ? <>
              <button type="button" className="text-button text-button--danger"
                aria-label={(choice.removed ? 'Восстановить фото ' : 'Удалить фото ') + (index + 1)}
                onClick={() => toggleRemoval(choice.value, index)}>
                {choice.removed ? 'Восстановить' : 'Удалить фото'}
              </button>
              {choice.removed ? <small>Будет удалено при сохранении</small> : null}
            </> : null}
          </div>
        ))}
      </div>
      {removedPhotoKeys.length ? <Notice as="p" tone="info" role="status" >Будет удалено фото: {removedPhotoKeys.length}. {currentSelection ? 'Главное фото отмечено ниже снимка.' : 'Фотографий не останется.'}</Notice> : null}
      <label className="form-field" htmlFor="complex-photos">Добавить фотографии
        <input id="complex-photos" type="file" multiple accept="image/jpeg,image/png,image/gif,image/webp"
          aria-describedby={'complex-photo-hint' + (error ? ' complex-photo-error' : '')}
          aria-invalid={Boolean(error)} onChange={(event) => {
            onFilesChange(Array.from(event.target.files ?? []))
            onPrimaryChange('')
          }} />
      </label>
      {error ? <Notice as="p" tone="error" role="alert" id="complex-photo-error" className="field-error">{error}</Notice> : null}
    </fieldset>
  )
}
