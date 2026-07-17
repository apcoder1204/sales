import React, { useState, useEffect } from 'react'
import Drawer from '@components/ui/Drawer'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import SW from '@constants/sw'

const ROLE_OPTIONS = [
  { value: 'super_admin', label: SW.majukumu.super_admin },
  { value: 'admin', label: SW.majukumu.admin },
  { value: 'general_manager', label: SW.majukumu.general_manager },
  { value: 'store_keeper', label: SW.majukumu.store_keeper },
  { value: 'cashier', label: SW.majukumu.cashier },
]

const empty = { full_name: '', username: '', email: '', password: '', role: 'cashier', branch_id: '' }

export default function UserDrawer({ open, onClose, user, onSaved }) {
  const [form, setForm] = useState(empty)
  const [branches, setBranches] = useState([])
  const { loading, call } = useApi()

  useEffect(() => {
    userService.branches().then((b) => setBranches(b.map((x) => ({ value: x.id, label: x.name })))).catch(() => {})
  }, [])

  useEffect(() => {
    if (user) setForm({ ...user, password: '', branch_id: user.branch_id || '' })
    else setForm(empty)
  }, [user, open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const globalRoles = ['super_admin', 'admin', 'general_manager']
  const needsBranch = !globalRoles.includes(form.role)

  const handleSave = async () => {
    const payload = { ...form, branch_id: needsBranch ? form.branch_id : null }
    if (!user) payload.password = form.password
    await call(
      () => user ? userService.update(user.id, payload) : userService.create(payload),
      { successMsg: SW.mafanikio.imehifadhiwa, onSuccess: onSaved }
    )
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={user ? SW.watumiaji.hariri : SW.watumiaji.ongeza}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={loading} onClick={handleSave}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input label={SW.watumiaji.jina} value={form.full_name} onChange={set('full_name')} required />
        <Input label={SW.watumiaji.jinalaMtumiaji} value={form.username} onChange={set('username')} required />
        <Input label={SW.watumiaji.barua} type="email" value={form.email} onChange={set('email')} required />
        {!user && (
          <Input label={SW.watumiaji.nenosiri} type="password" value={form.password} onChange={set('password')} required />
        )}
        <Select
          label={SW.watumiaji.jukumu}
          value={form.role}
          onChange={set('role')}
          options={ROLE_OPTIONS}
          required
        />
        {needsBranch && (
          <Select
            label={SW.watumiaji.tawi}
            value={form.branch_id}
            onChange={set('branch_id')}
            options={branches}
            placeholder="Chagua tawi..."
            required
          />
        )}
      </div>
    </Drawer>
  )
}
