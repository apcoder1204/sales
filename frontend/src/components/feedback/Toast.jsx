import React from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { clsx } from 'clsx'
import { useContext } from 'react'
import { ToastContext } from '@context/ToastContext'

const config = {
  success: { icon: CheckCircle, cls: 'border-accent-green/30 bg-accent-green-muted', iconCls: 'text-accent-green' },
  error: { icon: XCircle, cls: 'border-accent-red/30 bg-accent-red-muted', iconCls: 'text-accent-red' },
  warning: { icon: AlertTriangle, cls: 'border-accent-yellow/30 bg-accent-yellow-muted', iconCls: 'text-accent-yellow' },
  info: { icon: Info, cls: 'border-primary/30 bg-primary-muted', iconCls: 'text-primary-light' },
}

export function Toast({ id, message, type = 'info' }) {
  const { dismiss } = useContext(ToastContext)
  const { icon: Icon, cls, iconCls } = config[type] || config.info

  return (
    <motion.div
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.95 }}
      className={clsx('flex items-start gap-3 px-4 py-3 rounded-xl border shadow-glass min-w-72 max-w-sm', cls)}
    >
      <Icon size={18} className={clsx('flex-shrink-0 mt-0.5', iconCls)} />
      <p className="flex-1 text-sm text-text-primary">{message}</p>
      <button onClick={() => dismiss(id)} className="text-text-muted hover:text-text-primary flex-shrink-0">
        <X size={14} />
      </button>
    </motion.div>
  )
}
