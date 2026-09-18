import React, { useState, useEffect, useCallback } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import { inventoryService } from '@services/inventoryService'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import { usePagination } from '@hooks/usePagination'
import { formatDateTime, formatNumber } from '@utils/formatters'
import { getTxTypes } from '@utils/constants'
import SW from '@constants/sw'

export default function MovementsPage() {
  const navigate = useNavigate()
  const branchFilter = useActiveBranchFilter()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await inventoryService.movements({ ...branchFilter, ...pagination.params })
      setItems(res.items || res)
      if (res.total !== undefined) pagination.setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [branchFilter.branch_id, pagination.page])

  useEffect(() => { load() }, [load])
  useEffect(() => { pagination.reset() }, [branchFilter.branch_id])

  const columns = [
    { key: 'created_at', header: SW.common.tarehe, render: (v) => formatDateTime(v) },
    {
      key: 'product', header: SW.bidhaa.bidhaa,
      render: (v, row) => (
        <div>
          <p className="font-medium">{v}</p>
          <p className="text-xs text-text-muted">{row.branch}</p>
        </div>
      ),
    },
    {
      key: 'transaction_type', header: SW.hifadhi.aina,
      render: (v) => {
        const tx = getTxTypes()[v] || { label: v, color: 'gray' }
        return <Badge color={tx.color}>{tx.label}</Badge>
      },
    },
    {
      key: 'quantity_change', header: SW.hifadhi.mabadiliko,
      render: (v) => (
        <span className={v > 0 ? 'text-accent-green font-semibold' : 'text-accent-red font-semibold'}>
          {v > 0 ? '+' : ''}{formatNumber(v)}
        </span>
      ),
    },
    { key: 'quantity_before', header: SW.hifadhi.kabla, render: (v) => formatNumber(v) },
    { key: 'quantity_after', header: SW.hifadhi.baada, render: (v) => <span className="font-medium">{formatNumber(v)}</span> },
    { key: 'notes', header: SW.bidhaa.maelezo, render: (v) => <span className="text-text-muted text-xs">{v || '-'}</span> },
  ]

  return (
    <PageWrapper
      title={SW.hifadhi.harakati}
      subtitle={SW.hifadhi.historiaSubtitle}
      action={
        <Button variant="ghost" onClick={() => navigate('/hifadhi')} leftIcon={<ArrowLeft size={16} />}>
          {SW.common.rudi}
        </Button>
      }
    >
      <DataTable
        columns={columns}
        data={items}
        loading={loading}
        pagination={pagination}
        emptyTitle={SW.hifadhi.hakunaHarakati}
      />
    </PageWrapper>
  )
}
