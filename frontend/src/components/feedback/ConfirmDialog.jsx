import React from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import { AlertTriangle } from 'lucide-react'

export default function ConfirmDialog({ open, onConfirm, onCancel, message, confirmLabel = 'Thibitisha', cancelLabel = 'Ghairi', variant = 'danger' }) {
  return (
    <Modal open={open} onClose={onCancel} size="sm">
      <div className="flex flex-col items-center text-center gap-4 py-2">
        <div className="p-3 rounded-full bg-accent-yellow-muted">
          <AlertTriangle size={24} className="text-accent-yellow" />
        </div>
        <p className="text-text-primary">{message}</p>
        <div className="flex gap-3 w-full">
          <Button variant="secondary" className="flex-1" onClick={onCancel}>{cancelLabel}</Button>
          <Button variant={variant} className="flex-1" onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </Modal>
  )
}
