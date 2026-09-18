import { useState, useEffect } from 'react'
import { reportService } from '@services/reportService'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'

export function useDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const branchFilter = useActiveBranchFilter()

  useEffect(() => {
    setLoading(true)
    reportService.dashboard(branchFilter)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [branchFilter.branch_id])

  return { data, loading }
}
