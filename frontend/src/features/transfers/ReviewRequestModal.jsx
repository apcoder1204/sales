import React, { useState, useEffect } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Badge from '@components/ui/Badge'
import Divider from '@components/ui/Divider'
import { transferService } from '@services/transferService'
import { usePermission } from '@hooks/usePermission'
import { useAuth } from '@hooks/useAuth'
import { useApi } from '@hooks/useApi'
import { formatDateTime } from '@utils/formatters'
import { TRANSFER_STATUSES } from '@utils/constants'
import { isGlobalRole } from '@utils/permissions'
import SW from '@constants/sw'

export default function ReviewRequestModal({ open, request, onClose, onUpdated }) {
  const { can } = usePermission()
  const { user } = useAuth()
  const { loading, call } = useApi()
  const [rejectReason, setRejectReason] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [approvedQty, setApprovedQty] = useState({})
  const [approveNotes, setApproveNotes] = useState('')

  const statusInfo = TRANSFER_STATUSES[request?.status] || { label: request?.status, color: 'gray' }

  useEffect(() => {
    if (!request) return
    const initial = {}
    for (const item of request.items || []) {
      initial[item.id] = String(item.requested_qty)
    }
    setApprovedQty(initial)
    setApproveNotes('')
  }, [request?.id])

  const handleApprove = () => call(
    () => transferService.approveRequest(request.id, {
      notes: approveNotes || undefined,
      items: (request.items || []).map((item) => ({
        item_id: item.id,
        approved_qty: parseInt(approvedQty[item.id] ?? item.requested_qty) || 0,
      })),
    }),
    { successMsg: SW.mafanikio.imekubaliwa, onSuccess: onUpdated }
  )

  const handleReject = () => call(
    () => transferService.rejectRequest(request.id, rejectReason),
    { successMsg: SW.mafanikio.imekataliwa, onSuccess: onUpdated }
  )

  const handleExecute = () => call(
    () => transferService.executeTransfer(request.id),
    { successMsg: SW.mafanikio.imesafirishwa, onSuccess: onUpdated }
  )

  if (!request) return null
  const isPending = request.status === 'pending'
  const isApproved = request.status === 'approved'
  // Execution is a physical handover — only whoever's providing the stock
  // may confirm it: admin/super_admin can always execute, everyone else only
  // for requests sourced from their own branch (store_keeper's is Duka Kuu).
  const canExecuteThis = can('transfers.execute')
    && (isGlobalRole(user) || user?.branch_id === request.from_branch_id)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Ombi: ${request.request_no}`}
      size="md"
      footer={
        <div className="flex gap-2 flex-wrap w-full">
          <Button variant="secondary" onClick={onClose} className="mr-auto">{SW.common.ghairi}</Button>
          {isPending && can('transfers.approve') && (
            <>
              <Button variant="danger" onClick={() => setShowReject(true)}>{SW.uhamisho.kataOmbi}</Button>
              <Button variant="success" onClick={handleApprove} loading={loading}>{SW.uhamisho.thibitishaOmbi}</Button>
            </>
          )}
          {isApproved && canExecuteThis && (
            <Button onClick={handleExecute} loading={loading}>{SW.uhamisho.tekeleza}</Button>
          )}
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-text-muted text-xs">Hali</p>
            <div className="flex items-center gap-1.5 mt-1">
              <Badge color={statusInfo.color}>{statusInfo.label}</Badge>
              {request.is_partial && <Badge color="yellow">Sehemu</Badge>}
            </div>
          </div>
          <div>
            <p className="text-text-muted text-xs">Tarehe</p>
            <p className="text-text-primary mt-1">{formatDateTime(request.created_at)}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs">Chanzo</p>
            <p className="text-accent-yellow mt-1 font-medium">{request.from_branch}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs">Lengo</p>
            <p className="text-accent-green mt-1 font-medium">{request.to_branch}</p>
          </div>
        </div>

        <Divider label={SW.uhamisho.bidhaa} />
        <div className="space-y-3">
          {(request.items || []).map((item) => (
            <div key={item.id || item.product_id} className="flex justify-between items-start text-sm gap-3">
              <div className="min-w-0">
                <p className="font-medium text-text-primary truncate">{item.product}</p>
                <p className="text-xs text-text-muted">{item.product_code} · Ombi: {item.requested_qty}</p>
                {item.main_store_had_stock === false && (
                  <p className="text-xs text-accent-yellow mt-0.5">{SW.uhamisho.chanzoNyingine}</p>
                )}
              </div>
              {isPending && can('transfers.approve') ? (
                <Input
                  type="number" min="0" max={item.requested_qty}
                  value={approvedQty[item.id] ?? ''}
                  onChange={(e) => setApprovedQty((p) => ({ ...p, [item.id]: e.target.value }))}
                  containerClassName="w-20 flex-shrink-0"
                />
              ) : (
                <div className="text-right flex-shrink-0">
                  <span className="text-text-primary font-medium">× {item.approved_qty ?? item.requested_qty}</span>
                  {item.approved_qty != null && item.approved_qty !== item.requested_qty && (
                    <p className="text-xs text-accent-yellow">ya {item.requested_qty}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {isPending && can('transfers.approve') && (
          <Input
            label="Maelezo ya Idhini (hiari)"
            value={approveNotes}
            onChange={(e) => setApproveNotes(e.target.value)}
            placeholder="Sababu ya kupunguza idadi, n.k..."
          />
        )}

        {request.reason && (
          <>
            <Divider />
            <div>
              <p className="text-xs text-text-muted mb-1">Sababu ya Ombi</p>
              <p className="text-sm text-text-secondary">{request.reason}</p>
            </div>
          </>
        )}

        {showReject && (
          <>
            <Divider />
            <Input
              label="Sababu ya Kukataa"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Eleza sababu..."
              required
            />
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setShowReject(false)} className="flex-1">Ghairi</Button>
              <Button variant="danger" onClick={handleReject} loading={loading} disabled={!rejectReason} className="flex-1">
                {SW.uhamisho.kataOmbi}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
