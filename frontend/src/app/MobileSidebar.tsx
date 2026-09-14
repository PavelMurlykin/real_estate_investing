import { useEffect, useRef, type ReactNode } from 'react'

type MobileSidebarProps = {
  isOpen: boolean
  onClose: () => void
  children: ReactNode
}

export function MobileSidebar({ isOpen, onClose, children }: MobileSidebarProps) {
  const dialogReference = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogReference.current
    if (!isOpen || !dialog) return

    const previousOverflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    return () => {
      dialog.close()
      document.body.style.overflow = previousOverflow
    }
  }, [isOpen])

  return (
    <dialog
      ref={dialogReference}
      id="application-sidebar"
      className="sidebar sidebar--mobile"
      aria-label="Навигация по разделам"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
      onKeyDown={(event) => {
        if (event.key !== 'Tab') return
        const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
          'a[href], button:not(:disabled)',
        )).filter((element) => element.tabIndex >= 0 && element.getClientRects().length > 0)
        const firstControl = controls[0]
        const lastControl = controls.at(-1)
        if (event.shiftKey && document.activeElement === firstControl) {
          event.preventDefault()
          lastControl?.focus()
        } else if (!event.shiftKey && document.activeElement === lastControl) {
          event.preventDefault()
          firstControl?.focus()
        }
      }}
    >
      {children}
    </dialog>
  )
}
