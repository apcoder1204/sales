import React from 'react'
import { clsx } from 'clsx'

const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }

export default function Spinner({ size = 'md', className }) {
  return (
    <span className={clsx('inline-block animate-spin rounded-full border-2 border-border border-t-primary', sizes[size], className)} />
  )
}
