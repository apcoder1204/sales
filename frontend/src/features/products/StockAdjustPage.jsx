import React, { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Settings } from 'lucide-react'
import { clsx } from 'clsx'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import StockAdjustFormModal from './StockAdjustFormModal'
import { inventoryService } from '@services/inventoryService'
import { usePermission } from '@hooks/usePermission'
import { usePagination } from '@hooks/usePagination'
import { formatDate, formatNumber } from '@utils/formatters'
import SW from '@constants/sw'

export default function StockAdjustPage() {
  const { can } = usePermission()
  const [modalOpen, setModalOpen] = useState(false)
  const [movements, setMovements] = useState([])
  const [loading, setLoading] = useState(true)
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await inventoryService.movements({ ...pagination.params })
      setMovements(res.items || [])
      if (res.total !== undefined) pagination.setTotal(res.total)
    } catch {
      setMovements([])
    } finally {
      setLoading(false)
    }
  }, [pagination.page])

  useEffect(() => { load() }, [load])

  const columns = [
    {
      key: 'created_at', header: SW.common.tarehe,
      render: (v) => <span className="text-xs text-text-muted whitespace-nowrap">{formatDate(v, 'dd/MM/yyyy HH:mm')}</span>,
    },
    {
      key: 'product', header: SW.bidhaa.bidhaa,
      render: (v, row) => (
        <div>
          <p className="font-medium text-text-primary text-sm">{v}</p>
          <p className="text-xs text-text-muted">{row.product_code} · {row.branch}</p>
        </div>
      ),
    },
    {
      key: 'quantity_change', header: SW.hifadhi.mabadiliko,
      render: (v) => (
        <span className={clsx('font-bold text-sm', v > 0 ? 'text-accent-green' : 'text-accent-red')}>
          {v > 0 ? '+' : ''}{formatNumber(v)}
        </span>
      ),
    },
    {
      key: 'notes', header: SW.hifadhi.sababu,
      render: (v) => <span className="text-xs text-text-secondary truncate max-w-[160px] block">{v || '—'}</span>,
    },
    {
      key: 'transaction_type', header: SW.common.hali,
      render: (v) => (
        <Badge color={v === 'stock_in' || v === 'initial_stock' ? 'green' : 'red'}>
          {v === 'stock_in' || v === 'initial_stock' ? SW.bidhaa.imeongezwa : SW.bidhaa.imepunguzwa}
        </Badge>
      ),
    },
    {
      key: 'performed_by', header: SW.bidhaa.imefanywaNa,
      render: (v) => <span className="text-xs text-text-secondary">{v}</span>,
    },
  ]

  return (
    <PageWrapper
      title={SW.nav.marekebishoYaBidhaa}
      subtitle={SW.bidhaa.historiaMarekebisho}
      action={
        can('inventory.adjust') && (
          <Button onClick={() => setModalOpen(true)} leftIcon={<Settings size={16} />}>
            {SW.hifadhi.rekebisha}
          </Button>
        )
      }
    >
      <DataTable
        columns={columns}
        data={movements}
        loading={loading}
        pagination={pagination}
        emptyTitle={SW.common.hakuna}
      />

      <StockAdjustFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={load}
      />
    </PageWrapper>
  )
}
