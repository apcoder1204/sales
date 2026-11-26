import React, { useCallback, useEffect, useState } from 'react'
import { FileDown, FileSpreadsheet } from 'lucide-react'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import SendWhatsAppButton from '@components/ui/SendWhatsAppButton'
import { customerService } from '@services/customerService'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { buildPDF, downloadExcel, downloadPDF } from '@utils/reportExport'
import { formatCurrency, formatDate } from '@utils/formatters'
import SW from '@constants/sw'

const iso = (d) => d.toLocaleDateString('en-CA')

// Account statement (brief §13): opening balance, every ledger entry in the
// range with a running balance, closing balance — the server builds it from
// the append-only ledger, so the closing figure always equals the balance.
export default function StatementTab({ customerId, branchFilter }) {
  const today = new Date()
  const [from, setFrom] = useState(iso(new Date(today.getFullYear(), today.getMonth(), 1)))
  const [to, setTo] = useState(iso(today))
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(null)
  const toast = useToast()
  const T = SW.taarifa

  const load = useCallback(async () => {
    if (!from || !to || from > to) return
    setLoading(true)
    try {
      setData(await customerService.statement(customerId, { date_from: from, date_to: to, ...branchFilter }))
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, from, to, branchFilter.branch_id])

  useEffect(() => { load() }, [load])

  const period = `${from} – ${to}`
  const exportAs = async (format) => {
    setExporting(format)
    try {
      if (format === 'pdf') await downloadPDF('customer_statement', data, period)
      else await downloadExcel('customer_statement', data, period)
    } catch {
      toast.error(SW.ripoti.imeshindwaKupakua)
    } finally {
      setExporting(null)
    }
  }

  const cell = 'px-3 py-2 text-right whitespace-nowrap'
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <Input label={T.kuanzia} type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />
        <Input label={T.hadi} type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
        {data && (
          <div className="flex flex-wrap gap-2 ml-auto">
            <Button variant="secondary" leftIcon={<FileDown size={15} />} loading={exporting === 'pdf'} disabled={!!exporting} onClick={() => exportAs('pdf')}>
              {SW.ripoti.pakuaPdf}
            </Button>
            <Button variant="secondary" leftIcon={<FileSpreadsheet size={15} />} loading={exporting === 'excel'} disabled={!!exporting} onClick={() => exportAs('excel')}>
              {SW.ripoti.pakuaExcel}
            </Button>
            <SendWhatsAppButton
              reportType="customer_statement"
              getPdf={async () => ({ ...(await buildPDF('customer_statement', data, period)), periodLabel: period })}
              branchId={branchFilter.branch_id}
              disabled={!!exporting}
            />
          </div>
        )}
      </div>

      {loading && <p className="text-sm text-text-muted animate-pulse">{SW.ripoti.inapakiaRipoti}</p>}
      {data && !loading && (
        <div className="glass-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted border-b border-border">
                <th className="px-3 py-2 text-left">{SW.wateja.tarehe}</th>
                <th className="px-3 py-2 text-left">{SW.wateja.kumbukumbu}</th>
                <th className="px-3 py-2 text-left">{T.maelezo}</th>
                <th className="px-3 py-2 text-left">{SW.wateja.tawi}</th>
                <th className={cell}>{T.debiti}</th>
                <th className={cell}>{T.krediti}</th>
                <th className={cell}>{T.salio}</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border/50 text-text-secondary">
                <td className="px-3 py-2">{formatDate(data.date_from)}</td>
                <td colSpan={3} className="px-3 py-2 font-medium">{T.salioLaKuanzia}</td>
                <td className={cell} /><td className={cell} />
                <td className={`${cell} font-medium`}>{formatCurrency(data.opening_balance)}</td>
              </tr>
              {data.lines.map((l, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="px-3 py-2 whitespace-nowrap">{formatDate(l.date)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{l.reference}</td>
                  <td className="px-3 py-2">{l.description}</td>
                  <td className="px-3 py-2">{l.branch_name}</td>
                  <td className={cell}>{Number(l.debit) ? formatCurrency(l.debit) : ''}</td>
                  <td className={`${cell} text-accent-green`}>{Number(l.credit) ? formatCurrency(l.credit) : ''}</td>
                  <td className={`${cell} font-medium`}>{formatCurrency(l.balance)}</td>
                </tr>
              ))}
              {data.lines.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-4 text-center text-text-muted">{T.hakunaMiamala}</td></tr>
              )}
              <tr className="font-semibold">
                <td className="px-3 py-2">{formatDate(data.date_to)}</td>
                <td colSpan={3} className="px-3 py-2">{T.salioLaMwisho}</td>
                <td className={cell}>{formatCurrency(data.total_debit)}</td>
                <td className={cell}>{formatCurrency(data.total_credit)}</td>
                <td className={`${cell} text-accent-red`}>{formatCurrency(data.closing_balance)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
