import React, { useState, useEffect } from 'react'
import Drawer from '@components/ui/Drawer'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { branchService } from '@services/branchService'
import { useApi } from '@hooks/useApi'
import SW from '@constants/sw'

const empty = { name: '', code: '', branch_type: 'pos_point', address: '', phone: '' }

export default function BranchDrawer({ open, onClose, branch, onSaved }) {
  const [form, setForm] = useState(empty)
  const { loading, call } = useApi()

  useEffect(() => {
    if (branch) {
      setForm({
        name: branch.name,
        code: branch.code,
        branch_type: branch.branch_type,
        address: branch.address || '',
        phone: branch.phone || '',
      })
    } else {
      setForm(empty)
    }
  }, [branch, open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSave = async () => {
    const payload = {
      name: form.name,
      code: form.code,
      branch_type: form.branch_type,
      address: form.address || null,
      phone: form.phone || null,
    }
    await call(
      () => branch ? branchService.update(branch.id, payload) : branchService.create(payload),
      { successMsg: SW.mafanikio.imehifadhiwa, onSuccess: onSaved }
    )
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={branch ? SW.matawiUsimamizi.hariri : SW.matawiUsimamizi.ongeza}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={loading} onClick={handleSave}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input
          label={SW.matawiUsimamizi.jina} value={form.name} onChange={set('name')}
          placeholder={SW.matawiUsimamizi.jinaPlaceholder} required
        />
        <Input
          label={SW.matawiUsimamizi.msimbo} value={form.code} onChange={set('code')}
          placeholder={SW.matawiUsimamizi.msimboPlaceholder} required
        />
        <Select
          label={SW.matawiUsimamizi.aina}
          value={form.branch_type}
          onChange={set('branch_type')}
          options={[
            { value: 'pos_point', label: SW.matawiUsimamizi.ainaSehemuYaMauzo },
            { value: 'main_store', label: SW.matawiUsimamizi.ainaGhalaKuu },
          ]}
          required
        />
        <Input label={SW.matawiUsimamizi.anwani} value={form.address} onChange={set('address')} />
        <Input label={SW.matawiUsimamizi.simu} value={form.phone} onChange={set('phone')} />
      </div>
    </Drawer>
  )
}
