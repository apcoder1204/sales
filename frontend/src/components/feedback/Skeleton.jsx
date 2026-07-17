import React from 'react'
import { clsx } from 'clsx'

export default function Skeleton({ className }) {
  return <div className={clsx('animate-pulse bg-bg-hover rounded', className)} />
}

export function SkeletonTable({ rows = 5, cols = 5 }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 px-4 py-3 border-b border-border">
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c} className="flex-1">
              <Skeleton className="h-4 w-full" />
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
