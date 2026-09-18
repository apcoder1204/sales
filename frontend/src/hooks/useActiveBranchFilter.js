import { usePermission } from '@hooks/usePermission'
import { useBranch } from '@hooks/useBranch'

/** branch_id query param for global roles when a top-bar branch is selected. */
export function useActiveBranchFilter() {
  const { isGlobal } = usePermission()
  const { activeBranchId } = useBranch()

  if (isGlobal && activeBranchId) {
    return { branch_id: activeBranchId }
  }
  return {}
}
