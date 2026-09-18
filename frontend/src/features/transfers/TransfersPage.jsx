import React, { useState, useEffect, useCallback } from 'react'
import { Plus, ArrowLeftRight } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import RequestsTable from './RequestsTable'
import TransfersTable from './TransfersTable'
import CreateRequestModal from './CreateRequestModal'
import DirectTransferModal from './DirectTransferModal'
import ReviewRequestModal from './ReviewRequestModal'
import { transferService } from '@services/transferService'
import { usePermission } from '@hooks/usePermission'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import { usePagination } from '@hooks/usePagination'
import SW from '@constants/sw'

export default function TransfersPage() {
  const { can, role } = usePermission()
  const branchFilter = useActiveBranchFilter()
  const [tab, setTab] = useState('requests')

  const TABS = [
    { key: 'requests', label: SW.uhamisho.maombi },
    { key: 'transfers', label: SW.uhamisho.uhamishoWaKumoja },
  ]
  const [requests, setRequests] = useState([])
  const [transfers, setTransfers] = useState([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [directOpen, setDirectOpen] = useState(false)
  const [reviewing, setReviewing] = useState(null)
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'requests') {
        const res = await transferService.listRequests({ ...branchFilter, ...pagination.params })
        setRequests(res.items || res)
        if (res.total !== undefined) pagination.setTotal(res.total)
      } else {
        const res = await transferService.listTransfers({ ...branchFilter, ...pagination.params })
        setTransfers(res.items || res)
        if (res.total !== undefined) pagination.setTotal(res.total)
      }
    } finally {
      setLoading(false)
    }
  }, [tab, branchFilter.branch_id, pagination.page])

  useEffect(() => { load() }, [load])
  useEffect(() => { pagination.reset() }, [tab, branchFilter.branch_id])

  const onReviewed = () => { setReviewing(null); load() }

  return (
    <PageWrapper
      title={SW.nav.uhamisho}
      subtitle={SW.uhamisho.subtitlePage}
      action={
        <div className="flex gap-2">
          <Button onClick={() => setCreateOpen(true)} leftIcon={<Plus size={16} />} variant="secondary">
            {SW.uhamisho.ombaBidhaaBtn}
          </Button>
          {can('transfers.execute') && role !== 'cashier' && (
            <Button onClick={() => setDirectOpen(true)} leftIcon={<ArrowLeftRight size={16} />}>
              {SW.uhamisho.uhamishoWaKumoja}
            </Button>
          )}
        </div>
      }
    >
      {/* Tabs */}
      <div className="flex border-b border-border gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-primary text-primary-light'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'requests' ? (
        <RequestsTable
          requests={requests}
          loading={loading}
          onReview={setReviewing}
          pagination={pagination}
        />
      ) : (
        <TransfersTable
          transfers={transfers}
          loading={loading}
          pagination={pagination}
        />
      )}

      <CreateRequestModal open={createOpen} onClose={() => setCreateOpen(false)} onSaved={() => { setCreateOpen(false); load() }} />
      <DirectTransferModal open={directOpen} onClose={() => setDirectOpen(false)} onSaved={() => { setDirectOpen(false); load() }} />
      {reviewing && (
        <ReviewRequestModal open={!!reviewing} request={reviewing} onClose={() => setReviewing(null)} onUpdated={onReviewed} />
      )}
    </PageWrapper>
  )
}
