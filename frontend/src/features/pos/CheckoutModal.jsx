import React, { useState, useEffect } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import Divider from '@components/ui/Divider'
import { useCart } from '@hooks/useCart'
import { useAuth } from '@hooks/useAuth'
import { useApi } from '@hooks/useApi'
import { saleService } from '@services/saleService'
import { userService } from '@services/userService'
import { formatCurrency } from '@utils/formatters'
import { PAYMENT_METHODS } from '@utils/constants'
import { isGlobalRole } from '@utils/permissions'
import SW from '@constants/sw'

export default function CheckoutModal({ open, onClose, onComplete }) {
  const { items, subtotal, total, clear } = useCart()
  const { user } = useAuth()
  const { loading, call } = useApi()
  const [payment, setPayment] = useState({ method: 'cash', reference: '' })
  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState('')

  const isGlobal = isGlobalRole(user)
  const needsReference = ['mobile_money', 'bank_transfer'].includes(payment.method)

  // Load POS branches for global-role users (Main Store is a warehouse, not a POS sales point)
  useEffect(() => {
    if (!open || !isGlobal) return
    userService.branches()
      .then((b) => {
        const pos = b.filter((x) => x.branch_type === 'pos_point')
        setBranches(pos.map((x) => ({ value: x.id, label: x.name })))
        if (pos.length > 0) setSelectedBranchId(pos[0].id)
      })
      .catch(() => {})
  }, [open, isGlobal])

  const effectiveBranchId = isGlobal ? selectedBranchId : user?.branch_id

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
        {/* Branch selector — only for global roles */}
        {isGlobal && (
          <Select
            label="Tawi la Mauzo"
            value={selectedBranchId}
            onChange={(e) => setSelectedBranchId(e.target.value)}
            options={branches}
            placeholder="Chagua tawi..."
            required
          />
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
          options={PAYMENT_METHODS}
        />

        {needsReference && (
          <Input
            label={SW.mauzo.kumbukumbuNamba}
            value={payment.reference}
            onChange={(e) => setPayment({ ...payment, reference: e.target.value })}
            placeholder="M-Pesa au namba ya benki..."
            required
          />
        )}

        {/* Item summary */}
        <div>
          <p className="text-xs text-text-muted mb-2">Bidhaa ({items.length})</p>
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
