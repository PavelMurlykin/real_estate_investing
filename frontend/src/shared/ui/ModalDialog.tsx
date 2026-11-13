import { useEffect, useRef, type ReactNode } from 'react'

type ModalDialogProps = {
  labelledBy: string
  describedBy?: string
  children: ReactNode
  onClose: () => void
  pending?: boolean
  role?: 'dialog' | 'alertdialog'
  className?: string
}

export function ModalDialog({ labelledBy, describedBy, children, onClose, pending = false,
  role = 'alertdialog', className = 'confirmation-dialog' }: ModalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current!
    const trigger = document.activeElement
    const previousOverflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    dialog.querySelector<HTMLElement>('button:not(:disabled), a[href], [tabindex="0"]')?.focus()
    return () => {
      if (dialog.open) dialog.close()
      document.body.style.overflow = previousOverflow
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus()
    }
  }, [])

  useEffect(() => {
    if (pending) dialogRef.current?.querySelector<HTMLElement>('h2, h3')?.focus()
  }, [pending])

  return <dialog ref={dialogRef} className={`modal-dialog ${className}`} role={role}
    aria-modal="true" aria-labelledby={labelledBy} aria-describedby={describedBy} aria-busy={pending || undefined}
    onCancel={(event) => { event.preventDefault(); if (!pending) onClose() }}
    onClick={(event) => {
      if (event.target !== event.currentTarget || pending) return
      const bounds = event.currentTarget.getBoundingClientRect()
      if (event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose()
    }}
    onKeyDown={(event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        if (!pending) onClose()
      }
      if (event.key !== 'Tab') return
      if (pending) { event.preventDefault(); return }
      const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), [tabindex="0"]')]
      const active = document.activeElement
      if (!controls.length) { event.preventDefault(); return }
      if (!controls.includes(active as HTMLElement) || active === controls[event.shiftKey ? 0 : controls.length - 1]) {
        event.preventDefault()
        controls[event.shiftKey ? controls.length - 1 : 0].focus()
      }
    }}>{children}</dialog>
}
