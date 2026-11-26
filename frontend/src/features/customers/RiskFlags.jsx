import React from 'react'
import Badge from '@components/ui/Badge'
import SW from '@constants/sw'

// Factual risk indicators (brief §15) — facts about the account, never a
// judgement of the customer.
const COLOR = {
  OVER_LIMIT: 'red', NEAR_LIMIT: 'yellow', OVERDUE: 'red', LONG_OUTSTANDING: 'purple', INACTIVE_WITH_DEBT: 'gray',
}

export default function RiskFlags({ flags, className = '' }) {
  if (!flags?.length) return null
  return (
    <div className={`flex flex-wrap gap-1 ${className}`}>
      {flags.map((f) => <Badge key={f} color={COLOR[f] || 'gray'}>{SW.hatari[f] || f}</Badge>)}
    </div>
  )
}
