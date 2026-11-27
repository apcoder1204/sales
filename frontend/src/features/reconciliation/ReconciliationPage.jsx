import React, { useCallback, useEffect, useState } from 'react'
import { Info, PlayCircle } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { reconciliationService } from '@services/reconciliationService'
import { useBranch } from '@hooks/useBranch'
import { usePermission } from '@hooks/usePermission'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { getReportPeriods } from '@utils/constants'
import { formatCurrency, formatDate, formatDateTime, formatNumber } from '@utils/formatters'
import { codeText } from '@utils/reconciliationLabels'
import SW from '@constants/sw'
import CustomerPicker from '@features/pos/CustomerPicker'
import ExceptionsTable from './ExceptionsTable'
import ExceptionStatusModal from './ExceptionStatusModal'

export const RUN_COLOR = { PASSED: 'green', WARNING: 'yellow', FAILED: 'red' }
const CODES = Object.keys(SW.upatanisho.kodi)

// Upatanisho wa Hesabu (spec §8): start a reconciliation, see what it found,
// and (admins) review each discrepancy. A run only reads; corrections are
// always the normal actions elsewhere in the system.
export default function ReconciliationPage() {
  const U = SW.upatanisho
  const { can } = usePermission()
  const canResolve = can('reconciliation.resolve')
  const toast = useToast()
  const [tab, setTab] = useState('matokeo')
  const [runs, setRuns] = useState([])
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [selected, setSelected] = useState(null) // run detail
  const [statusFor, setStatusFor] = useState(null)
  const [running, setRunning] = useState(false)

  const openRun = useCallback(async (id) => {
    try {
      setSelected(await reconciliationService.runs.get(id))
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadRuns = useCallback(async (selectId) => {
    setLoadingRuns(true)
    try {
      const list = await reconciliationService.runs.list()
      setRuns(list)
      const id = selectId || list[0]?.id
      if (id) await openRun(id)
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setLoadingRuns(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openRun])

  useEffect(() => { loadRuns() }, [loadRuns])

  const start = async (payload) => {
    setRunning(true)
    try {
      const run = await reconciliationService.runs.create(payload)
      toast.success(`${U.umekamilika}: ${run.run_no} — ${U.haliRun[run.status]}`)
      setTab('matokeo')
      await loadRuns(run.id)
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setRunning(false)
    }
  }

  // "Check again": the narrowest scope that covers the affected record.
  const recheck = (e) => {
    if (e.sale_id) return start({ scope: 'sale', sale_id: e.sale_id })
    if (e.payment_id) return start({ scope: 'payment', payment_id: e.payment_id })
    if (e.customer?.id && e.group !== 'G' && e.group !== 'F') return start({ scope: 'customer', customer_id: e.customer.id })
    if (e.branch_id) return start({ scope: 'branch', branch_id: e.branch_id })
    return start({ scope: 'all' })
  }

  const [refreshKey, setRefreshKey] = useState(0)
  const afterStatus = () => {
    if (selected) openRun(selected.id)
    setRefreshKey((k) => k + 1)
  }

  return (
    <PageWrapper title={U.kichwa} subtitle={U.subtitle}>
      <div className="glass-card p-3 flex gap-2 text-sm text-text-secondary">
        <Info size={16} className="shrink-0 mt-0.5" />
        <p>{U.haiRekebishi}</p>
      </div>

      <RunForm onStart={start} running={running} />

      <div className="flex items-center gap-2 border-b border-border">
        {['matokeo', 'tofautiZote'].map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === t ? 'border-primary text-text-primary' : 'border-transparent text-text-muted'}`}>
            {U[t]}
          </button>
        ))}
      </div>

      {tab === 'matokeo' && (
        <>
          <RunsTable runs={runs} loading={loadingRuns} selectedId={selected?.id} onSelect={(r) => openRun(r.id)} />
          {selected && <RunDetail run={selected} canResolve={canResolve} onChangeStatus={setStatusFor} onRecheck={recheck} />}
        </>
      )}
      {tab === 'tofautiZote' && (
        <AllExceptions canResolve={canResolve} onChangeStatus={setStatusFor} onRecheck={recheck} refreshKey={refreshKey} />
      )}

      <ExceptionStatusModal exception={statusFor} onClose={() => setStatusFor(null)} onDone={afterStatus} />
    </PageWrapper>
  )
}

function RunForm({ onStart, running }) {
  const U = SW.upatanisho
  const { branches } = useBranch()
  const posBranches = (branches || []).filter((b) => b.branch_type === 'pos_point')
  const [scope, setScope] = useState('all')
  const [branchId, setBranchId] = useState('')
  const [customer, setCustomer] = useState(null)
  const [period, setPeriod] = useState('month')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const withPeriod = scope === 'all' || scope === 'branch'
  const ready = (scope !== 'branch' || branchId) && (scope !== 'customer' || customer)
    && (!withPeriod || period !== 'custom' || (from && to))

  const submit = () => {
    const payload = { scope }
    if (scope === 'branch') payload.branch_id = branchId
    if (scope === 'customer') payload.customer_id = customer.id
    if (withPeriod) {
      payload.period = period
      if (period === 'custom') Object.assign(payload, { from_date: from, to_date: to })
    }
    onStart(payload)
  }

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <Select
          label={U.kipimo}
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          options={['all', 'branch', 'customer'].map((s) => ({ value: s, label: U.vipimo[s] }))}
        />
        {scope === 'branch' && (
          <Select
            label={SW.wateja.tawi}
            value={branchId}
            onChange={(e) => setBranchId(e.target.value)}
            options={[{ value: '', label: '—' }, ...posBranches.map((b) => ({ value: b.id, label: b.name }))]}
          />
        )}
        {scope === 'customer' && (
          <div className="md:col-span-2"><CustomerPicker value={customer} onChange={setCustomer} label={SW.wateja.mteja} /></div>
        )}
        {withPeriod && (
          <Select label={U.kipindi} value={period} onChange={(e) => setPeriod(e.target.value)} options={getReportPeriods()} />
        )}
        {withPeriod && period === 'custom' && (
          <div className="grid grid-cols-2 gap-2">
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        )}
        <Button leftIcon={<PlayCircle size={16} />} loading={running} disabled={!ready || running} onClick={submit}>
          {U.anzisha}
        </Button>
      </div>
      {withPeriod && <p className="text-xs text-text-muted">{U.kipindiMaelezo}</p>}
    </div>
  )
}

function scopeText(r) {
  const U = SW.upatanisho
  const what = r.branch_name || r.customer?.name || r.sale_no || r.payment_no
  return what ? `${U.vipimo[r.scope]}: ${what}` : U.vipimo[r.scope]
}

function RunsTable({ runs, loading, selectedId, onSelect }) {
  const U = SW.upatanisho
  const columns = [
    { key: 'run_no', header: U.namba, render: (v, r) => <span className={r.id === selectedId ? 'font-semibold text-primary' : ''}>{v}</span> },
    { key: 'started_at', header: U.wakati, render: (v) => <span className="whitespace-nowrap">{formatDateTime(v)}</span> },
    { key: 'scope', header: U.kipimo, render: (_, r) => scopeText(r) },
    { key: 'date_from', header: U.kipindi, render: (v, r) => `${formatDate(v)} – ${formatDate(r.date_to)}` },
    { key: 'run_by_name', header: U.aliyeanzisha },
    { key: 'records_examined', header: U.rekodi, render: (v) => formatNumber(v) },
    { key: 'discrepancy_count', header: U.tofauti, render: (v, r) => `${formatNumber(v)}${r.warning_count ? ` (${U.maonyo}: ${r.warning_count})` : ''}` },
    { key: 'status', header: U.hali, render: (v) => <Badge color={RUN_COLOR[v]}>{U.haliRun[v]}</Badge> },
  ]
  return <DataTable columns={columns} data={runs} loading={loading} onRowClick={onSelect} emptyTitle={U.hakunaUpatanisho} />
}

function RunDetail({ run, canResolve, onChangeStatus, onRecheck }) {
  const U = SW.upatanisho
  const branches = run.summary?.branches || []
  const cols = [
    ['sales_total', U.mauzo], ['till_collected', U.yaliyolipwaMauzoni], ['credit_given', U.mkopo],
    ['debt_collected', U.madeniYaliyolipwa], ['voided_total', U.yaliyobatilishwa], ['pnl_revenue', U.mapatoPL],
    ['receivables', U.madeniHati], ['ledger', U.madeniLeja],
  ]
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-base font-semibold text-text-primary">{run.run_no}</h3>
        <Badge color={RUN_COLOR[run.status]}>{U.haliRun[run.status]}</Badge>
        <span className="text-sm text-text-secondary">
          {scopeText(run)} · {U.rekodi}: {formatNumber(run.records_examined)} · {U.tofauti}: {formatNumber(run.discrepancy_count)}
          {run.suppressed_count ? ` · ${U.zilizopuuzwa}: ${run.suppressed_count}` : ''}
        </span>
      </div>
      {Object.keys(run.by_code || {}).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(run.by_code).map(([code, n]) => (
            <span key={code} className="text-xs px-2 py-1 rounded bg-bg-hover" title={codeText(code)}>{code} × {n}</span>
          ))}
        </div>
      )}
      {branches.length > 0 && (
        <div className="glass-card overflow-x-auto">
          <p className="px-4 pt-3 text-sm font-medium text-text-primary">{U.muhtasariTawi}</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted border-b border-border">
                <th className="px-3 py-2 text-left">{SW.wateja.tawi}</th>
                {cols.map(([k, label]) => <th key={k} className="px-3 py-2 text-right">{label}</th>)}
              </tr>
            </thead>
            <tbody>
              {branches.map((b) => (
                <tr key={b.branch_id} className="border-b border-border/50">
                  <td className="px-3 py-2">{b.branch_name}</td>
                  {cols.map(([k]) => (
                    <td key={k} className={`px-3 py-2 text-right whitespace-nowrap ${k === 'ledger' && b.ledger !== b.receivables ? 'text-accent-red font-semibold' : ''}`}>
                      {b[k] == null ? '—' : formatCurrency(Number(b[k]))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ExceptionsTable rows={run.exceptions} canResolve={canResolve} onChangeStatus={onChangeStatus} onRecheck={onRecheck} />
    </div>
  )
}

function AllExceptions({ canResolve, onChangeStatus, onRecheck, refreshKey }) {
  const U = SW.upatanisho
  const toast = useToast()
  const [status, setStatus] = useState('')
  const [code, setCode] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    reconciliationService.exceptions.list({ status: status || undefined, code: code || undefined })
      .then((r) => { if (alive) setRows(r) })
      .catch((err) => toast.error(resolveApiErrorMessage(err)))
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, code, refreshKey])

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <Select
          containerClassName="w-64"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[
            { value: '', label: U.zinazoendelea },
            { value: 'all', label: U.zote },
            ...Object.entries(U.haliTofauti).map(([k, v]) => ({ value: k, label: v })),
          ]}
        />
        <Select
          containerClassName="w-72"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          options={[{ value: '', label: U.ainaZote }, ...CODES.map((c) => ({ value: c, label: c }))]}
        />
      </div>
      <ExceptionsTable rows={rows} loading={loading} canResolve={canResolve} onChangeStatus={onChangeStatus} onRecheck={onRecheck} />
    </div>
  )
}
