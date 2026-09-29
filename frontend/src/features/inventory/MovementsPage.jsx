import React, { useState, useEffect, useCallback } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import { inventoryService } from '@services/inventoryService'
import { productService } from '@services/productService'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import { usePagination } from '@hooks/usePagination'
import { formatDateTime, formatNumber } from '@utils/formatters'
import { getTxTypes } from '@utils/constants'
import SW from '@constants/sw'

export default function MovementsPage() {
  const navigate = useNavigate()
  const branchFilter = useActiveBranchFilter()
  const [items, setItems] = useState([])
  const [products, setProducts] = useState([])
  const [valuation, setValuation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [productId, setProductId] = useState('')
  const [txType, setTxType] = useState('')
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await inventoryService.movements({
        ...branchFilter,
        product_id: productId || undefined,
        tx_type: txType || undefined,
        ...pagination.params,
      })
      setItems(res.items || res)
      if (res.total !== undefined) pagination.setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [branchFilter.branch_id, productId, txType, pagination.page])

  useEffect(() => { load() }, [load])
  useEffect(() => { pagination.reset() }, [branchFilter.branch_id, productId, txType])

  useEffect(() => {
    productService.list({ status: 'active', per_page: 200 }).then((r) => setProducts(r.items || r)).catch(() => {})
  }, [])

  // Current stock-on-hand value for whatever branch context is active — the
  // ledger below explains *how* stock moved; this header answers "what is
  // it worth right now". Best-effort: cashier lacks inventory.summary's
  // cost-visibility permission and gets a 403 here, so it's just left blank
  // for them rather than surfaced as an error.
  useEffect(() => {
    inventoryService.summary(branchFilter.branch_id).then(setValuation).catch(() => setValuation(null))
  }, [branchFilter.branch_id])

  const TX_TYPE_OPTIONS = [
    { value: '', label: SW.hifadhi.ainaZote },
    ...Object.entries(getTxTypes()).map(([value, t]) => ({ value, label: t.label })),
  ]
  const PRODUCT_OPTIONS = [
    { value: '', label: SW.hifadhi.bidhaaZote },
    ...products.map((p) => ({ value: p.id, label: `${p.product_code} — ${p.name}` })),
  ]

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
      {valuation && valuation.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {valuation.map((v) => (
            <div key={v.branch_id} className="glass-card p-4">
              <p className="text-xs text-text-muted mb-1">{v.branch_name}</p>
              <p className="text-lg font-bold text-text-primary">{v.total_value}</p>
              <p className="text-xs text-text-muted">{SW.bidhaa.idadiBidhaa(v.product_count)} · {SW.hifadhi.jumlaIdadi(v.total_quantity)}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-3 flex-wrap">
        <Select value={productId} onChange={(e) => setProductId(e.target.value)} options={PRODUCT_OPTIONS} containerClassName="w-64" />
        <Select value={txType} onChange={(e) => setTxType(e.target.value)} options={TX_TYPE_OPTIONS} containerClassName="w-48" />
      </div>

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
