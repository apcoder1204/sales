import React, { useState } from 'react'
import { MessageCircle } from 'lucide-react'
import Button from '@components/ui/Button'
import { whatsappService } from '@services/whatsappService'
import { useWhatsAppStatus } from '@hooks/useWhatsAppStatus'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import SW from '@constants/sw'

/**
 * Sends the report PDF produced by `getPdf()` to the designated WhatsApp
 * receiver (configured server-side). Hidden when the feature is off.
 *
 * getPdf: () => Promise<{ blob, filename, title, periodLabel }>  (buildPDF)
 */
export default function SendWhatsAppButton({
  reportType, getPdf, branchId, size, variant = 'secondary', iconOnly = false, disabled = false,
}) {
  const { enabled, configured, connected, refresh } = useWhatsAppStatus()
  const toast = useToast()
  const [sending, setSending] = useState(false)

  if (!enabled) return null

  const reason = !configured ? SW.whatsapp.hakunaNamba : !connected ? SW.whatsapp.haijaunganishwa : null

  const handleSend = async () => {
    setSending(true)
    try {
      const { blob, filename, title, periodLabel } = await getPdf()
      await whatsappService.sendReport({ blob, filename, reportType, title, periodLabel, branchId })
      toast.success(SW.whatsapp.imetumwa)
    } catch (err) {
      if (err?.response?.status === 504 || err?.code === 'ECONNABORTED') {
        toast.error(SW.whatsapp.haijathibitishwa)
      } else {
        toast.error(resolveApiErrorMessage(err))
      }
      // Connection state may have changed (phone logged out, gateway down).
      if (err?.response?.status === 503) refresh()
    } finally {
      setSending(false)
    }
  }

  return (
    <Button
      variant={iconOnly ? 'ghost' : variant}
      size={size}
      leftIcon={<MessageCircle size={iconOnly ? 14 : 15} />}
      onClick={handleSend}
      loading={sending}
      disabled={disabled || sending || !!reason}
      title={reason || SW.whatsapp.tuma}
    >
      {iconOnly ? null : SW.whatsapp.tuma}
    </Button>
  )
}
