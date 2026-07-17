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
      key: 'created_at', header: 'Tarehe',
      render: (v) => <span className="text-xs text-text-muted whitespace-nowrap">{formatDate(v, 'dd/MM/yyyy HH:mm')}</span>,
    },
    {
      key: 'product', header: 'Bidhaa',
      render: (v, row) => (
        <div>
          <p className="font-medium text-text-primary text-sm">{v}</p>
          <p className="text-xs text-text-muted">{row.product_code} · {row.branch}</p>
        </div>
      ),
    },
    {
      key: 'quantity_change', header: 'Mabadiliko',
      render: (v) => (
        <span className={clsx('font-bold text-sm', v > 0 ? 'text-accent-green' : 'text-accent-red')}>
          {v > 0 ? '+' : ''}{formatNumber(v)}
        </span>
      ),
    },
    {
      key: 'notes', header: 'Sababu',
      render: (v) => <span className="text-xs text-text-secondary truncate max-w-[160px] block">{v || '—'}</span>,
    },
    {
      key: 'transaction_type', header: 'Status',
      render: (v) => (
        <Badge color={v === 'stock_in' || v === 'initial_stock' ? 'green' : 'red'}>
          {v === 'stock_in' || v === 'initial_stock' ? 'Imeongezwa' : 'Imepunguzwa'}
        </Badge>
      ),
    },
    {
      key: 'performed_by', header: 'Imefanywa Na',
      render: (v) => <span className="text-xs text-text-secondary">{v}</span>,
    },
  ]

  return (
    <PageWrapper
      title={SW.nav.marekebishoYaBidhaa}
      subtitle="Historia ya marekebisho ya idadi ya bidhaa"
      action={
        can('inventory.adjust') && (
          <Button onClick={() => setModalOpen(true)} leftIcon={<Settings size={16} />}>
            Rekebisha Bidhaa
          </Button>
        )
      }
    >
      <DataTable
        columns={columns}
        data={movements}
        loading={loading}
        pagination={pagination}
        emptyTitle="Hakuna data iliyopatikana"
      />

      <StockAdjustFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={load}
      />
    </PageWrapper>
  )
}
