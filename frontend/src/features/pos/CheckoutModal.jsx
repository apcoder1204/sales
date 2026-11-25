import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import Divider from '@components/ui/Divider'
import { useCart } from '@hooks/useCart'
import { useAuth } from '@hooks/useAuth'
import { useApi } from '@hooks/useApi'
import { useBranch } from '@hooks/useBranch'
import { saleService } from '@services/saleService'
import { formatCurrency } from '@utils/formatters'
import { getPaymentMethods } from '@utils/constants'
import { isGlobalRole } from '@utils/permissions'
import SW from '@constants/sw'
import CustomerPicker from './CustomerPicker'

const MAX_LINES = 3
const NEEDS_REFERENCE = ['mobile_money', 'bank_transfer']
// Whole shillings only on the client; the server re-checks every amount.
const toInt = (v) => {
  const n = parseInt(String(v ?? '').replace(/[^0-9]/g, ''), 10)
  return Number.isFinite(n) ? n : 0
}

export default function CheckoutModal({ open, onClose, onComplete }) {
  const { items, subtotal, total, clear } = useCart()
  const { user } = useAuth()
  const { loading, call } = useApi()
  const { activeBranchId, branches } = useBranch()
  const [lines, setLines] = useState([{ method: 'cash', amount: '', reference: '' }])
  const [customer, setCustomer] = useState(null)

  // One key per checkout attempt, reused across retries (a slow/ambiguous
  // network response the cashier retries by clicking Sell again, or a
  // double-tap before the button's disabled state takes effect) so the
  // backend replays the first sale instead of creating a second one.
  // Regenerated each time the modal opens — a fresh open is a new attempt.
  const idempotencyKeyRef = useRef(null)
  useEffect(() => {
    if (open) {
      idempotencyKeyRef.current = crypto.randomUUID()
      // Most sales are paid in full in cash: start there.
      setLines([{ method: 'cash', amount: String(Math.round(total)), reference: '' }])
      setCustomer(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const isGlobal = isGlobalRole(user)
  const totalInt = Math.round(total)
  const paid = useMemo(() => lines.reduce((sum, l) => sum + toInt(l.amount), 0), [lines])
  const deni = totalInt - paid
  const overpaid = deni < 0
  const missingReference = lines.some(
    (l) => toInt(l.amount) > 0 && NEEDS_REFERENCE.includes(l.method) && !l.reference.trim()
  )
  const available = customer?.summary?.available_credit
  const overLimitHint = deni > 0 && available !== undefined && available !== null && deni > Number(available)

  const setLine = (i, patch) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  const payRemainder = (i) => setLine(i, { amount: String(toInt(lines[i].amount) + Math.max(0, deni)) })
  const addLine = () => setLines((ls) => [...ls, { method: 'mobile_money', amount: String(Math.max(0, deni)), reference: '' }])
  const removeLine = (i) => setLines((ls) => ls.filter((_, j) => j !== i))

  // A sale always sells from wherever the global branch switcher (top bar)
  // is currently pointed — there is no separate in-checkout branch choice,
  // and it never silently falls back to "the first POS branch" if the
  // switcher is on ALL or on a non-sellable branch (e.g. Main Store, a
  // warehouse). If it isn't a valid pos_point branch, checkout is blocked
  // with a message telling the cashier/admin to switch branch first — a
  // wrong guess here means the sale (and its stock deduction) lands on the
  // wrong branch, which is far worse than one extra click.
  const activeBranch = isGlobal ? branches.find((b) => b.id === activeBranchId) : null
  const globalBranchReady = !isGlobal || activeBranch?.branch_type === 'pos_point'
  const effectiveBranchId = isGlobal ? activeBranchId : user?.branch_id

  const handleCheckout = async () => {
    if (!canSubmit) return

    const payload = {
      branch_id: effectiveBranchId,
      customer_id: customer?.id || undefined,
      payments: lines
        .filter((l) => toInt(l.amount) > 0)
        .map((l) => ({
          method: l.method,
          amount: String(toInt(l.amount)),
          reference: l.reference.trim() || undefined,
        })),
      items: items.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
    }

    let result
    try {
      result = await call(() => saleService.create(payload, idempotencyKeyRef.current), {
        successMsg: SW.mauzo.mauzoYamefanikiwa,
      })
    } catch {
      return // useApi already showed the translated error (e.g. credit limit numbers)
    }

    if (result) {
      clear()
      onComplete(result)
    }
  }

  const canSubmit = items.length > 0
    && !overpaid
    && !missingReference
    && !(deni > 0 && !customer)
    && Boolean(effectiveBranchId)
    && globalBranchReady

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={SW.mauzo.thibitisha}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={loading} onClick={handleCheckout} disabled={!canSubmit}>
            {SW.mauzo.kuuza}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {/* Branch context — read-only, driven entirely by the top branch
            switcher. Global roles see which branch the sale will post to;
            if the switcher isn't on a sellable branch, checkout is blocked
            below rather than guessing one. */}
        {isGlobal && (
          globalBranchReady ? (
            <p className="text-sm text-text-secondary">
              {SW.mauzo.tawiLaMauzo}: <span className="font-medium text-text-primary">{activeBranch.name}</span>
            </p>
          ) : (
            <p className="text-sm text-accent-red">{SW.mauzo.chaguaTawiLaMauzoKwanza}</p>
          )
        )}

        {/* Summary */}
        <div className="glass-card p-4 space-y-2">
          <div className="flex justify-between text-sm text-text-secondary">
            <span>{SW.mauzo.jumla}</span><span>{formatCurrency(subtotal)}</span>
          </div>
          <Divider />
          <div className="flex justify-between font-bold text-text-primary">
            <span>{SW.mauzo.jumlaKuu}</span>
            <span className="text-accent-green text-lg">{formatCurrency(total)}</span>
          </div>
        </div>

        {/* Payment lines: one or more methods; whatever isn't paid is debt */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-text-secondary">{SW.mauzo.malipo}</p>
          {lines.map((line, i) => (
            <div key={i} className="glass-card p-3 space-y-2">
              <div className="flex gap-2 items-end">
                <Select
                  containerClassName="flex-1"
                  label={SW.mauzo.njiaYaLipa}
                  value={line.method}
                  onChange={(e) => setLine(i, { method: e.target.value })}
                  options={getPaymentMethods()}
                />
                <Input
                  containerClassName="flex-1"
                  label={SW.mauzo.kiasi}
                  inputMode="numeric"
                  value={line.amount}
                  onChange={(e) => setLine(i, { amount: e.target.value.replace(/[^0-9]/g, '') })}
                />
                <Button variant="ghost" size="icon" onClick={() => removeLine(i)} aria-label={SW.mauzo.ondoaMalipo}>
                  <Trash2 size={16} />
                </Button>
              </div>
              {NEEDS_REFERENCE.includes(line.method) && (
                <Input
                  label={SW.mauzo.kumbukumbuNamba}
                  value={line.reference}
                  onChange={(e) => setLine(i, { reference: e.target.value })}
                  placeholder={SW.mauzo.kumbukumbuPlaceholder}
                  required
                />
              )}
              {deni > 0 && (
                <button type="button" className="text-xs text-primary-light hover:underline" onClick={() => payRemainder(i)}>
                  {SW.mauzo.lipaYote}
                </button>
              )}
            </div>
          ))}
          {lines.length < MAX_LINES && (
            <button type="button" className="text-xs text-primary-light hover:underline inline-flex items-center gap-1" onClick={addLine}>
              <Plus size={14} /> {SW.mauzo.ongezaMalipo}
            </button>
          )}
        </div>

        <div className="glass-card p-3 space-y-1 text-sm">
          <div className="flex justify-between text-text-secondary">
            <span>{SW.mauzo.kilicholipwa}</span><span>{formatCurrency(paid)}</span>
          </div>
          <div className={`flex justify-between font-medium ${deni > 0 ? 'text-accent-red' : 'text-text-primary'}`}>
            <span>{SW.mauzo.deni}</span><span>{formatCurrency(Math.max(0, deni))}</span>
          </div>
          {overpaid && <p className="text-xs text-accent-red">{SW.mauzo.malipoYanazidi}</p>}
        </div>

        <CustomerPicker value={customer} onChange={setCustomer} label={deni > 0 ? SW.mauzo.mteja : SW.mauzo.mtejaHiari} />
        {deni > 0 && !customer && <p className="text-xs text-accent-red">{SW.mauzo.mtejaAnahitajika}</p>}
        {overLimitHint && <p className="text-xs text-accent-yellow">{SW.mauzo.mkopoUnazidi}</p>}

        {/* Item summary */}
        <div>
          <p className="text-xs text-text-muted mb-2">{SW.mauzo.bidhaaIdadi(items.length)}</p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {items.map((i) => (
              <div key={i.product_id} className="flex justify-between text-sm">
                <span className="text-text-secondary truncate">{i.product_name} × {i.quantity}</span>
                <span className="text-text-primary ml-2 flex-shrink-0">{formatCurrency(i.selling_price * i.quantity)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  )
}
