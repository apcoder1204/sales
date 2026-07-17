import React from 'react'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import { formatDateTime } from '@utils/formatters'
import { TRANSFER_STATUSES } from '@utils/constants'

export default function TransfersTable({ transfers, loading, pagination }) {
  const columns = [
    { key: 'transfer_no', header: 'Namba', render: (v) => <span className="font-mono text-xs text-primary-light">{v}</span> },
    {
      key: 'from_branch_name', header: 'Chanzo → Lengo',
      render: (v, row) => (
        <span className="text-sm">
          <span className="text-accent-yellow">{v}</span>
          <span className="text-text-muted mx-1">→</span>
          <span className="text-accent-green">{row.to_branch_name}</span>
        </span>
      ),
    },
    { key: 'items_count', header: 'Bidhaa', render: (v) => `${v} aina` },
    {
      key: 'status', header: 'Hali',
      render: (v) => {
        const s = TRANSFER_STATUSES[v] || { label: v, color: 'gray' }
        return <Badge color={s.color}>{s.label}</Badge>
      },
    },
    { key: 'executed_by_name', header: 'Aliyetekeleza', render: (v) => <span className="text-text-secondary text-sm">{v || '-'}</span> },
    { key: 'created_at', header: 'Tarehe', render: (v) => formatDateTime(v) },
  ]

  return (
    <DataTable
      columns={columns}
      data={transfers}
      loading={loading}
      pagination={pagination}
      emptyTitle="Hakuna uhamisho uliofanywa"
    />
  )
}
