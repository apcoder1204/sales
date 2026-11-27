import React from 'react'
import { RefreshCw, ShieldCheck } from 'lucide-react'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import { formatDateTime } from '@utils/formatters'
import { codeText, detailText, figure, recordLabel } from '@utils/reconciliationLabels'
import SW from '@constants/sw'

export const EXCEPTION_COLOR = { OPEN: 'red', UNDER_REVIEW: 'yellow', RESOLVED: 'green', DISMISSED: 'gray' }

// One row per discrepancy: what is wrong (in plain words), which record,
// expected vs actual, and its review status. Admins get the status button;
// everyone who can read gets "check again" for the affected record.
export default function ExceptionsTable({ rows, loading, canResolve, onChangeStatus, onRecheck, emptyTitle }) {
  const U = SW.upatanisho
  const live = (row) => row.status === 'OPEN' || row.status === 'UNDER_REVIEW'
  const columns = [
    {
      key: 'code', header: U.aina,
      render: (v, row) => (
        <div className="max-w-md">
          <div className="flex items-center gap-2">
            <Badge color={row.severity === 'warning' ? 'yellow' : 'red'}>{row.severity === 'warning' ? U.onyoTu : U.fedha}</Badge>
            <span className="text-xs text-text-muted">{row.group} · {v}</span>
          </div>
          <p className="text-sm mt-1">{codeText(v)}</p>
          {detailText(row) && <p className="text-xs text-text-muted">{detailText(row)}</p>}
        </div>
      ),
    },
    { key: 'customer', header: U.rekodiHusika, render: (_, row) => <span className="text-sm">{recordLabel(row)}</span> },
    { key: 'branch_name', header: SW.wateja.tawi, render: (v) => v || '—' },
    { key: 'expected', header: U.inayotarajiwa, render: (v, row) => <span className="whitespace-nowrap">{figure(row, v)}</span> },
    { key: 'actual', header: U.halisi, render: (v, row) => <span className="whitespace-nowrap">{figure(row, v)}</span> },
    {
      key: 'difference', header: U.kiasiTofauti,
      render: (v, row) => <span className="whitespace-nowrap font-semibold">{figure(row, v)}</span>,
    },
    {
      key: 'status', header: U.hali,
      render: (v, row) => (
        <div>
          <Badge color={EXCEPTION_COLOR[v]}>{U.haliTofauti[v] || v}</Badge>
          {row.status_by_name && <p className="text-xs text-text-muted mt-1">{U.aliyebadilisha}: {row.status_by_name}</p>}
          {row.status_reason && <p className="text-xs text-text-muted">{row.status_reason}</p>}
          {row.status_reference && <p className="text-xs text-text-muted">{row.status_reference}</p>}
        </div>
      ),
    },
    { key: 'detected_at', header: U.ilionekana, render: (v) => <span className="text-xs whitespace-nowrap">{formatDateTime(v)}</span> },
    {
      key: '_actions', header: '',
      render: (_, row) => live(row) && (
        <div className="flex flex-col gap-1">
          {canResolve && (
            <Button size="sm" variant="secondary" leftIcon={<ShieldCheck size={14} />} onClick={() => onChangeStatus(row)}>
              {U.badilishaHali}
            </Button>
          )}
          <Button size="sm" variant="ghost" leftIcon={<RefreshCw size={14} />} onClick={() => onRecheck(row)}>
            {U.kaguaTena}
          </Button>
        </div>
      ),
    },
  ]
  return <DataTable columns={columns} data={rows} loading={loading} emptyTitle={emptyTitle || U.hakunaTofauti} />
}
