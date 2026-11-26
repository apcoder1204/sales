import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserPlus, Search } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { customerService } from '@services/customerService'
import { usePagination } from '@hooks/usePagination'
import { usePermission } from '@hooks/usePermission'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import { formatCurrency, formatDate } from '@utils/formatters'
import SW from '@constants/sw'
import CustomerFormModal from './CustomerFormModal'
import RiskFlags from './RiskFlags'

export default function CustomersPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [status, setStatus] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const pagination = usePagination(20)
  const branchFilter = useActiveBranchFilter()
  const { can } = usePermission()
  const navigate = useNavigate()

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQ(q.trim()); pagination.reset() }, 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await customerService.search(debouncedQ, {
        status: status || undefined, ...branchFilter,
        page: pagination.page, per_page: pagination.pageSize,
      })
      setRows(res.items || [])
      pagination.setTotal(res.total || 0)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, status, branchFilter.branch_id, pagination.page])

  useEffect(() => { load() }, [load])

  const columns = [
    {
      key: 'name', header: SW.wateja.mteja,
      render: (v, row) => (
        <div>
          <p className="font-medium text-text-primary">{v}</p>
          <p className="text-xs text-text-muted">{row.customer_no}</p>
        </div>
      ),
    },
    { key: 'phone', header: SW.wateja.simu },
    {
      key: 'balance', header: SW.wateja.salioLaDeni,
      render: (v) => <span className={Number(v) > 0 ? 'font-semibold text-accent-red' : ''}>{formatCurrency(v)}</span>,
    },
    { key: 'credit_limit', header: SW.wateja.kikomo, render: (v) => formatCurrency(v) },
    {
      key: 'overdue', header: SW.wateja.yaliyochelewa,
      render: (v) => (Number(v) > 0 ? <Badge color="red">{formatCurrency(v)}</Badge> : '-'),
    },
    { key: 'last_payment_at', header: SW.wateja.malipoYaMwisho, render: (v) => formatDate(v) },
    {
      key: 'status', header: SW.wateja.hali,
      render: (v, row) => (
        <div>
          <Badge color={v === 'active' ? 'green' : 'gray'}>{SW.hali.mteja[v] || v}</Badge>
          <RiskFlags flags={row.flags} className="mt-1" />
        </div>
      ),
    },
  ]

  return (
    <PageWrapper
      title={SW.wateja.wateja}
      subtitle={SW.wateja.subtitle}
      action={can('customers.write') && (
        <Button leftIcon={<UserPlus size={16} />} onClick={() => setFormOpen(true)}>{SW.wateja.ongezaMteja}</Button>
      )}
    >
      <div className="flex flex-col sm:flex-row gap-3">
        <Input
          containerClassName="flex-1"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={SW.wateja.tafuta}
          leftIcon={<Search size={14} />}
        />
        <Select
          containerClassName="w-48"
          value={status}
          onChange={(e) => { setStatus(e.target.value); pagination.reset() }}
          options={[
            { value: '', label: SW.wateja.haliZote },
            { value: 'active', label: SW.hali.mteja.active },
            { value: 'inactive', label: SW.hali.mteja.inactive },
          ]}
        />
      </div>

      <DataTable
        columns={columns}
        data={rows}
        loading={loading}
        pagination={pagination}
        onRowClick={(row) => navigate(`/wateja/${row.id}`)}
        emptyTitle={SW.wateja.hakunaWateja}
      />

      <CustomerFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={(c) => navigate(`/wateja/${c.id}`)}
      />
    </PageWrapper>
  )
}
