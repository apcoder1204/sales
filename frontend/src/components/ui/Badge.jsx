import React from 'react'
import { clsx } from 'clsx'

const colorMap = {
  green: 'badge-green',
  red: 'badge-red',
  yellow: 'badge-yellow',
  blue: 'badge-blue',
  purple: 'badge-purple',
  gray: 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-bg-hover text-text-secondary',
}

export default function Badge({ children, color = 'gray', className }) {
  return (
    <span className={clsx(colorMap[color] || colorMap.gray, className)}>
      {children}
    </span>
  )
}
