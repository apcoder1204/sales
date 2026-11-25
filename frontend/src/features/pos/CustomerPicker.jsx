import React, { useEffect, useRef, useState } from 'react'
import { Search, UserPlus, X } from 'lucide-react'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import Button from '@components/ui/Button'
import Badge from '@components/ui/Badge'
import { customerService } from '@services/customerService'
import { resolveApiErrorMessage } from '@utils/apiError'
import { formatCurrency } from '@utils/formatters'
import SW from '@constants/sw'

const CUSTOMER_TYPES = ['individual', 'business', 'institution', 'government']

// Search-or-create customer selector. `value` is the selected customer
// (with `summary` from GET /customers/{id}: scoped balance + all-branch
// available credit) or null; `onChange` receives the same shape.
export default function CustomerPicker({ value, onChange, allowCreate = true, label }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ name: '', phone: '', customer_type: 'individual' })
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)
  const seq = useRef(0)

  useEffect(() => {
    if (value || query.trim().length < 2) {
      setResults([])
      return undefined
    }
    const mine = ++seq.current
    const t = setTimeout(async () => {
      setSearching(true)
      try {
        const data = await customerService.search(query.trim(), { per_page: 8 })
        if (mine === seq.current) setResults(data.items || [])
      } catch {
        if (mine === seq.current) setResults([])
      } finally {
        if (mine === seq.current) setSearching(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [query, value])

  const select = async (customer) => {
    setQuery('')
    setResults([])
    setCreating(false)
    try {
      const detail = await customerService.get(customer.id)
      onChange({ ...detail.customer, summary: detail.summary })
    } catch {
      onChange({ ...customer, summary: null })
    }
  }

  const create = async () => {
    setSaving(true)
    setFormError(null)
    try {
      const created = await customerService.create(form)
      setForm({ name: '', phone: '', customer_type: 'individual' })
      await select(created)
    } catch (err) {
      setFormError(resolveApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (value) {
    const available = value.summary?.available_credit
    return (
      <div className="glass-card p-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-text-muted">{label || SW.mauzo.mteja}</p>
          <p className="font-medium text-text-primary truncate">
            {value.name}{' '}
            {value.status === 'inactive' && <Badge color="red">{SW.hali.mteja.inactive}</Badge>}
          </p>
          <p className="text-xs text-text-secondary">{value.phone} · {value.customer_no}</p>
          {available !== undefined && available !== null && (
            <p className="text-xs text-text-secondary mt-1">
              {SW.mauzo.mkopoUnaopatikana}: <span className="font-medium text-text-primary">{formatCurrency(available)}</span>
            </p>
          )}
        </div>
        <button
          type="button"
          className="text-text-muted hover:text-text-primary"
          onClick={() => onChange(null)}
          aria-label={SW.mauzo.ondoaMalipo}
        >
          <X size={16} />
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <Input
        label={label || SW.mauzo.mtejaHiari}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={SW.wateja.tafutaFupi}
        leftIcon={<Search size={14} />}
      />
      {query.trim().length >= 2 && (
        <div className="glass-card max-h-40 overflow-y-auto divide-y divide-border">
          {searching && <p className="p-2 text-xs text-text-muted">…</p>}
          {!searching && results.length === 0 && (
            <p className="p-2 text-xs text-text-muted">{SW.wateja.hakunaMatokeo}</p>
          )}
          {results.map((c) => (
            <button
              key={c.id}
              type="button"
              className="w-full text-left p-2 hover:bg-bg-hover"
              onClick={() => select(c)}
            >
              <p className="text-sm text-text-primary">{c.name}</p>
              <p className="text-xs text-text-muted">{c.phone} · {c.customer_no}</p>
            </button>
          ))}
        </div>
      )}
      {allowCreate && !creating && (
        <button
          type="button"
          className="text-xs text-accent-blue inline-flex items-center gap-1"
          onClick={() => setCreating(true)}
        >
          <UserPlus size={14} /> {SW.wateja.mtejaMpya}
        </button>
      )}
      {allowCreate && creating && (
        <div className="glass-card p-3 space-y-2">
          <Input
            label={SW.wateja.jina}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            label={SW.wateja.simu}
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="07XX XXX XXX"
            required
          />
          <Select
            label={SW.wateja.aina}
            value={form.customer_type}
            onChange={(e) => setForm({ ...form, customer_type: e.target.value })}
            options={CUSTOMER_TYPES.map((t) => ({ value: t, label: SW.hali.ainaMteja[t] }))}
          />
          {formError && <p className="text-xs text-accent-red">{formError}</p>}
          <div className="flex gap-2 justify-end">
            <Button size="sm" variant="secondary" onClick={() => setCreating(false)}>{SW.common.ghairi}</Button>
            <Button
              size="sm"
              loading={saving}
              disabled={form.name.trim().length < 2 || form.phone.trim().length < 9}
              onClick={create}
            >
              {SW.wateja.ongezaMteja}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
