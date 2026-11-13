import type { ReactNode } from 'react'
import { ModalDialog } from '@/shared/ui/ModalDialog'

type MobileSidebarProps = { isOpen: boolean; onClose: () => void; children: ReactNode }

export function MobileSidebar({ isOpen, onClose, children }: MobileSidebarProps) {
  return <ModalDialog open={isOpen} id="application-sidebar" className="sidebar sidebar--mobile"
    role="dialog" label="Навигация по разделам" onClose={onClose}>
    {children}
  </ModalDialog>
}
