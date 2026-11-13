import { useEffect, useRef, type ReactNode } from 'react'
import { dialogControls, restoreFocus } from '@/shared/lib/restoreFocus'

type ModalDialogProps = {
  labelledBy?: string
  label?: string
  describedBy?: string
  id?: string
  open?: boolean
  children: ReactNode
  onClose: () => void
  pending?: boolean
  role?: 'dialog' | 'alertdialog'
  className?: string
}

export function ModalDialog({ labelledBy, label, describedBy, id, children, onClose, pending = false,
  open = true, role = 'alertdialog', className = 'confirmation-dialog' }: ModalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const startedOutside = useRef(false)

  useEffect(() => {
    const dialog = dialogRef.current!
    if (!open) return
    const trigger = document.activeElement
    const previousOverflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    const initial = dialogControls(dialog)[0] ?? dialog
    initial.focus()
    return () => {
      if (dialog.open) dialog.close()
      document.body.style.overflow = previousOverflow
      restoreFocus(trigger)
    }
  }, [open])

  useEffect(() => {
    if (!open || !pending) return
    const target = dialogRef.current?.querySelector<HTMLElement>('h2, h3') ?? dialogRef.current
    if (target) { target.setAttribute('tabindex', '-1'); target.focus() }
  }, [open, pending])

  const outside = (dialog: HTMLDialogElement, x: number, y: number) => {
    const bounds = dialog.getBoundingClientRect()
    return x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom
  }

  return <dialog ref={dialogRef} id={id} tabIndex={-1} className={`modal-dialog ${className}`} role={role}
    aria-modal="true" aria-labelledby={labelledBy} aria-label={label} aria-describedby={describedBy} aria-busy={pending || undefined}
    onCancel={(event) => { event.preventDefault(); if (!pending) onClose() }}
    onPointerDown={(event) => {
      startedOutside.current = event.target === event.currentTarget && outside(event.currentTarget, event.clientX, event.clientY)
    }}
    onPointerUp={(event) => {
      if (startedOutside.current && event.target === event.currentTarget && !pending
        && outside(event.currentTarget, event.clientX, event.clientY)) onClose()
      startedOutside.current = false
    }}
    onKeyDown={(event) => {
      if (event.defaultPrevented) return
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        if (!pending) onClose()
      }
      if (event.key !== 'Tab') return
      if (pending) { event.preventDefault(); return }
      const controls = dialogControls(event.currentTarget)
      const active = document.activeElement
      if (!controls.length) { event.preventDefault(); return }
      if (!controls.includes(active as HTMLElement) || active === controls[event.shiftKey ? 0 : controls.length - 1]) {
        event.preventDefault()
        controls[event.shiftKey ? controls.length - 1 : 0].focus()
      }
    }}>{children}</dialog>
}
