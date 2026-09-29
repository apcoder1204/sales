import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Modal from '@components/ui/Modal'
import BranchDrawer from './BranchDrawer'
import { branchService } from '@services/branchService'
import { useApi } from '@hooks/useApi'
import { useToast } from '@hooks/useToast'
import { formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

export default function BranchesPage() {
  const [branches, setBranches] = useState([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const { loading: deleting, call: callDelete } = useApi()
  const toast = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setBranches(await branchService.list())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async () => {
    await callDelete(
      () => branchService.remove(deleteTarget.id),
      {
        // The backend decides delete-vs-deactivate based on whether this
        // branch has any real activity history — the response tells us
        // which one actually happened, so the toast reflects reality
        // instead of always claiming "deleted".
        onSuccess: (res) => {
          toast.success(res.deleted ? SW.mafanikio.imefutwa : SW.mafanikio.imezimwa)
          setDeleteTarget(null)
          load()
        },
        silent: true,
      }
    )
  }

  const columns = [
    {
      key: 'name', header: SW.matawiUsimamizi.jina,
      render: (v, row) => (
        <div>
          <p className="font-medium text-text-primary">{v}</p>
          <p className="text-xs text-text-muted">{row.code}</p>
        </div>
      ),
    },
    {
      key: 'branch_type', header: SW.matawiUsimamizi.aina,
      render: (v) => (
        <Badge color={v === 'main_store' ? 'purple' : 'blue'}>
          {v === 'main_store' ? SW.matawiUsimamizi.ainaGhalaKuu : SW.matawiUsimamizi.ainaSehemuYaMauzo}
        </Badge>
      ),
    },
    { key: 'address', header: SW.matawiUsimamizi.anwani, render: (v) => <span className="text-text-secondary text-sm">{v || '—'}</span> },
    { key: 'phone', header: SW.matawiUsimamizi.simu, render: (v) => <span className="text-text-secondary text-sm">{v || '—'}</span> },
    {
      key: 'is_active', header: SW.matawiUsimamizi.hali,
      render: (v) => <Badge color={v ? 'green' : 'red'}>{v ? SW.matawiUsimamizi.hai : SW.matawiUsimamizi.hafanyiKazi}</Badge>,
    },
    { key: 'created_at', header: SW.matawiUsimamizi.ameundwa, render: (v) => formatDateTime(v) },
    {
      key: '_actions', header: '',
      render: (_, row) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => { setEditing(row); setDrawerOpen(true) }}>
            {SW.matawiUsimamizi.haririKitendo}
          </Button>
          <Button
            variant="danger" size="sm"
            leftIcon={<Trash2 size={14} />}
            onClick={() => setDeleteTarget(row)}
          >
            {SW.matawiUsimamizi.futaKitendo}
          </Button>
        </div>
      ),
    },
  ]

  return (
    <PageWrapper
      title={SW.nav.matawi}
      subtitle={SW.matawiUsimamizi.kichwaUkurasa}
      action={
        <Button onClick={() => { setEditing(null); setDrawerOpen(true) }} leftIcon={<Plus size={16} />}>
          {SW.matawiUsimamizi.ongeza}
        </Button>
      }
    >
      <DataTable
        columns={columns}
        data={branches}
        loading={loading}
        emptyTitle={SW.matawiUsimamizi.hakunaMatawi}
      />

      <BranchDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        branch={editing}
        onSaved={() => { setDrawerOpen(false); load() }}
      />

      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title={SW.matawiUsimamizi.futaKichwa}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>{SW.common.ghairi}</Button>
            <Button variant="danger" loading={deleting} onClick={handleDelete} leftIcon={<Trash2 size={15} />}>
              {SW.matawiUsimamizi.futaKitendo}
            </Button>
          </>
        }
      >
        <p className="text-sm font-medium text-text-primary">
          {SW.matawiUsimamizi.thibitishaFuta(deleteTarget?.name)}
        </p>
        <p className="text-sm text-text-secondary mt-2">
          {SW.matawiUsimamizi.futaMaelezo}
        </p>
      </Modal>
    </PageWrapper>
  )
}
