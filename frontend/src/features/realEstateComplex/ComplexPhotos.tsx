import { ModalDialog } from '@/shared/ui/ModalDialog'
import { useRef, useState } from 'react'

import type { RealEstateComplexDetail } from '@/api/schemas'

import { complexPhotoItems } from './photoItems'

export function ComplexPhotos({ complex }: { complex: RealEstateComplexDetail }) {
  const photos = complexPhotoItems(complex)
  const [activeIndex, setActiveIndex] = useState(0)
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const photo = photos[activeIndex % photos.length]
  const move = (direction: number) => setActiveIndex((current) => (
    (current + direction + photos.length) % photos.length
  ))
  const close = () => {
    setIsOpen(false)
    triggerRef.current?.focus()
  }

  const navigation = photos.length > 1 ? (
    <div className="complex-carousel__navigation">
      <button type="button" className="icon-button" aria-label="Предыдущее фото" onClick={() => move(-1)}>‹</button>
      <span role="status" aria-live="polite" aria-atomic="true">Фото {activeIndex % photos.length + 1} из {photos.length}</span>
      <button type="button" className="icon-button" aria-label="Следующее фото" onClick={() => move(1)}>›</button>
    </div>
  ) : null

  return (
    <section className="complex-photo-card" aria-label="Фотографии ЖК" aria-roledescription="карусель"
      onKeyDown={(event) => {
        if (photos.length < 2) return
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault()
          move(event.key === 'ArrowLeft' ? -1 : 1)
        }
      }}>
      {photo ? <>
        <button type="button" className="complex-carousel__image" ref={triggerRef}
          aria-label="Увеличить фото жилого комплекса" onClick={() => setIsOpen(true)}>
          <img src={photo.url} alt={`Жилой комплекс ${complex.name} — фото ${activeIndex % photos.length + 1}`} />
        </button>
        {isOpen ? null : navigation}
      </> : (
        <div className="complex-photo-placeholder">
          <span aria-hidden="true">⌂</span><p>Фото жилого комплекса не загружено</p>
        </div>
      )}
      {isOpen && photo ? (
        <ModalDialog className="property-image-dialog" role="dialog" labelledBy="complex-photo-modal-title" onClose={close}>
          <div className="property-image-modal__content">
            <div className="property-image-modal__header">
              <h2 id="complex-photo-modal-title">Фото {complex.name}</h2>
              <button type="button" className="icon-button" ref={closeRef} aria-label="Закрыть изображение" onClick={close}>×</button>
            </div>
            <img src={photo.url} alt={`${complex.name} — фото ${activeIndex % photos.length + 1}`} />
            {navigation}
          </div>
        </ModalDialog>
      ) : null}
    </section>
  )
}
