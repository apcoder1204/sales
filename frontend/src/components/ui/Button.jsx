import React from 'react'
import { clsx } from 'clsx'
import Spinner from '@components/feedback/Spinner'

const variants = {
  primary: 'bg-primary hover:bg-primary-hover text-white',
  secondary: 'bg-bg-panel hover:bg-bg-hover text-text-primary border border-border',
  danger: 'bg-accent-red hover:bg-red-600 text-white',
  ghost: 'text-text-secondary hover:text-text-primary hover:bg-bg-hover',
  success: 'bg-accent-green hover:bg-emerald-600 text-white',
}

const sizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
  icon: 'p-2',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className,
  leftIcon,
  rightIcon,
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-colors duration-200',
        'disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary/50',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {loading ? <Spinner size="sm" /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  )
}
