import React from 'react'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import { formatDateTime } from '@utils/formatters'
import { TRANSFER_STATUSES } from '@utils/constants'
import { usePermission } from '@hooks/usePermission'
import SW from '@constants/sw'

export default function RequestsTable({ requests, loading, onReview, pagination }) {
  const { can } = usePermission()

  const columns = [
    { key: 'request_no', header: 'Namba', render: (v) => <span className="font-mono text-xs text-primary-light">{v}</span> },
    {
      key: 'items', header: 'Bidhaa',
      render: (v, row) => {
        const first = v?.[0]
        const rest = (v?.length || 0) - 1
        return (
          <div>
            <p className="font-medium">{first ? first.product : '—'}</p>
            <p className="text-xs text-text-muted">
              {first ? `Idadi: ${first.requested_qty}` : ''}
              {rest > 0 && ` · ${SW.uhamisho.naZaidi(rest)}`}
            </p>
          </div>
        )
      },
    },
    {
      key: 'from_branch', header: 'Chanzo → Lengo',
      render: (v, row) => (
        <div className="text-sm">
          <span className="text-accent-yellow">{v}</span>
          <span className="text-text-muted mx-1">→</span>
          <span className="text-accent-green">{row.to_branch}</span>
        </div>
      ),
    },
    {
      key: 'status', header: 'Hali',
      render: (v) => {
        const s = TRANSFER_STATUSES[v] || { label: v, color: 'gray' }
        return <Badge color={s.color}>{s.label}</Badge>
      },
    },
    { key: 'created_at', header: 'Tarehe', render: (v) => formatDateTime(v) },
    {
      key: '_actions', header: '',
      render: (_, row) => (
        <Button variant="ghost" size="sm" onClick={() => onReview(row)}>
          {SW.common.angalia}
        </Button>
      ),
    },
  ]

  return (
    <DataTable
      columns={columns}
      data={requests}
      loading={loading}
      pagination={pagination}
      emptyTitle="Hakuna maombi yaliyopatikana"
    />
  )
}
