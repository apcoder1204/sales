import React from 'react'

export default function PageWrapper({ title, subtitle, action, children }) {
  return (
    <div className="space-y-6">
      {(title || action) && (
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-text-primary">{title}</h1>
            {subtitle && <p className="text-sm text-text-muted mt-0.5">{subtitle}</p>}
          </div>
          {action && <div className="flex-shrink-0">{action}</div>}
        </div>
      )}
      {children}
    </div>
  )
}
