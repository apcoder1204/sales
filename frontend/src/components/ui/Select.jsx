import React from 'react'
import { clsx } from 'clsx'

export default function Select({ label, error, options = [], placeholder, containerClassName, required, className, leftIcon, ...props }) {
  return (
    <div className={clsx('flex flex-col gap-1', containerClassName)}>
      {label && (
        <label className="text-sm font-medium text-text-secondary">
          {label}
          {required && <span className="text-accent-red ml-1">*</span>}
        </label>
      )}
      <div className="relative">
        {leftIcon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted flex items-center pointer-events-none z-10">
            {leftIcon}
          </span>
        )}
        <select
          className={clsx(
            'input-base appearance-none cursor-pointer w-full',
            leftIcon && 'pl-9',
            error && 'border-accent-red',
            className
          )}
          {...props}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="text-xs text-accent-red">{error}</p>}
    </div>
  )
}
