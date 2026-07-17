import React, { useState, useEffect } from 'react'
import Drawer from '@components/ui/Drawer'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { productService } from '@services/productService'
import { useApi } from '@hooks/useApi'
import { useToast } from '@hooks/useToast'
import SW from '@constants/sw'

const empty = { name: '', product_code: '', category_id: '', cost_price: '', selling_price: '', description: '', status: 'active' }

export default function ProductDrawer({ open, onClose, product, onSaved }) {
  const [form, setForm] = useState(empty)
  const [categories, setCategories] = useState([])
  const { loading, call } = useApi()
  const toast = useToast()

  useEffect(() => {
    productService.categories().then((c) => setCategories(c.map((x) => ({ value: x.id, label: x.name })))).catch(() => {})
  }, [])

  useEffect(() => {
    if (product) setForm({ ...product, category_id: product.category_id || '' })
    else setForm(empty)
  }, [product, open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSave = async () => {
    const payload = {
      ...form,
      cost_price: parseFloat(form.cost_price),
      selling_price: parseFloat(form.selling_price),
    }
    if (payload.selling_price < payload.cost_price) {
      toast.error(SW.bidhaa.beiSio); return
    }
    await call(
      () => product ? productService.update(product.id, payload) : productService.create(payload),
      { successMsg: SW.mafanikio.imehifadhiwa, onSuccess: onSaved }
    )
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={product ? SW.bidhaa.kuhariryaBidhaa : SW.bidhaa.kuongezaBidhaa}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={loading} onClick={handleSave}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input label={SW.bidhaa.jina} value={form.name} onChange={set('name')} required />
        <Input label={SW.bidhaa.msimbo} value={form.product_code} onChange={set('product_code')} required />
        <Select
          label={SW.bidhaa.kitengo}
          value={form.category_id}
          onChange={set('category_id')}
          options={categories}
          placeholder="Chagua kitengo..."
          required
        />
        <div className="grid grid-cols-2 gap-3">
          <Input label={SW.bidhaa.beiGhali} type="number" value={form.cost_price} onChange={set('cost_price')} required />
          <Input label={SW.bidhaa.beiUzaji} type="number" value={form.selling_price} onChange={set('selling_price')} required />
        </div>
        <Select
          label={SW.bidhaa.hali}
          value={form.status}
          onChange={set('status')}
          options={[
            { value: 'active', label: SW.bidhaa.hai },
            { value: 'inactive', label: SW.bidhaa.imesimama },
          ]}
        />
        <Input
          label={SW.bidhaa.maelezo}
          value={form.description || ''}
          onChange={set('description')}
          containerClassName=""
        />
      </div>
    </Drawer>
  )
}
