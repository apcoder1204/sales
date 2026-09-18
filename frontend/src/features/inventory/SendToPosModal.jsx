import React, { useState, useEffect } from 'react'
import { ArrowRight } from 'lucide-react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import { transferService } from '@services/transferService'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import { formatNumber } from '@utils/formatters'
import SW from '@constants/sw'

export default function SendToPosModal({ open, onClose, item, onSaved }) {
  const { loading, call } = useApi()
  const [posBranches, setPosBranches] = useState([])
  const [form, setForm] = useState({ to_branch_id: '', quantity: '', notes: '' })

  useEffect(() => {
    if (!open) return
    setForm({ to_branch_id: '', quantity: '', notes: '' })
    userService.branches()
      .then((b) => {
        const pos = b.filter((x) => x.branch_type === 'pos_point')
        setPosBranches(pos.map((x) => ({ value: x.id, label: x.name })))
        if (pos.length > 0) setForm((f) => ({ ...f, to_branch_id: pos[0].id }))
      })
      .catch(() => {})
  }, [open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const qty = parseInt(form.quantity) || 0
  const maxQty = item?.available_qty ?? 0
  const overLimit = qty > maxQty

  const handleSend = async () => {
    if (!form.to_branch_id || qty <= 0 || overLimit) return
    await call(
      () => transferService.createDirect({
        from_branch_id: item.branch_id,
        to_branch_id: form.to_branch_id,
        notes: form.notes || undefined,
        items: [{ product_id: item.product_id, quantity: qty }],
      }),
      {
        successMsg: SW.mafanikio.imesafirishwa,
        onSuccess: () => { onSaved?.(); onClose() },
      }
    )
  }

  if (!item) return null

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={SW.hifadhi.tumaBidhaaKwaKioski}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button
            loading={loading}
            onClick={handleSend}
            disabled={!form.to_branch_id || qty <= 0 || overLimit}
            leftIcon={<ArrowRight size={15} />}
          >
            {SW.hifadhi.tumaBidhaaBtn}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {/* Product info card */}
        <div className="glass-card p-3 space-y-2">
          <div>
            <p className="text-sm font-semibold text-text-primary">{item.product_name}</p>
            <p className="text-xs text-text-muted">{item.product_code}</p>
          </div>
          <div className="flex gap-6">
            <div>
              <p className="text-xs text-text-muted">{SW.uhamisho.chanzo}</p>
              <p className="text-sm font-medium text-text-primary">{item.branch_name}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">{SW.hifadhi.inayopatikana}</p>
              <p className="text-sm font-bold text-accent-green">{formatNumber(maxQty)}</p>
            </div>
          </div>
        </div>

        <Select
          label={SW.hifadhi.tumaKwenda}
          value={form.to_branch_id}
          onChange={set('to_branch_id')}
          options={posBranches}
          placeholder={SW.hifadhi.chaguaKioskiPlaceholder}
          required
        />

        <div>
          <Input
            label={SW.hifadhi.idadiYaKutuma}
            type="number"
            min="1"
            max={maxQty}
            value={form.quantity}
            onChange={set('quantity')}
            placeholder={`1 – ${formatNumber(maxQty)}`}
            required
          />
          {overLimit && (
            <p className="text-xs text-accent-red mt-1">
              {SW.hifadhi.inazidiBidhaa(formatNumber(maxQty))}
            </p>
          )}
          {qty > 0 && !overLimit && (
            <p className="text-xs text-accent-green mt-1">
              {SW.hifadhi.dukaKuuItabakiNa(formatNumber(maxQty - qty))}
            </p>
          )}
        </div>

        <Input
          label={SW.ufungaji.maelezo}
          value={form.notes}
          onChange={set('notes')}
          placeholder={SW.hifadhi.sababuYaUhamishoPlaceholder}
        />
      </div>
    </Modal>
  )
}
