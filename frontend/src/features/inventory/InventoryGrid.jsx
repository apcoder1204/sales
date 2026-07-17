import React from 'react'
import { Settings, SendHorizontal } from 'lucide-react'
import { clsx } from 'clsx'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import { formatNumber, formatCurrency } from '@utils/formatters'
import { usePermission } from '@hooks/usePermission'

export default function InventoryGrid({ items, loading, onAdjust, onSend, pagination }) {
  const { can } = usePermission()
  const columns = [
    {
      key: 'product_name', header: 'Bidhaa',
      render: (v, row) => (
        <div>
          <p className="font-medium text-text-primary">{v}</p>
          <p className="text-xs text-text-muted">{row.product_code}</p>
        </div>
      ),
    },
    { key: 'branch_name', header: 'Tawi', render: (v) => <span className="text-text-secondary text-sm">{v}</span> },
    {
      key: 'quantity', header: 'Bidhaa Yote',
      render: (v) => <span className="font-semibold">{formatNumber(v)}</span>,
    },
    {
      key: 'reserved_qty', header: 'Imehifadhiwa',
      render: (v) => <span className="text-text-secondary">{formatNumber(v)}</span>,
    },
    {
      key: 'available_qty', header: 'Inayopatikana',
      render: (v, row) => (
        <span className={clsx('font-bold', row.is_low_stock ? 'text-accent-red' : 'text-accent-green')}>
          {formatNumber(v)}
          {row.is_low_stock && <Badge color="red" className="ml-2">Chini</Badge>}
        </span>
      ),
    },
    can('products.cost') && {
      key: 'cost_price', header: 'Bei Ununuzi',
      render: (v) => <span className="text-text-secondary text-sm">{formatCurrency(v)}</span>,
    },
    {
      key: 'selling_price', header: 'Bei Mauzo',
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
              title="Tuma kwa Kioski cha POS"
            >
              <SendHorizontal size={15} className="text-primary-light" />
            </Button>
          )}
          {onAdjust && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onAdjust(row)}
              title="Rekebisha Bidhaa"
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
      emptyTitle="Hakuna bidhaa zilizopatikana"
    />
  )
}
