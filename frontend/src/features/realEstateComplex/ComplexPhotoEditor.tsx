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

export function ComplexPhotoEditor({ complex, files, primarySelection, onFilesChange, onPrimaryChange, disabled, error }: {
  complex?: RealEstateComplexDetail
  files: File[]
  primarySelection: string
  onFilesChange: (files: File[]) => void
  onPrimaryChange: (selection: string) => void
  disabled: boolean
  error?: string
}) {
  const existing = complexPhotoItems(complex)
  const currentPrimary = existing.find((photo) => photo.isPrimary)
  const currentSelection = primarySelection || (currentPrimary
    ? 'existing:' + (currentPrimary.id ?? 'legacy')
    : files.length ? 'new:0' : '')
  const choices = [
    ...existing.map((photo) => ({ value: 'existing:' + (photo.id ?? 'legacy'), url: photo.url, file: null })),
    ...files.map((file, index) => ({ value: 'new:' + index, url: null, file })),
  ]

  return (
    <fieldset className="property-upload-card complex-photo-upload form-field--wide" disabled={disabled}>
      <legend>Фотографии ЖК</legend>
      <p id="complex-photo-hint">До 30 фотографий. Главное фото отображается на главной странице. Изменения сохранятся вместе с ЖК.</p>
      <div className="complex-gallery">
        {choices.map((choice, index) => (
          <label className="complex-photo-choice" key={choice.value}>
            {choice.url ? <img src={choice.url} alt={'Фото ЖК ' + (index + 1)} loading="lazy" /> : null}
            {choice.file ? <UploadedPhotoPreview file={choice.file} number={index + 1} /> : null}
            <span><input type="radio" name="primary-complex-photo" value={choice.value}
              aria-label={'Главное фото ' + (index + 1)}
              checked={currentSelection === choice.value} onChange={() => onPrimaryChange(choice.value)} />
              Главное фото {index + 1}
            </span>
            {choice.file ? <small>{choice.file.name}</small> : null}
          </label>
        ))}
      </div>
      <label className="form-field" htmlFor="complex-photos">Добавить фотографии
        <input id="complex-photos" type="file" multiple accept="image/jpeg,image/png,image/gif,image/webp"
          aria-describedby={'complex-photo-hint' + (error ? ' complex-photo-error' : '')}
          aria-invalid={Boolean(error)} onChange={(event) => {
            onFilesChange(Array.from(event.target.files ?? []))
            onPrimaryChange('')
          }} />
      </label>
      {error ? <p id="complex-photo-error" className="field-error" role="alert">{error}</p> : null}
    </fieldset>
  )
}
