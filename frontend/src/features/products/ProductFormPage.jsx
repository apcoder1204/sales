import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Save, X, Package } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { productService } from '@services/productService'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import { useToast } from '@hooks/useToast'
import SW from '@constants/sw'

const UNIT_OPTIONS = Object.entries(SW.bidhaa.vipimo).map(([value, label]) => ({ value, label }))
const STATUS_OPTIONS = [
  { value: 'active', label: SW.bidhaa.hai },
  { value: 'inactive', label: SW.bidhaa.imesimama },
  { value: 'discontinued', label: SW.bidhaa.imekomeshwa },
]

const empty = {
  product_code: '',
  name: '',
  category_id: '',
  family_name: '',
  unit: 'Kipande',
  cost_price: '',
  selling_price: '',
  minimum_stock: '5',
  description: '',
  status: 'active',
}

export default function ProductFormPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = Boolean(id)
  const [form, setForm] = useState(empty)
  const [categories, setCategories] = useState([])
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState('')
  const { loading, call } = useApi()
  const toast = useToast()

  useEffect(() => {
    productService.categories()
      .then((c) => setCategories(c.map((x) => ({ value: String(x.id), label: x.name }))))
      .catch(() => {})
    userService.branches()
      .then((b) => {
        setBranches(b.map((x) => ({ value: x.id, label: x.name })))
        if (b.length > 0) setSelectedBranch(b[0].id)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (isEdit) {
      productService.get(id).then((p) => {
        setForm({
          product_code: p.product_code || '',
          name: p.name || '',
          category_id: String(p.category_id || ''),
          family_name: p.family_name || '',
          unit: p.unit || 'Kipande',
          cost_price: String(p.cost_price || ''),
          selling_price: String(p.selling_price || ''),
          minimum_stock: String(p.minimum_stock ?? 5),
          description: p.description || '',
          status: p.status || 'active',
        })
      }).catch(() => {
        toast.error('Bidhaa haipatikani')
        navigate('/bidhaa')
      })
    }
  }, [id, isEdit])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSave = async () => {
    if (!form.name || !form.category_id || !form.selling_price) {
      toast.error('Tafadhali jaza sehemu zote zinazohitajika')
      return
    }
    const payload = {
      name: form.name,
      category_id: parseInt(form.category_id),
      family_name: form.family_name || undefined,
      unit: form.unit,
      description: form.description || undefined,
      cost_price: parseFloat(form.cost_price) || 0,
      selling_price: parseFloat(form.selling_price),
      minimum_stock: parseInt(form.minimum_stock) || 5,
      status: form.status,
    }
    if (form.product_code) payload.product_code = form.product_code
    if (!isEdit) {
      delete payload.status
    }
    await call(
      () => isEdit ? productService.update(id, payload) : productService.create(payload),
      {
        successMsg: SW.mafanikio.imehifadhiwa,
        onSuccess: () => navigate('/bidhaa'),
      }
    )
  }

  const title = isEdit ? SW.bidhaa.kuhariryaBidhaa : SW.bidhaa.kuongezaBidhaa
  const subtitle = isEdit ? 'Badilisha taarifa za bidhaa' : 'Ongeza bidhaa mpya kwenye mfumo'

  return (
    <PageWrapper
      title={title}
      subtitle={subtitle}
      action={
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => navigate('/bidhaa')} leftIcon={<X size={16} />}>
            {SW.common.ghairi}
          </Button>
          <Button loading={loading} onClick={handleSave} leftIcon={<Save size={16} />}>
            {SW.common.hifadhi}
          </Button>
        </div>
      }
    >
      <div className="max-w-3xl">
        <div className="glass-card p-6 space-y-6">
          {/* Row 1: Stoo + Jamii */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label={SW.bidhaa.stoo}
              value={selectedBranch}
              onChange={(e) => setSelectedBranch(e.target.value)}
              options={branches}
              placeholder="Chagua stoo"
            />
            <Select
              label={SW.bidhaa.jamii}
              value={form.category_id}
              onChange={set('category_id')}
              options={categories}
              placeholder="Chagua jamii ya bidhaa"
              required
            />
          </div>

          {/* Row 2: Jina + Kipimo */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={SW.bidhaa.jina}
              value={form.name}
              onChange={set('name')}
              placeholder="Ingiza jina la bidhaa"
              leftIcon={<Package size={16} />}
              required
            />
            <Select
              label={SW.bidhaa.kipimo}
              value={form.unit}
              onChange={set('unit')}
              options={UNIT_OPTIONS}
              placeholder="Chagua kipimo"
            />
          </div>

          {/* Row 3: Msimbo + Familia */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={SW.bidhaa.msimbo}
              value={form.product_code}
              onChange={set('product_code')}
              placeholder="Mfano: CCTV-001 (hiari, itatengenezwa kiotomatiki)"
            />
            <Input
              label={SW.bidhaa.familia}
              value={form.family_name}
              onChange={set('family_name')}
              placeholder="Mfano: Hikvision, Dahua, Reolink"
            />
          </div>

          {/* Row 4: Bei ya Ununuzi + Bei ya Mauzo */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={SW.bidhaa.beiGhali}
              type="number"
              value={form.cost_price}
              onChange={set('cost_price')}
              placeholder="Ingiza bei ya ununuzi"
              leftIcon={<span className="text-xs font-bold">TSh</span>}
            />
            <Input
              label={SW.bidhaa.beiUzaji}
              type="number"
              value={form.selling_price}
              onChange={set('selling_price')}
              placeholder="Ingiza bei ya mauzo"
              leftIcon={<span className="text-xs font-bold">TSh</span>}
              required
            />
          </div>

          {/* Row 5: Idadi ya Kuanzia + Tahadhari */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={SW.bidhaa.idadiKuanzia}
              type="number"
              value={isEdit ? '' : '0'}
              disabled={isEdit}
              placeholder="Ingiza idadi ya sasa"
              leftIcon={<span className="text-xs font-bold">#</span>}
            />
            <Input
              label={SW.bidhaa.tahadhari}
              type="number"
              value={form.minimum_stock}
              onChange={set('minimum_stock')}
              placeholder="Mfano: 5"
              leftIcon={<span className="text-xs font-bold">#</span>}
            />
          </div>

          {/* Row 6: Hali + Maelezo */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {isEdit && (
              <Select
                label={SW.bidhaa.hali}
                value={form.status}
                onChange={set('status')}
                options={STATUS_OPTIONS}
              />
            )}
            <div className={isEdit ? '' : 'sm:col-span-2'}>
              <Input
                label={SW.bidhaa.maelezo}
                value={form.description}
                onChange={set('description')}
                placeholder="Maelezo ya ziada (hiari)"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2 border-t border-border">
            <Button loading={loading} onClick={handleSave} leftIcon={<Save size={16} />}>
              {SW.common.hifadhi}
            </Button>
            <Button variant="secondary" onClick={() => navigate('/bidhaa')} leftIcon={<X size={16} />}>
              {SW.common.ghairi}
            </Button>
          </div>
        </div>
      </div>
    </PageWrapper>
  )
}
