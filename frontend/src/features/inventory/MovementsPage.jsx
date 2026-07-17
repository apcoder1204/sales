import React, { useState, useEffect, useCallback } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import { inventoryService } from '@services/inventoryService'
import { usePagination } from '@hooks/usePagination'
import { formatDateTime, formatNumber } from '@utils/formatters'
import { TX_TYPES } from '@utils/constants'
import SW from '@constants/sw'

export default function MovementsPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await inventoryService.movements(pagination.params)
      setItems(res.items || res)
      if (res.total !== undefined) pagination.setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [pagination.page])

  useEffect(() => { load() }, [load])

  const columns = [
    { key: 'created_at', header: 'Tarehe', render: (v) => formatDateTime(v) },
    {
      key: 'product', header: 'Bidhaa',
      render: (v, row) => (
        <div>
          <p className="font-medium">{v}</p>
          <p className="text-xs text-text-muted">{row.branch}</p>
        </div>
      ),
    },
    {
      key: 'transaction_type', header: 'Aina',
      render: (v) => {
        const tx = TX_TYPES[v] || { label: v, color: 'gray' }
        return <Badge color={tx.color}>{tx.label}</Badge>
      },
    },
    {
      key: 'quantity_change', header: 'Mabadiliko',
      render: (v) => (
        <span className={v > 0 ? 'text-accent-green font-semibold' : 'text-accent-red font-semibold'}>
          {v > 0 ? '+' : ''}{formatNumber(v)}
        </span>
      ),
    },
    { key: 'quantity_before', header: 'Kabla', render: (v) => formatNumber(v) },
    { key: 'quantity_after', header: 'Baada', render: (v) => <span className="font-medium">{formatNumber(v)}</span> },
    { key: 'notes', header: 'Maelezo', render: (v) => <span className="text-text-muted text-xs">{v || '-'}</span> },
  ]

  return (
    <PageWrapper
      title={SW.hifadhi.harakati}
      subtitle="Historia ya harakati zote za bidhaa"
      action={
        <Button variant="ghost" onClick={() => navigate('/hifadhi')} leftIcon={<ArrowLeft size={16} />}>
          Rudi
        </Button>
      }
    >
      <DataTable
        columns={columns}
        data={items}
        loading={loading}
        pagination={pagination}
        emptyTitle="Hakuna harakati zilizopatikana"
      />
    </PageWrapper>
  )
}
