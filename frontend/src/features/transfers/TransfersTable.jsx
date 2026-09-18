import React from 'react'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import { formatDateTime } from '@utils/formatters'
import { getTransferStatuses } from '@utils/constants'
import SW from '@constants/sw'

export default function TransfersTable({ transfers, loading, pagination }) {
  const columns = [
    { key: 'transfer_no', header: SW.uhamisho.namba, render: (v) => <span className="font-mono text-xs text-primary-light">{v}</span> },
    {
      key: 'from_branch_name', header: SW.uhamisho.chanzoLengo,
      render: (v, row) => (
        <span className="text-sm">
          <span className="text-accent-yellow">{v}</span>
          <span className="text-text-muted mx-1">→</span>
          <span className="text-accent-green">{row.to_branch_name}</span>
        </span>
      ),
    },
    { key: 'items_count', header: SW.uhamisho.bidhaa, render: (v) => SW.uhamisho.ainaCount(v) },
    {
      key: 'status', header: SW.common.hali,
      render: (v) => {
        const s = getTransferStatuses()[v] || { label: v, color: 'gray' }
        return <Badge color={s.color}>{s.label}</Badge>
      },
    },
    { key: 'executed_by_name', header: SW.uhamisho.aliyetekeleza, render: (v) => <span className="text-text-secondary text-sm">{v || '-'}</span> },
    { key: 'created_at', header: SW.common.tarehe, render: (v) => formatDateTime(v) },
  ]

  return (
    <DataTable
      columns={columns}
      data={transfers}
      loading={loading}
      pagination={pagination}
      emptyTitle={SW.uhamisho.hakunaUhamisho}
    />
  )
}
