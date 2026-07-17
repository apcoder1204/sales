import React from 'react'
import { clsx } from 'clsx'

export default function Card({ children, className, title, action, noPad = false }) {
  return (
    <div className={clsx('glass-card', className)}>
      {title && (
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-semibold text-text-primary">{title}</h3>
          {action}
        </div>
      )}
      <div className={clsx(!noPad && 'p-5')}>{children}</div>
    </div>
  )
}
