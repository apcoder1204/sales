import React, { useContext } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence } from 'framer-motion'
import { ToastContext } from '@context/ToastContext'
import { Toast } from './Toast'

export default function ToastContainer() {
  const { toasts } = useContext(ToastContext)

  return createPortal(
    <div className="fixed top-5 right-5 z-[100] flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <Toast key={t.id} {...t} />
        ))}
      </AnimatePresence>
    </div>,
    document.getElementById('toast-root')
  )
}
