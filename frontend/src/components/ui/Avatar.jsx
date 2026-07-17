import React from 'react'
import { clsx } from 'clsx'

const colors = ['bg-primary-muted text-primary-light', 'bg-accent-green-muted text-accent-green', 'bg-accent-purple-muted text-accent-purple', 'bg-accent-yellow-muted text-accent-yellow']

export default function Avatar({ name = '', size = 'md', className }) {
  const initials = name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()
  const colorIdx = name.charCodeAt(0) % colors.length
  const sizes = { sm: 'w-7 h-7 text-xs', md: 'w-9 h-9 text-sm', lg: 'w-11 h-11 text-base' }

  return (
    <div className={clsx('rounded-full flex items-center justify-center font-semibold flex-shrink-0', colors[colorIdx], sizes[size], className)}>
      {initials}
    </div>
  )
}
