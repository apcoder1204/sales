import React from 'react'
import { PackageOpen } from 'lucide-react'

export default function EmptyState({ icon: Icon = PackageOpen, title = 'Hakuna data', description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="p-4 bg-bg-hover rounded-full mb-4">
        <Icon size={32} className="text-text-muted" />
      </div>
      <p className="text-text-secondary font-medium mb-1">{title}</p>
      {description && <p className="text-text-muted text-sm mb-4">{description}</p>}
      {action}
    </div>
  )
}
