import React, { useEffect, useState } from 'react'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Modal from '@components/ui/Modal'
import Select from '@components/ui/Select'
import { reconciliationService } from '@services/reconciliationService'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { codeText, recordLabel } from '@utils/reconciliationLabels'
import SW from '@constants/sw'

const NEXT = { OPEN: ['UNDER_REVIEW', 'RESOLVED', 'DISMISSED'], UNDER_REVIEW: ['OPEN', 'RESOLVED', 'DISMISSED'] }

// Admins move a discrepancy through review. The server refuses "resolved"
// while the discrepancy is still there, and that message is shown here.
export default function ExceptionStatusModal({ exception, onClose, onDone }) {
  const U = SW.upatanisho
  const toast = useToast()
  const [status, setStatus] = useState('')
  const [reason, setReason] = useState('')
  const [reference, setReference] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (exception) {
      setStatus(NEXT[exception.status]?.[0] || '')
      setReason('')
      setReference('')
      setError(null)
    }
  }, [exception])

  if (!exception) return null
  const needsReference = status === 'RESOLVED' || status === 'DISMISSED'
  const canSave = status && reason.trim().length >= 5 && (!needsReference || reference.trim())

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await reconciliationService.exceptions.changeStatus(exception.id, {
        status, reason: reason.trim(), reference: reference.trim() || undefined,
      })
      toast.success(U.imebadilishwa)
      onDone?.()
      onClose()
    } catch (err) {
      setError(resolveApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={!!exception}
      onClose={onClose}
      title={U.badilishaHali}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={saving} disabled={!canSave} onClick={save}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm">{codeText(exception.code)}</p>
        <p className="text-xs text-text-muted">{recordLabel(exception)}</p>
        <Select
          label={U.haliMpya}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={(NEXT[exception.status] || []).map((s) => ({ value: s, label: U.haliTofauti[s] }))}
        />
        <Input label={U.sababu} value={reason} onChange={(e) => setReason(e.target.value)} required />
        <Input
          label={U.kumbukumbu}
          placeholder={U.kumbukumbuMaelezo}
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          required={needsReference}
        />
        {error && <p className="text-sm text-accent-red">{error}</p>}
      </div>
    </Modal>
  )
}
