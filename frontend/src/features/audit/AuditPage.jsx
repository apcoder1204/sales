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

const ACTION_COLORS = {
  create: 'green', update: 'blue', delete: 'red', login: 'purple',
  logout: 'gray', approve: 'green', reject: 'red', execute: 'yellow',
}

export default function AuditPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [selected, setSelected] = useState(null)
  const pagination = usePagination()

  const CATEGORY_OPTIONS = [
    { value: '', label: SW.kumbukumbu.vitengoVyote },
    { value: 'auth', label: SW.kumbukumbu.uthibitishaji },
    { value: 'products', label: SW.bidhaa.bidhaa },
    { value: 'inventory', label: SW.hifadhi.hifadhi },
    { value: 'sales', label: SW.mauzo.mauzo },
    { value: 'transfers', label: SW.kumbukumbu.uhamishoPekee },
    { value: 'users', label: SW.watumiaji.watumiaji },
  ]

  const ENTITY_LABELS = {
    product: SW.bidhaa.bidhaa,
    category: SW.kumbukumbu.ainaYaBidhaaEntity,
    inventory: SW.hifadhi.hifadhi,
    sale: SW.kumbukumbu.uuzajiEntity,
    stock_request: SW.uhamisho.ombi,
    stock_transfer: SW.kumbukumbu.uhamishoEntity,
  }

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
    { key: 'created_at', header: SW.ufungaji.wakati, render: (v) => formatDateTime(v) },
    {
      key: 'action', header: SW.kumbukumbu.kitendo,
      render: (v) => <Badge color={ACTION_COLORS[v] || 'gray'}>{v}</Badge>,
    },
    { key: 'category', header: SW.kumbukumbu.kitengo, render: (v) => <span className="text-text-secondary text-xs uppercase">{v}</span> },
    {
      key: 'username', header: SW.kumbukumbu.mtumiaji,
      render: (v, row) => (
        <div>
          <p className="text-sm font-medium">{v}</p>
          <p className="text-xs text-text-muted">{SW.majukumu[row.user_role] || row.user_role}</p>
        </div>
      ),
    },
    { key: 'entity_type', header: SW.kumbukumbu.kilichoAthiriwa, render: (v) => <span className="text-text-secondary text-xs">{ENTITY_LABELS[v] || '-'}</span> },
    { key: 'ip_address', header: SW.kumbukumbu.ip, render: (v) => <span className="font-mono text-xs text-text-muted">{v}</span> },
    {
      key: '_actions', header: '',
      render: (_, row) => row.details ? (
        <Button variant="ghost" size="sm" onClick={() => setSelected(row)}>{SW.common.angalia}</Button>
      ) : null,
    },
  ]

  return (
    <PageWrapper title={SW.nav.kumbukumbu} subtitle={SW.kumbukumbu.subtitle}>
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
        emptyTitle={SW.kumbukumbu.hakunaKumbukumbu}
      />

      {selected && (
        <AuditDetailModal open={!!selected} log={selected} onClose={() => setSelected(null)} />
      )}
    </PageWrapper>
  )
}
