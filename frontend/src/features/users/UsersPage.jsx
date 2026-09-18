import React, { useState, useEffect, useCallback } from 'react'
import { Plus, UserX, UserCheck, Trash2 } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Avatar from '@components/ui/Avatar'
import Modal from '@components/ui/Modal'
import UserDrawer from './UserDrawer'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import { usePagination } from '@hooks/usePagination'
import { usePermission } from '@hooks/usePermission'
import { useAuth } from '@hooks/useAuth'
import { formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deactivateTarget, setDeactivateTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const { call } = useApi()
  const { loading: deactivating, call: callDeactivate } = useApi()
  const { loading: activating, call: callActivate } = useApi()
  const { loading: deleting, call: callDelete } = useApi()
  const pagination = usePagination()
  const { can, role } = usePermission()
  const { user: currentUser } = useAuth()

  // Backend already excludes super_admin/admin rows from admin's view — this
  // is defense in depth, not the real enforcement, in case a stale/cached
  // response ever included one.
  const visibleUsers = role === 'super_admin' ? users : users.filter((u) => u.role !== 'super_admin')

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

  const handleActivate = (userId) => {
    callActivate(() => userService.activate(userId), { successMsg: SW.mafanikio.imewashwa, onSuccess: load })
  }

  const handleDeactivate = async () => {
    await callDeactivate(
      () => userService.deactivate(deactivateTarget.id),
      {
        successMsg: SW.mafanikio.imezimwa,
        onSuccess: () => { setDeactivateTarget(null); load() },
      }
    )
  }

  const handlePermanentDelete = async () => {
    await callDelete(
      () => userService.permanentlyDelete(deleteTarget.id),
      {
        successMsg: SW.mafanikio.imefutwa,
        onSuccess: () => { setDeleteTarget(null); load() },
      }
    )
  }

  const columns = [
    {
      key: 'full_name', header: SW.watumiaji.kichwaMtumiaji,
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
    { key: 'email', header: SW.watumiaji.barua, render: (v) => <span className="text-text-secondary text-sm">{v}</span> },
    {
      key: 'role', header: SW.watumiaji.jukumu,
      render: (v) => {
        const colors = { super_admin: 'red', admin: 'yellow', general_manager: 'purple', store_keeper: 'blue', cashier: 'green' }
        return <Badge color={colors[v] || 'gray'}>{SW.majukumu[v] || v}</Badge>
      },
    },
    { key: 'branch_name', header: SW.watumiaji.tawi, render: (v) => <span className="text-text-secondary text-sm">{v || '—'}</span> },
    {
      key: 'is_active', header: SW.watumiaji.hali,
      render: (v, row) => row.locked_until ? (
        <Badge color="red">{SW.watumiaji.imefungwa}</Badge>
      ) : (
        <Badge color={v ? 'green' : 'red'}>{v ? SW.watumiaji.hai : SW.watumiaji.hafanyiKazi}</Badge>
      ),
    },
    { key: 'created_at', header: SW.watumiaji.ameundwa, render: (v) => formatDateTime(v) },
    {
      key: '_actions', header: '',
      render: (_, row) => (
        <div className="flex gap-1">
          {can('users.write') && row.locked_until && (
            <Button variant="success" size="sm" onClick={() => handleUnlock(row.id)}>
              {SW.watumiaji.funguaKitendo}
            </Button>
          )}
          {can('users.write') && (
            <Button variant="ghost" size="sm" onClick={() => { setEditing(row); setDrawerOpen(true) }}>
              {SW.watumiaji.haririKitendo}
            </Button>
          )}
          {can('users.write') && row.is_active && row.id !== currentUser?.id && (
            <Button
              variant="danger" size="sm"
              leftIcon={<UserX size={14} />}
              onClick={() => setDeactivateTarget(row)}
            >
              {SW.watumiaji.zimaKitendo}
            </Button>
          )}
          {can('users.write') && !row.is_active && row.id !== currentUser?.id && (
            <Button
              variant="success" size="sm"
              leftIcon={<UserCheck size={14} />}
              loading={activating}
              onClick={() => handleActivate(row.id)}
            >
              {SW.watumiaji.washaKitendo}
            </Button>
          )}
          {can('users.write') && !row.is_active && row.id !== currentUser?.id && (
            <Button
              variant="danger" size="sm"
              leftIcon={<Trash2 size={14} />}
              onClick={() => setDeleteTarget(row)}
            >
              {SW.watumiaji.futaKabisaKitendo}
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <PageWrapper
      title={SW.nav.watumiaji}
      subtitle={SW.watumiaji.kichwaUkurasa}
      action={
        can('users.write') && (
          <Button onClick={() => { setEditing(null); setDrawerOpen(true) }} leftIcon={<Plus size={16} />}>
            {SW.watumiaji.ongeza}
          </Button>
        )
      }
    >
      <DataTable
        columns={columns}
        data={visibleUsers}
        loading={loading}
        pagination={pagination}
        emptyTitle={SW.watumiaji.hakunaWatumiaji}
      />

      <UserDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        user={editing}
        onSaved={() => { setDrawerOpen(false); load() }}
      />

      <Modal
        open={Boolean(deactivateTarget)}
        onClose={() => setDeactivateTarget(null)}
        title={SW.watumiaji.zimaKichwa}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeactivateTarget(null)}>{SW.common.ghairi}</Button>
            <Button variant="danger" loading={deactivating} onClick={handleDeactivate} leftIcon={<UserX size={15} />}>
              {SW.watumiaji.zimaKitendo}
            </Button>
          </>
        }
      >
        <p className="text-sm font-medium text-text-primary">
          {SW.watumiaji.thibitishaZima(deactivateTarget?.full_name, deactivateTarget?.username)}
        </p>
        <p className="text-sm text-text-secondary mt-2">
          {SW.watumiaji.zimaMaelezo}
        </p>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title={SW.watumiaji.futaKabisaKichwa}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>{SW.common.ghairi}</Button>
            <Button variant="danger" loading={deleting} onClick={handlePermanentDelete} leftIcon={<Trash2 size={15} />}>
              {SW.watumiaji.futaKabisaKitendo}
            </Button>
          </>
        }
      >
        <p className="text-sm font-medium text-text-primary">
          {SW.watumiaji.thibitishaFutaKabisa(deleteTarget?.full_name, deleteTarget?.username)}
        </p>
        <p className="text-sm text-text-secondary mt-2">
          {SW.watumiaji.futaKabisaMaelezo}
        </p>
      </Modal>
    </PageWrapper>
  )
}
