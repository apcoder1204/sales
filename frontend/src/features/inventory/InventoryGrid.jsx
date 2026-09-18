import React from 'react'
import { Settings, SendHorizontal } from 'lucide-react'
import { clsx } from 'clsx'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import { formatNumber, formatCurrency } from '@utils/formatters'
import { usePermission } from '@hooks/usePermission'
import SW from '@constants/sw'

export default function InventoryGrid({ items, loading, onAdjust, onSend, pagination }) {
  const { can } = usePermission()
  const columns = [
    {
      key: 'product_name', header: SW.bidhaa.bidhaa,
      render: (v, row) => (
        <div>
          <p className="font-medium text-text-primary">{v}</p>
          <p className="text-xs text-text-muted">{row.product_code}</p>
        </div>
      ),
    },
    { key: 'branch_name', header: SW.ufungaji.tawi, render: (v) => <span className="text-text-secondary text-sm">{v}</span> },
    {
      key: 'quantity', header: SW.hifadhi.bidhaaYote,
      render: (v) => <span className="font-semibold">{formatNumber(v)}</span>,
    },
    {
      key: 'reserved_qty', header: SW.hifadhi.kiasiKilichohifadhiwa,
      render: (v) => <span className="text-text-secondary">{formatNumber(v)}</span>,
    },
    {
      key: 'available_qty', header: SW.hifadhi.inayopatikana,
      render: (v, row) => (
        <span className={clsx('font-bold', row.is_low_stock ? 'text-accent-red' : 'text-accent-green')}>
          {formatNumber(v)}
          {row.is_low_stock && <Badge color="red" className="ml-2">{SW.hifadhi.chini}</Badge>}
        </span>
      ),
    },
    can('products.cost') && {
      key: 'cost_price', header: SW.bidhaa.beiGhali,
      render: (v) => <span className="text-text-secondary text-sm">{formatCurrency(v)}</span>,
    },
    {
      key: 'selling_price', header: SW.bidhaa.beiUzaji,
      render: (v) => <span className="font-semibold text-accent-green text-sm">{formatCurrency(v)}</span>,
    },
    (onAdjust || onSend) && {
      key: '_actions', header: '',
      render: (_, row) => (
        <div className="flex gap-1 justify-end">
          {onSend && row.branch_type === 'main_store' && row.available_qty > 0 && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onSend(row)}
              title={SW.hifadhi.tumaKwaKioski}
            >
              <SendHorizontal size={15} className="text-primary-light" />
            </Button>
          )}
          {onAdjust && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onAdjust(row)}
              title={SW.hifadhi.rekebisha}
            >
              <Settings size={15} />
            </Button>
          )}
        </div>
      ),
    },
  ].filter(Boolean)

  return (
    <DataTable
      columns={columns}
      data={items}
      loading={loading}
      pagination={pagination}
      emptyTitle={SW.bidhaa.hakunaBidhaaZilizopatikana}
    />
  )
}
