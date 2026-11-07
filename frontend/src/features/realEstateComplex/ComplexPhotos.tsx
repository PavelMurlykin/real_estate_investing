import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { apiErrorMessage } from '@/api/client'
import { selectComplexPrimaryPhoto, uploadComplexPhotos } from '@/api/queries'
import type { RealEstateComplexDetail } from '@/api/schemas'

export function ComplexPhotos({ complex, canManage }: { complex: RealEstateComplexDetail; canManage: boolean }) {
  const [files, setFiles] = useState<File[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (photoId: number | null) => photoId === null
      ? uploadComplexPhotos(complex.id, files)
      : selectComplexPrimaryPhoto(complex.id, photoId),
    onSuccess: async (updated) => {
      setFiles([])
      if (fileInput.current) fileInput.current.value = ''
      queryClient.setQueryData(['real-estate-complex', complex.id], updated)
      await queryClient.invalidateQueries({ predicate: (query) => new Set([
        'homepage-complexes', 'real-estate-complexes', 'real-estate-complex', 'homepage', 'overview',
      ]).has(String(query.queryKey[0])) })
    },
  })
  const photos = complex.photos ?? []
  return (
    <section className="saved-property-card" aria-label="Фотографии ЖК">
      <h2>Фотографии ЖК</h2>
      <div className="complex-gallery">
        {photos.map((photo, index) => (
          <figure key={photo.id}>
            <a href={photo.url} target="_blank" rel="noreferrer" aria-label={'Открыть фото ' + (index + 1)}>
              <img src={photo.url} alt={complex.name + ' — фото ' + (index + 1)} loading="lazy" />
            </a>
            <figcaption>
              {canManage ? <label>
                <input type="radio" name="primary-complex-photo" checked={photo.isPrimary}
                  disabled={mutation.isPending} onChange={() => mutation.mutate(photo.id)} />
                Главное фото {index + 1}
              </label> : photo.isPrimary ? 'Главное фото' : 'Фото ' + (index + 1)}
            </figcaption>
          </figure>
        ))}
      </div>
      {canManage ? (
        <form className="complex-photo-form" onSubmit={(event) => {
          event.preventDefault()
          if (files.length && !mutation.isPending) mutation.mutate(null)
        }}>
          <label>Добавить фотографии
            <input ref={fileInput} type="file" multiple accept="image/jpeg,image/png,image/gif,image/webp"
              disabled={mutation.isPending} onChange={(event) => {
                setFiles(Array.from(event.target.files ?? []))
                mutation.reset()
              }} />
          </label>
          <button className="button button--secondary" type="submit" disabled={!files.length || mutation.isPending}>
            {mutation.isPending ? 'Сохраняем…' : 'Загрузить фотографии'}
          </button>
          <small>Выберите несколько файлов. Главное фото отображается на главной странице.</small>
        </form>
      ) : null}
      {mutation.isError ? <p role="alert" className="form-error">
        {apiErrorMessage(mutation.error) ?? 'Не удалось сохранить фотографии.'}
      </p> : null}
      {mutation.isSuccess ? <p role="status">Фотографии сохранены.</p> : null}
    </section>
  )
}
