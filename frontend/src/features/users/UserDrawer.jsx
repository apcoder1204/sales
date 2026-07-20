import React, { useState, useEffect } from 'react'
import Drawer from '@components/ui/Drawer'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import SW from '@constants/sw'

const GLOBAL_ROLE_NAMES = ['super_admin', 'admin', 'general_manager']

const empty = { full_name: '', username: '', email: '', password: '', confirm_password: '', role_id: '', branch_id: '' }

export default function UserDrawer({ open, onClose, user, onSaved }) {
  const [form, setForm] = useState(empty)
  const [branches, setBranches] = useState([])
  const [roles, setRoles] = useState([])
  const { loading, call } = useApi()

  useEffect(() => {
    userService.branches().then((b) => setBranches(b.map((x) => ({ value: x.id, label: x.name })))).catch(() => {})
    userService.roles().then(setRoles).catch(() => {})
  }, [])

  useEffect(() => {
    if (user) setForm({ ...user, password: '', confirm_password: '', branch_id: user.branch_id || '' })
    else setForm(empty)
  }, [user, open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const selectedRoleName = roles.find((r) => String(r.id) === String(form.role_id))?.name
  const needsBranch = selectedRoleName && !GLOBAL_ROLE_NAMES.includes(selectedRoleName)

  const handleSave = async () => {
    const payload = {
      full_name: form.full_name,
      username: form.username,
      email: form.email,
      role_id: parseInt(form.role_id, 10),
      branch_id: needsBranch ? form.branch_id : null,
    }
    if (!user) {
      payload.password = form.password
      payload.confirm_password = form.confirm_password
    }
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
          <>
            <Input label={SW.watumiaji.nenosiri} type="password" value={form.password} onChange={set('password')} required />
            <Input
              label="Thibitisha Nenosiri" type="password"
              value={form.confirm_password} onChange={set('confirm_password')}
              required
            />
          </>
        )}
        <Select
          label={SW.watumiaji.jukumu}
          value={form.role_id}
          onChange={set('role_id')}
          options={roles.map((r) => ({ value: r.id, label: SW.majukumu[r.name] || r.name }))}
          placeholder="Chagua jukumu..."
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
