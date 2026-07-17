import React, { useState, useEffect } from 'react'
import { Save, X, Package } from 'lucide-react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { productService } from '@services/productService'
import { inventoryService } from '@services/inventoryService'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import { useToast } from '@hooks/useToast'
import { useAuth } from '@hooks/useAuth'
import { isGlobalRole } from '@utils/permissions'
import SW from '@constants/sw'

const UNIT_OPTIONS = Object.entries(SW.bidhaa.vipimo).map(([value, label]) => ({ value, label }))
const STATUS_OPTIONS = [
  { value: 'active', label: SW.bidhaa.hai },
  { value: 'inactive', label: SW.bidhaa.imesimama },
  { value: 'discontinued', label: SW.bidhaa.imekomeshwa },
]

const empty = {
  product_code: '', name: '', category_id: '', family_name: '',
  unit: 'Kipande', cost_price: '', selling_price: '',
  minimum_stock: '5', description: '', status: 'active',
  initial_qty: '0',
}

export default function ProductFormModal({ open, onClose, onSaved, product }) {
  const isEdit = Boolean(product)
  const { user } = useAuth()
  const isGlobal = isGlobalRole(user)
  const [form, setForm] = useState(empty)
  const [categories, setCategories] = useState([])
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState('')
  const { loading, call } = useApi()
  const toast = useToast()

  useEffect(() => {
    if (!open) return
    productService.categories()
      .then((c) => setCategories(c.map((x) => ({
        value: String(x.id),
        label: x.name + (x.brand_name ? ` — ${x.brand_name}` : '') + (x.category_code ? ` [${x.category_code}]` : ''),
      }))))
      .catch(() => {})
    if (isGlobal) {
      // Initial product stock always goes to Main Store (POS outlets get stock via transfers)
      userService.branches()
        .then((b) => {
          const main = b.filter((x) => x.branch_type === 'main_store')
          setBranches(main.map((x) => ({ value: x.id, label: x.name })))
          if (main.length > 0) setSelectedBranch(main[0].id)
        })
        .catch(() => {})
    } else {
      setSelectedBranch(user?.branch_id || '')
    }
  }, [open])

  useEffect(() => {
    if (open && isEdit && product) {
      setForm({
        product_code: product.product_code || '',
        name: product.name || '',
        category_id: String(product.category_id || ''),
        family_name: product.family_name || '',
        unit: product.unit || 'Kipande',
        cost_price: String(product.cost_price || ''),
        selling_price: String(product.selling_price || ''),
        minimum_stock: String(product.minimum_stock ?? 5),
        description: product.description || '',
        status: product.status || 'active',
        initial_qty: '0',
      })
    } else if (open && !isEdit) {
      setForm(empty)
    }
  }, [open, product])

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
    }
    if (form.product_code) payload.product_code = form.product_code
    if (isEdit) payload.status = form.status

    await call(
      () => isEdit ? productService.update(product.id, payload) : productService.create(payload),
      {
        successMsg: SW.mafanikio.imehifadhiwa,
        onSuccess: async (newProduct) => {
          // After creating a new product, add initial stock if provided
          const qty = parseInt(form.initial_qty) || 0
          if (!isEdit && qty > 0 && selectedBranch && newProduct?.id) {
            try {
              await inventoryService.adjust({
                product_id: newProduct.id,
                branch_id: selectedBranch,
                type: 'stock_in',
                quantity: qty,
                notes: 'Idadi ya awali',
              })
            } catch {
              toast.error('Bidhaa imehifadhiwa lakini idadi haikuongezwa — ongeza kwa Marekebisho ya Bidhaa')
            }
          }
          onSaved()
          onClose()
        },
      }
    )
  }

  const handleClose = () => { setForm(empty); onClose() }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={isEdit ? SW.bidhaa.kuhariryaBidhaa : SW.bidhaa.kuongezaBidhaa}
      size="xl"
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} leftIcon={<X size={15} />}>
            {SW.common.ghairi}
          </Button>
          <Button loading={loading} onClick={handleSave} leftIcon={<Save size={15} />}>
            {SW.common.hifadhi}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {isGlobal ? (
            <Select
              label="Hifadhi Kuu (Idadi ya Awali)"
              value={selectedBranch}
              onChange={(e) => setSelectedBranch(e.target.value)}
              options={branches}
              placeholder="Hifadhi Kuu"
            />
          ) : null}
          <Select
            label={SW.bidhaa.jamii}
            value={form.category_id}
            onChange={set('category_id')}
            options={categories}
            placeholder="Chagua jamii ya bidhaa"
            required
            className={isGlobal ? '' : 'sm:col-span-2'}
          />
        </div>

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
          />
        </div>

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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label={SW.bidhaa.beiGhali}
            type="number"
            min="0"
            value={form.cost_price}
            onChange={set('cost_price')}
            placeholder="Ingiza bei ya ununuzi"
            leftIcon={<span className="text-xs font-bold">TSh</span>}
          />
          <Input
            label={SW.bidhaa.beiUzaji}
            type="number"
            min="0"
            value={form.selling_price}
            onChange={set('selling_price')}
            placeholder="Ingiza bei ya mauzo"
            leftIcon={<span className="text-xs font-bold">TSh</span>}
            required
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Input
              label={isEdit ? SW.bidhaa.idadiKuanzia : `${SW.bidhaa.idadiKuanzia} (idadi unayoiingiza sasa)`}
              type="number"
              min="0"
              value={isEdit ? '' : form.initial_qty}
              onChange={isEdit ? undefined : set('initial_qty')}
              disabled={isEdit}
              placeholder={isEdit ? 'Tumia Marekebisho ya Bidhaa' : '0'}
              leftIcon={<span className="text-xs font-bold">#</span>}
            />
            {!isEdit && parseInt(form.initial_qty) > 0 && (
              <p className="text-xs text-accent-green mt-1">
                Itaongeza {form.initial_qty} {isGlobal ? `kwenye tawi uliochagua` : 'kwenye tawi lako'}
              </p>
            )}
          </div>
          <Input
            label={`${SW.bidhaa.tahadhari} (kiwango cha chini cha tahadhari)`}
            type="number"
            min="0"
            value={form.minimum_stock}
            onChange={set('minimum_stock')}
            placeholder="Mfano: 5"
            leftIcon={<span className="text-xs font-bold">#</span>}
          />
        </div>

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
      </div>
    </Modal>
  )
}
