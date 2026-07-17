import React, { useState, useEffect, useCallback } from 'react'
import PageWrapper from '@components/layout/PageWrapper'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import AuditDetailModal from './AuditDetailModal'
import { auditService } from '@services/auditService'
import { usePagination } from '@hooks/usePagination'
import { formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

const CATEGORY_OPTIONS = [
  { value: '', label: 'Vitengo Vyote' },
  { value: 'auth', label: 'Uthibitishaji' },
  { value: 'products', label: 'Bidhaa' },
  { value: 'inventory', label: 'Inventory' },
  { value: 'sales', label: 'Mauzo' },
  { value: 'transfers', label: 'Uhamisho' },
  { value: 'users', label: 'Watumiaji' },
]

const ACTION_COLORS = {
  create: 'green', update: 'blue', delete: 'red', login: 'purple',
  logout: 'gray', approve: 'green', reject: 'red', execute: 'yellow',
}

const ENTITY_LABELS = {
  product: 'Bidhaa',
  category: 'Aina ya Bidhaa',
  inventory: 'Inventory',
  sale: 'Uuzaji',
  stock_request: 'Ombi la Bidhaa',
  stock_transfer: 'Uhamisho',
}

export default function AuditPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [selected, setSelected] = useState(null)
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await auditService.list({
        category: category || undefined,
        ...pagination.params,
      })
      setLogs(res.items || res)
      if (res.total !== undefined) pagination.setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [category, pagination.page])

  useEffect(() => { load() }, [load])

  const columns = [
    { key: 'created_at', header: 'Wakati', render: (v) => formatDateTime(v) },
    {
      key: 'action', header: 'Kitendo',
      render: (v) => <Badge color={ACTION_COLORS[v] || 'gray'}>{v}</Badge>,
    },
    { key: 'category', header: 'Kitengo', render: (v) => <span className="text-text-secondary text-xs uppercase">{v}</span> },
    {
      key: 'username', header: 'Mtumiaji',
      render: (v, row) => (
        <div>
          <p className="text-sm font-medium">{v}</p>
          <p className="text-xs text-text-muted">{SW.majukumu[row.user_role] || row.user_role}</p>
        </div>
      ),
    },
    { key: 'entity_type', header: 'Kilicho Athiriwa', render: (v) => <span className="text-text-secondary text-xs">{ENTITY_LABELS[v] || '-'}</span> },
    { key: 'ip_address', header: 'IP', render: (v) => <span className="font-mono text-xs text-text-muted">{v}</span> },
    {
      key: '_actions', header: '',
      render: (_, row) => row.details ? (
        <Button variant="ghost" size="sm" onClick={() => setSelected(row)}>{SW.common.angalia}</Button>
      ) : null,
    },
  ]

  return (
    <PageWrapper title={SW.nav.kumbukumbu} subtitle="Kumbukumbu za vitendo vyote vya mfumo">
      <div className="flex gap-3">
        <Select
          value={category}
          onChange={(e) => { setCategory(e.target.value); pagination.reset() }}
          options={CATEGORY_OPTIONS}
          containerClassName="w-48"
        />
      </div>

      <DataTable
        columns={columns}
        data={logs}
        loading={loading}
        pagination={pagination}
        emptyTitle="Hakuna kumbukumbu zilizopatikana"
      />

      {selected && (
        <AuditDetailModal open={!!selected} log={selected} onClose={() => setSelected(null)} />
      )}
    </PageWrapper>
  )
}
