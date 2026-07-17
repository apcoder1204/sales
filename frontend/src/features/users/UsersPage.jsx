import React, { useState, useEffect, useCallback } from 'react'
import { Plus } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Avatar from '@components/ui/Avatar'
import UserDrawer from './UserDrawer'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import { usePagination } from '@hooks/usePagination'
import { formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const { call } = useApi()
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await userService.list(pagination.params)
      setUsers(res.items || res)
      if (res.total !== undefined) pagination.setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [pagination.page])

  useEffect(() => { load() }, [load])

  const handleUnlock = (userId) => {
    call(() => userService.unlock(userId), { successMsg: SW.mafanikio.imewashwa, onSuccess: load })
  }

  const columns = [
    {
      key: 'full_name', header: 'Mtumiaji',
      render: (v, row) => (
        <div className="flex items-center gap-3">
          <Avatar name={v} size="sm" />
          <div>
            <p className="font-medium text-text-primary">{v}</p>
            <p className="text-xs text-text-muted">{row.username}</p>
          </div>
        </div>
      ),
    },
    { key: 'email', header: 'Barua Pepe', render: (v) => <span className="text-text-secondary text-sm">{v}</span> },
    {
      key: 'role', header: 'Jukumu',
      render: (v) => {
        const colors = { super_admin: 'red', admin: 'yellow', general_manager: 'purple', store_keeper: 'blue', cashier: 'green' }
        return <Badge color={colors[v] || 'gray'}>{SW.majukumu[v] || v}</Badge>
      },
    },
    { key: 'branch_name', header: 'Tawi', render: (v) => <span className="text-text-secondary text-sm">{v || '—'}</span> },
    {
      key: 'is_active', header: 'Hali',
      render: (v, row) => row.locked_until ? (
        <Badge color="red">Imefungwa</Badge>
      ) : (
        <Badge color={v ? 'green' : 'red'}>{v ? 'Hai' : 'Imezimwa'}</Badge>
      ),
    },
    { key: 'created_at', header: 'Ameundwa', render: (v) => formatDateTime(v) },
    {
      key: '_actions', header: '',
      render: (_, row) => (
        <div className="flex gap-1">
          {row.locked_until && (
            <Button variant="success" size="sm" onClick={() => handleUnlock(row.id)}>
              Fungua
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => { setEditing(row); setDrawerOpen(true) }}>
            Hariri
          </Button>
        </div>
      ),
    },
  ]

  return (
    <PageWrapper
      title={SW.nav.watumiaji}
      subtitle="Simamia watumiaji wa mfumo"
      action={
        <Button onClick={() => { setEditing(null); setDrawerOpen(true) }} leftIcon={<Plus size={16} />}>
          {SW.watumiaji.ongeza}
        </Button>
      }
    >
      <DataTable
        columns={columns}
        data={users}
        loading={loading}
        pagination={pagination}
        emptyTitle="Hakuna watumiaji waliopo"
      />

      <UserDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        user={editing}
        onSaved={() => { setDrawerOpen(false); load() }}
      />
    </PageWrapper>
  )
}
