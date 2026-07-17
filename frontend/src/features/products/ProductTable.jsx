import React from 'react'
import { Pencil } from 'lucide-react'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import { formatCurrency } from '@utils/formatters'
import { usePermission } from '@hooks/usePermission'
import SW from '@constants/sw'

export default function ProductTable({ products, loading, onEdit, pagination }) {
  const { can } = usePermission()
  // Optional columns appear only when at least one product has data in that field
  const hasFamily = products.some((p) => p.family_name)
  const hasDescription = products.some((p) => p.description)

  const columns = [
    {
      key: 'product_code',
      header: 'Msimbo',
      width: 110,
      render: (v) => <span className="font-mono text-xs text-primary-light">{v}</span>,
    },
    {
      key: 'name',
      header: 'Jina la Bidhaa',
      render: (v) => <span className="font-medium text-text-primary">{v}</span>,
    },
    {
      key: 'category',
      header: 'Jamii',
      render: (v) => <span className="text-text-secondary text-sm">{v}</span>,
    },
    hasFamily && {
      key: 'family_name',
      header: 'Familia / Brand',
      render: (v) => <span className="text-text-secondary text-sm">{v || ''}</span>,
    },
    {
      key: 'unit',
      header: 'Kipimo',
      width: 90,
      render: (v) => <span className="text-text-secondary text-sm">{v || 'Kipande'}</span>,
    },
    can('products.cost') && {
      key: 'cost_price',
      header: SW.bidhaa.beiGhali,
      render: (v) => <span className="text-text-secondary">{formatCurrency(v)}</span>,
    },
    {
      key: 'selling_price',
      header: SW.bidhaa.beiUzaji,
      render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span>,
    },
    {
      key: 'minimum_stock',
      header: 'Hisa Ndogo',
      width: 95,
      render: (v) => <span className="text-text-muted text-sm">{v ?? 5}</span>,
    },
    hasDescription && {
      key: 'description',
      header: 'Maelezo',
      render: (v) => (
        <span className="text-text-muted text-xs line-clamp-2 max-w-48 block">{v}</span>
      ),
    },
    {
      key: 'status',
      header: 'Hali',
      width: 90,
      render: (v) => (
        <Badge color={v === 'active' ? 'green' : v === 'discontinued' ? 'red' : 'yellow'}>
          {v === 'active' ? SW.bidhaa.hai : v === 'discontinued' ? SW.bidhaa.imekomeshwa : SW.bidhaa.imesimama}
        </Badge>
      ),
    },
    onEdit && {
      key: '_actions',
      header: '',
      render: (_, row) => (
        <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); onEdit(row) }}>
          <Pencil size={15} />
        </Button>
      ),
    },
  ].filter(Boolean)

  return (
    <DataTable
      columns={columns}
      data={products}
      loading={loading}
      pagination={pagination}
      emptyTitle="Hakuna bidhaa zilizopatikana"
    />
  )
}
