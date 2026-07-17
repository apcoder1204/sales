import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Pencil, Trash2, FolderOpen, Save, X } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import DataTable from '@components/tables/DataTable'
import Modal from '@components/ui/Modal'
import { productService } from '@services/productService'
import { usePermission } from '@hooks/usePermission'
import { useApi } from '@hooks/useApi'
import { useToast } from '@hooks/useToast'
import SW from '@constants/sw'

const empty = { name: '', name_sw: '', category_code: '', brand_name: '', family: '', description: '' }

export default function CategoryPage() {
  const { can } = usePermission()
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(empty)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const { loading: saving, call } = useApi()
  const { loading: deleting, call: callDelete } = useApi()
  const toast = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await productService.categories()
      setCategories(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openNew = () => { setEditing(null); setForm(empty); setModalOpen(true) }
  const openEdit = (cat) => {
    setEditing(cat)
    setForm({
      name: cat.name || '',
      name_sw: cat.name_sw || '',
      category_code: cat.category_code || '',
      brand_name: cat.brand_name || '',
      family: cat.family || '',
      description: cat.description || '',
    })
    setModalOpen(true)
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSave = async () => {
    if (!form.name) { toast.error('Jina la jamii linahitajika'); return }
    const payload = {
      name: form.name,
      name_sw: form.name_sw || undefined,
      category_code: form.category_code || undefined,
      brand_name: form.brand_name || undefined,
      family: form.family || undefined,
      description: form.description || undefined,
    }
    await call(
      () => editing
        ? productService.updateCategory(editing.id, payload)
        : productService.createCategory(payload),
      {
        successMsg: SW.mafanikio.imehifadhiwa,
        onSuccess: () => { setModalOpen(false); load() },
      }
    )
  }

  const handleDelete = async () => {
    await callDelete(
      () => productService.deleteCategory(deleteTarget.id),
      {
        successMsg: SW.mafanikio.imefutwa,
        onSuccess: () => { setDeleteTarget(null); load() },
      }
    )
  }

  const columns = [
    {
      key: 'category_code', header: 'ID / Msimbo', width: 110,
      render: (v) => <span className="font-mono text-xs text-text-muted">{v || '—'}</span>,
    },
    {
      key: 'name', header: 'Jina la Jamii',
      render: (v, row) => (
        <div>
          <p className="font-medium text-text-primary">{v}</p>
          {row.name_sw && <p className="text-xs text-text-muted">{row.name_sw}</p>}
        </div>
      ),
    },
    {
      key: 'brand_name', header: 'Brand',
      render: (v) => <span className="text-text-secondary text-sm">{v || '—'}</span>,
    },
    {
      key: 'family', header: 'Familia',
      render: (v) => <span className="text-text-secondary text-sm">{v || '—'}</span>,
    },
    {
      key: 'description', header: 'Maelezo',
      render: (v) => <span className="text-text-muted text-xs truncate max-w-[200px] block">{v || '—'}</span>,
    },
    can('products.write') && {
      key: '_actions', header: '',
      render: (_, row) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); openEdit(row) }}>
            <Pencil size={14} />
          </Button>
          <Button variant="ghost" size="icon" className="text-accent-red hover:bg-accent-red-muted"
            onClick={(e) => { e.stopPropagation(); setDeleteTarget(row) }}>
            <Trash2 size={14} />
          </Button>
        </div>
      ),
    },
  ].filter(Boolean)

  return (
    <PageWrapper
      title={SW.nav.jamiiYaBidhaa}
      subtitle="Simamia jamii za bidhaa"
      action={
        can('products.write') && (
          <Button onClick={openNew} leftIcon={<Plus size={16} />}>
            {SW.bidhaa.kuongezaJamii}
          </Button>
        )
      }
    >
      <DataTable
        columns={columns}
        data={categories}
        loading={loading}
        emptyTitle="Hakuna jamii zilizopatikana"
        emptyIcon={FolderOpen}
      />

      {/* Add / Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? SW.bidhaa.kuharirJamii : SW.bidhaa.kuongezaJamii}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)} leftIcon={<X size={15} />}>
              {SW.common.ghairi}
            </Button>
            <Button loading={saving} onClick={handleSave} leftIcon={<Save size={15} />}>
              {SW.common.hifadhi}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {/* Row 1: Msimbo + Brand */}
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={SW.bidhaa.msimboJamii}
              value={form.category_code}
              onChange={set('category_code')}
              placeholder="Mfano: CCTV-CAM"
            />
            <Input
              label="Brand / Mtengenezaji"
              value={form.brand_name}
              onChange={set('brand_name')}
              placeholder="Mfano: Hikvision, Dahua"
            />
          </div>
          {/* Row 2: Jina (required) */}
          <Input
            label={SW.bidhaa.jinaJamii}
            value={form.name}
            onChange={set('name')}
            placeholder="Ingiza jina la jamii (Mfano: Cameras)"
            required
          />
          {/* Row 3: Jina Kiswahili + Familia */}
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Jina kwa Kiswahili"
              value={form.name_sw}
              onChange={set('name_sw')}
              placeholder="Jina kwa Kiswahili (hiari)"
            />
            <Input
              label={SW.bidhaa.familiaJamii}
              value={form.family}
              onChange={set('family')}
              placeholder="Mfano: Vifaa vya Usalama"
            />
          </div>
          {/* Maelezo */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              {SW.bidhaa.maelezo}
            </label>
            <textarea
              value={form.description}
              onChange={set('description')}
              rows={3}
              placeholder="Ingiza maelezo ya jamii hii"
              className="w-full rounded-lg bg-bg-panel border border-border text-text-primary placeholder-text-muted px-3 py-2.5 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
            />
          </div>
        </div>
      </Modal>

      {/* Delete Confirm Modal */}
      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Futa Jamii"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>{SW.common.ghairi}</Button>
            <Button variant="danger" loading={deleting} onClick={handleDelete} leftIcon={<Trash2 size={15} />}>
              {SW.common.futa}
            </Button>
          </>
        }
      >
        <div className="space-y-2">
          <p className="text-sm font-medium text-text-primary">
            Je, una uhakika wa kufuta jamii &quot;{deleteTarget?.name}&quot;?
          </p>
          <p className="text-sm text-text-secondary">
            Jamii hii itafutwa kabisa. Bidhaa zinazotumia jamii hii hazitaweza kufutwa — unahitaji kuhamisha bidhaa kwanza.
          </p>
        </div>
      </Modal>
    </PageWrapper>
  )
}
