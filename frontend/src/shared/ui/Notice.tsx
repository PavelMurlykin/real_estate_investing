import { useEffect, useRef, type ReactNode, type RefObject } from 'react'
import { restoreFocus } from '@/shared/lib/restoreFocus'

type NoticeProps = {
  children: ReactNode
  tone?: 'info' | 'success' | 'warning' | 'error'
  as?: 'p' | 'div' | 'span' | 'section'
  role?: 'alert' | 'status'
  id?: string
  className?: string
} & ({ onDismiss?: undefined; returnFocusRef?: undefined } | {
  onDismiss: () => void
  returnFocusRef: RefObject<HTMLElement | null>
})

export function Notice({ children, tone = 'info', as: Tag = 'p', role, id, className = '',
  onDismiss, returnFocusRef }: NoticeProps) {
  const focusChecked = useRef(false)
  useEffect(() => {
    if (focusChecked.current || !returnFocusRef) return
    const trigger = returnFocusRef.current
    if (!trigger || trigger.matches(':disabled')) return
    focusChecked.current = true
    if (document.activeElement === document.body) trigger.focus({ preventScroll: true })
  })
  const Content = Tag === 'p' || Tag === 'span' ? 'span' : 'div'
  return <Tag id={id} className={`notice notice--${tone} ${className}`} role={role ?? (tone === 'error' ? 'alert' : 'status')} aria-atomic="true">
    <svg className="notice__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      {tone === 'success' ? <path d="m7.5 12 3 3 6-6" /> : <path d={tone === 'info' ? 'M12 10v7m0-10v1' : 'M12 7v7m0 3v1'} />}
    </svg>
    <Content className="notice__content">{children}</Content>
    {onDismiss ? <button type="button" className="notice__dismiss" aria-label="Закрыть уведомление" onClick={() => {
      restoreFocus(returnFocusRef.current)
      onDismiss()
    }}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
    </button> : null}
  </Tag>
}
