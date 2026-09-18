import React from 'react'
import { PackageOpen } from 'lucide-react'
import SW from '@constants/sw'

export default function EmptyState({ icon: Icon = PackageOpen, title, description, action }) {
  const resolvedTitle = title ?? SW.common.hakuna
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="p-4 bg-bg-hover rounded-full mb-4">
        <Icon size={32} className="text-text-muted" />
      </div>
      <p className="text-text-secondary font-medium mb-1">{resolvedTitle}</p>
      {description && <p className="text-text-muted text-sm mb-4">{description}</p>}
      {action}
    </div>
  )
}
