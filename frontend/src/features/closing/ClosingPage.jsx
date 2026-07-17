import React, { useState, useEffect, useCallback } from 'react'
import { Lock, Unlock, Wallet, Smartphone, Landmark, Receipt } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import KpiCard from '@components/ui/KpiCard'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import Button from '@components/ui/Button'
import Badge from '@components/ui/Badge'
import DataTable from '@components/tables/DataTable'
import { closingService } from '@services/closingService'
import { userService } from '@services/userService'
import { useAuth } from '@hooks/useAuth'
import { usePermission } from '@hooks/usePermission'
import { useApi } from '@hooks/useApi'
import { useToast } from '@hooks/useToast'
import { isGlobalRole } from '@utils/permissions'
import { formatCurrency, formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

// Use LOCAL date parts, not toISOString() (which is UTC) — otherwise the
// closing page can ask for the wrong business day during the few hours after
// local midnight when the UTC calendar date still lags a day behind.
const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function ClosingPage() {
  const { user } = useAuth()
  const { can } = usePermission()
  const { loading, call } = useApi()
  const toast = useToast()
  const isGlobal = isGlobalRole(user)

  const [branches, setBranches] = useState([])
  const [branchId, setBranchId] = useState('')
  const [businessDate, setBusinessDate] = useState(todayStr())
  const [preview, setPreview] = useState(null)
  const [countedCash, setCountedCash] = useState('')
  const [notes, setNotes] = useState('')
  const [matumizi, setMatumizi] = useState([])
  const [history, setHistory] = useState([])
  const [reopenReason, setReopenReason] = useState({})

  useEffect(() => {
    if (!isGlobal) { setBranchId(user?.branch_id || ''); return }
    userService.branches().then((b) => {
      const pos = b.filter((x) => x.branch_type === 'pos_point')
      setBranches(pos.map((x) => ({ value: x.id, label: x.name })))
      if (pos.length > 0) setBranchId(pos[0].id)
    }).catch(() => {})
  }, [isGlobal, user])

  const loadPreview = useCallback(async () => {
    if (!branchId) return
    try {
      const data = await closingService.preview(branchId, businessDate)
      setPreview(data)
      setCountedCash('')
      setNotes('')
      setMatumizi([])
    } catch (_) {
      setPreview(null)
    }
  }, [branchId, businessDate])

  const loadHistory = useCallback(async () => {
    if (!branchId) return
    const res = await closingService.list({ branch_id: branchId, per_page: 10 })
    setHistory(res.items || [])
  }, [branchId])

  useEffect(() => { loadPreview() }, [loadPreview])
  useEffect(() => { loadHistory() }, [loadHistory])

  const setMatumiziField = (i, k) => (e) => setMatumizi((prev) => prev.map((m, idx) => idx === i ? { ...m, [k]: e.target.value } : m))
  const addMatumizi = () => setMatumizi((p) => [...p, { description: '', amount: '' }])
  const removeMatumizi = (i) => setMatumizi((p) => p.filter((_, idx) => idx !== i))

  const handleClose = () => call(
    () => closingService.close({
      branch_id: branchId,
      business_date: businessDate,
      counted_cash: countedCash || undefined,
      notes: notes || undefined,
      expenses: matumizi
        .filter((m) => m.description && m.amount)
        .map((m) => ({ description: m.description, amount: parseFloat(m.amount) })),
    }),
    {
      successMsg: 'Siku imefungwa',
      onSuccess: () => { loadPreview(); loadHistory() },
    }
  )

  const handleReopen = (closing) => call(
    () => closingService.reopen(closing.id, reopenReason[closing.id] || ''),
    {
      successMsg: 'Siku imefunguliwa tena',
      onSuccess: () => { loadPreview(); loadHistory() },
    }
  )

  const variance = countedCash !== '' && preview
    ? parseFloat(countedCash) - preview.total_cash
    : null

  const totalMatumizi = matumizi.reduce((sum, m) => sum + (parseFloat(m.amount) || 0), 0)
  // Mirrors the backend's netting: a shortage is explained by expenses paid
  // out of the drawer (added back), a surplus by noting where the extra came
  // from (subtracted back) — same {description, amount} shape either way.
  const unexplainedVariance = variance === null ? null
    : variance < 0 ? variance + totalMatumizi
    : variance - totalMatumizi

  const closedToday = history.find((h) => h.business_date === businessDate && h.status === 'closed')

  const branchOptions = branches

  const historyColumns = [
    { key: 'business_date', header: SW.ufungaji.tarehe },
    {
      key: 'status', header: SW.common.hali,
      render: (v) => <Badge color={v === 'closed' ? 'green' : 'yellow'}>{v === 'closed' ? SW.ufungaji.imefungwa : SW.ufungaji.wazi}</Badge>,
    },
    { key: 'total_revenue', header: SW.ufungaji.jumlaKuu, render: (v) => formatCurrency(v) },
    {
      key: 'cash_variance', header: SW.ufungaji.tofauti,
      render: (v) => v == null ? '—' : (
        <span className={Math.abs(v) < 1 ? 'text-text-secondary' : v > 0 ? 'text-accent-green' : 'text-accent-red'}>
          {formatCurrency(v)}
        </span>
      ),
    },
    {
      key: 'total_expenses', header: SW.ufungaji.matumizi,
      render: (v) => Number(v) > 0 ? formatCurrency(v) : '—',
    },
    { key: 'closed_by', header: SW.ufungaji.aliyefunga, render: (v) => v || '—' },
    { key: 'closed_at', header: 'Wakati', render: (v) => v ? formatDateTime(v) : '—' },
    {
      key: '_actions', header: '',
      render: (_, row) => (
        row.status === 'closed' && can('closing.reopen') ? (
          <div className="flex items-center gap-2">
            <Input
              placeholder={SW.ufungaji.sababuYaKufungua}
              value={reopenReason[row.id] || ''}
              onChange={(e) => setReopenReason((p) => ({ ...p, [row.id]: e.target.value }))}
              containerClassName="w-40"
            />
            <Button
              variant="secondary" size="sm" leftIcon={<Unlock size={14} />}
              disabled={!reopenReason[row.id]}
              onClick={() => handleReopen(row)}
            >
              {SW.ufungaji.fungua}
            </Button>
          </div>
        ) : null
      ),
    },
  ]

  return (
    <PageWrapper title={SW.ufungaji.ufungaji} subtitle="Funga siku ya biashara na uangalie muhtasari wa malipo">
      <div className="glass-card p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {isGlobal && (
            <Select label={SW.ufungaji.tawi} value={branchId} onChange={(e) => setBranchId(e.target.value)} options={branchOptions} placeholder="Chagua tawi..." />
          )}
          <Input label={SW.ufungaji.tarehe} type="date" value={businessDate} onChange={(e) => setBusinessDate(e.target.value)} max={todayStr()} />
        </div>

        {preview && (
          <>
            {preview.already_closed && (
              <div className="p-3 rounded-lg bg-accent-green-muted space-y-2">
                <div className="flex items-center gap-2 text-accent-green text-sm">
                  <Lock size={16} /> {SW.ufungaji.imefungwaTayari}
                </div>
                {closedToday && closedToday.expenses.length > 0 && (
                  <div className="pt-2 border-t border-accent-green/20 space-y-1">
                    <p className="text-xs font-medium text-text-secondary">{SW.ufungaji.matumizi}</p>
                    {closedToday.expenses.map((e) => (
                      <div key={e.id} className="flex justify-between text-xs text-text-secondary">
                        <span>{e.description}</span>
                        <span>{formatCurrency(e.amount)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <KpiCard title={SW.ufungaji.taslimu} value={formatCurrency(preview.total_cash)} icon={Wallet} color="green" />
              <KpiCard title={SW.ufungaji.simuLipa} value={formatCurrency(preview.total_mobile_money)} icon={Smartphone} color="blue" />
              <KpiCard title={SW.ufungaji.benki} value={formatCurrency(preview.total_bank_transfer)} icon={Landmark} color="purple" />
              <KpiCard title={SW.ufungaji.jumlaKuu} value={formatCurrency(preview.total_revenue)} icon={Receipt} color="yellow" />
            </div>
            <p className="text-xs text-text-muted">{SW.ufungaji.idadiMauzo}: {preview.total_sales_count}</p>

            {!preview.already_closed && can('closing.close') && (
              <div className="border-t border-border pt-4 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Input
                    label={SW.ufungaji.fedhaIliyohesabiwa}
                    type="number" min="0" value={countedCash}
                    onChange={(e) => setCountedCash(e.target.value)}
                    placeholder={String(preview.total_cash)}
                  />
                  <Input label={SW.ufungaji.maelezo} value={notes} onChange={(e) => setNotes(e.target.value)} />
                </div>
                {variance !== null && (
                  <p className={`text-sm font-medium ${variance === 0 ? 'text-text-secondary' : variance > 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                    {SW.ufungaji.tofauti}: {formatCurrency(variance)}
                  </p>
                )}

                {variance !== null && variance !== 0 && (
                  <div className="space-y-2 border border-accent-yellow/20 bg-accent-yellow-muted/40 rounded-lg p-3">
                    <p className="text-sm font-medium text-accent-yellow">
                      {variance < 0 ? SW.ufungaji.pungufuLaFedha : SW.ufungaji.zaidiLaFedha}: {formatCurrency(Math.abs(variance))}
                    </p>
                    <p className="text-xs text-text-muted">{SW.ufungaji.elezaTofauti}</p>

                    {matumizi.map((m, i) => (
                      <div key={i} className="flex gap-2 items-end">
                        <Input
                          placeholder={SW.ufungaji.maelezoYaMatumizi}
                          value={m.description}
                          onChange={setMatumiziField(i, 'description')}
                          containerClassName="flex-1"
                        />
                        <Input
                          type="number" min="0" placeholder={SW.ufungaji.kiasi}
                          value={m.amount}
                          onChange={setMatumiziField(i, 'amount')}
                          containerClassName="w-28"
                        />
                        <Button variant="danger" size="icon" onClick={() => removeMatumizi(i)}>×</Button>
                      </div>
                    ))}
                    <Button variant="ghost" size="sm" onClick={addMatumizi}>{SW.ufungaji.ongezaMatumizi}</Button>

                    {totalMatumizi > 0 && (
                      <p className={`text-xs font-semibold ${Math.abs(unexplainedVariance) < 1 ? 'text-accent-green' : 'text-accent-red'}`}>
                        {Math.abs(unexplainedVariance) < 1
                          ? SW.ufungaji.imeelezwaKikamilifu
                          : `${SW.ufungaji.tofautiIsiyoelezwa}: ${formatCurrency(unexplainedVariance)}`}
                      </p>
                    )}
                  </div>
                )}

                <Button onClick={handleClose} loading={loading} leftIcon={<Lock size={16} />}>
                  {SW.ufungaji.fungaSiku}
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">{SW.ufungaji.historia}</h3>
        <DataTable columns={historyColumns} data={history} loading={false} emptyTitle="Hakuna historia ya ufungaji" />
      </div>
    </PageWrapper>
  )
}
