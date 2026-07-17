import React from 'react'
import Modal from '@components/ui/Modal'
import Badge from '@components/ui/Badge'
import Divider from '@components/ui/Divider'
import { formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

const ACTION_COLORS = {
  create: 'green', update: 'blue', delete: 'red', login: 'purple',
  logout: 'gray', approve: 'green', reject: 'red', execute: 'yellow',
}

export default function AuditDetailModal({ open, log, onClose }) {
  if (!log) return null

  return (
    <Modal open={open} onClose={onClose} title="Maelezo ya Kumbukumbu" size="md">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-text-muted text-xs mb-1">Kitendo</p>
            <Badge color={ACTION_COLORS[log.action] || 'gray'}>{log.action}</Badge>
          </div>
          <div>
            <p className="text-text-muted text-xs mb-1">Kitengo</p>
            <p className="text-text-primary uppercase text-xs">{log.category}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs mb-1">Mtumiaji</p>
            <p className="text-text-primary">{log.username}</p>
            <p className="text-xs text-text-muted">{SW.majukumu[log.user_role] || log.user_role}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs mb-1">Wakati</p>
            <p className="text-text-primary">{formatDateTime(log.created_at)}</p>
          </div>
          {log.resource_type && (
            <div>
              <p className="text-text-muted text-xs mb-1">Kitu</p>
              <p className="text-text-primary">{log.resource_type}</p>
            </div>
          )}
          {log.ip_address && (
            <div>
              <p className="text-text-muted text-xs mb-1">Anwani ya IP</p>
              <p className="font-mono text-text-primary text-sm">{log.ip_address}</p>
            </div>
          )}
        </div>

        {log.details && (
          <>
            <Divider label="Maelezo ya Kina (JSONB)" />
            <div className="bg-bg rounded-lg p-4 overflow-x-auto">
              <pre className="text-xs text-accent-green font-mono whitespace-pre-wrap">
                {JSON.stringify(log.details, null, 2)}
              </pre>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
