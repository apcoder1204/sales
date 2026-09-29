import React, { useState } from 'react'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import { formatDateTime } from '@utils/formatters'
import { getTransferStatuses } from '@utils/constants'
import { usePermission } from '@hooks/usePermission'
import { useAuth } from '@hooks/useAuth'
import { useApi } from '@hooks/useApi'
import { isGlobalRole } from '@utils/permissions'
import { transferService } from '@services/transferService'
import SW from '@constants/sw'

export default function RequestsTable({ requests, loading, onReview, onExecuted, pagination }) {
  const { can } = usePermission()
  const { user } = useAuth()
  const { call } = useApi()
  const [executingId, setExecutingId] = useState(null)

  // Same eligibility rule as ReviewRequestModal's execute button — a
  // physical handover, so only whoever's actually holding the stock (or a
  // global role) may confirm it. Inline here too so the common "approved,
  // ready to hand over" case doesn't need opening the full review modal
  // just to click one button.
  const canExecute = (row) => can('transfers.execute') && (isGlobalRole(user) || user?.branch_id === row.from_branch_id)

  const handleExecute = async (row) => {
    setExecutingId(row.id)
    try {
      await call(() => transferService.executeTransfer(row.id), {
        successMsg: SW.mafanikio.imesafirishwa, onSuccess: onExecuted,
      })
    } finally {
      setExecutingId(null)
    }
  }

  const columns = [
    { key: 'request_no', header: SW.uhamisho.namba, render: (v) => <span className="font-mono text-xs text-primary-light">{v}</span> },
    {
      key: 'items', header: SW.uhamisho.bidhaa,
      render: (v, row) => {
        const first = v?.[0]
        const rest = (v?.length || 0) - 1
        return (
          <div>
            <p className="font-medium">{first ? first.product : '—'}</p>
            <p className="text-xs text-text-muted">
              {first ? `${SW.common.idadi}: ${first.requested_qty}` : ''}
              {rest > 0 && ` · ${SW.uhamisho.naZaidi(rest)}`}
            </p>
          </div>
        )
      },
    },
    {
      key: 'from_branch', header: SW.uhamisho.chanzoLengo,
      render: (v, row) => (
        <div className="text-sm">
          <span className="text-accent-yellow">{v}</span>
          <span className="text-text-muted mx-1">→</span>
          <span className="text-accent-green">{row.to_branch}</span>
        </div>
      ),
    },
    {
      key: 'status', header: SW.common.hali,
      render: (v) => {
        const s = getTransferStatuses()[v] || { label: v, color: 'gray' }
        return <Badge color={s.color}>{s.label}</Badge>
      },
    },
    { key: 'created_at', header: SW.common.tarehe, render: (v) => formatDateTime(v) },
    {
      key: '_actions', header: '',
      render: (_, row) => (
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => onReview(row)}>
            {SW.common.angalia}
          </Button>
          {row.status === 'approved' && canExecute(row) && (
            <Button
              size="sm" loading={executingId === row.id}
              onClick={(e) => { e.stopPropagation(); handleExecute(row) }}
            >
              {SW.uhamisho.tekeleza}
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <DataTable
      columns={columns}
      data={requests}
      loading={loading}
      pagination={pagination}
      emptyTitle={SW.uhamisho.hakunaMaombi}
    />
  )
}
