import React, { useEffect, useState } from 'react'
import { MessageCircle } from 'lucide-react'
import Card from '@components/ui/Card'
import Input from '@components/ui/Input'
import Button from '@components/ui/Button'
import Badge from '@components/ui/Badge'
import { whatsappService } from '@services/whatsappService'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import SW from '@constants/sw'

/**
 * Admin card for the single WhatsApp number that receives every report sent
 * with "Tuma WhatsApp". Not rendered when the feature is off on this server.
 */
export default function WhatsAppSettingsCard() {
  const toast = useToast()
  const [settings, setSettings] = useState(null)
  const [number, setNumber] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    whatsappService
      .getSettings()
      .then((s) => {
        setSettings(s)
        setNumber(s.number || '')
      })
      .catch(() => setSettings(null))
  }, [])

  if (!settings?.enabled) return null

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const s = await whatsappService.updateSettings(number)
      setSettings(s)
      setNumber(s.number || '')
      toast.success(SW.whatsapp.imehifadhiwa)
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card
      className="mb-6"
      title={
        <span className="flex items-center gap-2">
          <MessageCircle size={16} /> {SW.whatsapp.mipangilio}
        </span>
      }
      action={
        <Badge color={settings.connected ? 'green' : 'red'}>
          {settings.connected ? SW.whatsapp.imeunganishwa : SW.whatsapp.haijaunganishwa}
        </Badge>
      }
    >
      <p className="text-sm text-text-secondary mb-4">{SW.whatsapp.maelezo}</p>
      <form onSubmit={handleSave} className="flex flex-wrap items-end gap-3">
        <div className="w-full max-w-xs">
          <Input
            label={SW.whatsapp.nambaYaKupokea}
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            placeholder="0712 345 678"
            hint={settings.locked ? SW.whatsapp.imefungwaNaSeva : SW.whatsapp.mfanoNamba}
            disabled={settings.locked}
            inputMode="tel"
          />
        </div>
        {!settings.locked && (
          <Button type="submit" loading={saving} disabled={!number.trim()}>
            {SW.whatsapp.hifadhi}
          </Button>
        )}
      </form>
    </Card>
  )
}
