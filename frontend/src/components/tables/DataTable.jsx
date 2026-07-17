import React from 'react'
import { clsx } from 'clsx'
import { SkeletonTable } from '@components/feedback/Skeleton'
import EmptyState from '@components/feedback/EmptyState'
import TablePagination from './TablePagination'

export default function DataTable({
  columns,
  data = [],
  loading,
  keyField = 'id',
  onRowClick,
  pagination,
  className,
  emptyIcon,
  emptyTitle,
}) {
  return (
    <div className={clsx('glass-card overflow-hidden', className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={clsx(
                    'px-4 py-3 text-left font-medium text-text-muted whitespace-nowrap',
                    col.headerClassName
                  )}
                  style={{ width: col.width }}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          {!loading && (
            <tbody>
              {data.map((row) => (
                <tr
                  key={row[keyField]}
                  onClick={() => onRowClick?.(row)}
                  className={clsx(
                    'border-b border-border/50 transition-colors',
                    onRowClick && 'cursor-pointer hover:bg-bg-hover'
                  )}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={clsx('px-4 py-3 text-text-primary', col.className)}>
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>
      {loading && <SkeletonTable rows={6} cols={columns.length} />}
      {!loading && data.length === 0 && <EmptyState icon={emptyIcon} title={emptyTitle} />}
      {pagination && <TablePagination {...pagination} />}
    </div>
  )
}
