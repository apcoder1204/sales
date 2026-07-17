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
import { usePagination } from '@hooks/usePagination'
import SW from '@constants/sw'

const TABS = [
  { key: 'requests', label: 'Maombi ya Bidhaa' },
  { key: 'transfers', label: 'Uhamisho wa Moja kwa Moja' },
]

export default function TransfersPage() {
  const { can, role } = usePermission()
  const [tab, setTab] = useState('requests')
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
        const res = await transferService.listRequests(pagination.params)
        setRequests(res.items || res)
        if (res.total !== undefined) pagination.setTotal(res.total)
      } else {
        const res = await transferService.listTransfers(pagination.params)
        setTransfers(res.items || res)
        if (res.total !== undefined) pagination.setTotal(res.total)
      }
    } finally {
      setLoading(false)
    }
  }, [tab, pagination.page])

  useEffect(() => { load() }, [load])
  useEffect(() => { pagination.reset() }, [tab])

  const onReviewed = () => { setReviewing(null); load() }

  return (
    <PageWrapper
      title={SW.nav.uhamisho}
      subtitle="Simamia uhamisho wa bidhaa kati ya matawi"
      action={
        <div className="flex gap-2">
          <Button onClick={() => setCreateOpen(true)} leftIcon={<Plus size={16} />} variant="secondary">
            Omba Bidhaa
          </Button>
          {can('transfers.execute') && role !== 'cashier' && (
            <Button onClick={() => setDirectOpen(true)} leftIcon={<ArrowLeftRight size={16} />}>
              Uhamisho wa Moja kwa Moja
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
