import React, { useState } from 'react'
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

export default function CheckoutModal({ open, onClose, onComplete }) {
  const { items, subtotal, total, clear } = useCart()
  const { user } = useAuth()
  const { loading, call } = useApi()
  const { activeBranchId, branches } = useBranch()
  const [payment, setPayment] = useState({ method: 'cash', reference: '' })

  const isGlobal = isGlobalRole(user)
  const needsReference = ['mobile_money', 'bank_transfer'].includes(payment.method)

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
    if (needsReference && !payment.reference.trim()) return
    if (!effectiveBranchId) return

    const payload = {
      branch_id: effectiveBranchId,
      payment_method: payment.method,
      payment_reference: payment.reference || undefined,
      items: items.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
    }

    const receipt = await call(() => saleService.create(payload), {
      successMsg: SW.mauzo.mauzoYamefanikiwa,
    })

    if (receipt) {
      clear()
      onComplete(receipt)
    }
  }

  const canSubmit = items.length > 0
    && !(needsReference && !payment.reference)
    && Boolean(effectiveBranchId)
    && globalBranchReady

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={SW.mauzo.thibitisha}
      size="sm"
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

        <Select
          label={SW.mauzo.njiaYaLipa}
          value={payment.method}
          onChange={(e) => setPayment({ ...payment, method: e.target.value })}
          options={getPaymentMethods()}
        />

        {needsReference && (
          <Input
            label={SW.mauzo.kumbukumbuNamba}
            value={payment.reference}
            onChange={(e) => setPayment({ ...payment, reference: e.target.value })}
            placeholder={SW.mauzo.kumbukumbuPlaceholder}
            required
          />
        )}

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
