import React, { createContext, useState, useCallback, useEffect, useRef } from 'react'
import { useAuth } from '@hooks/useAuth'
import { useToast } from '@hooks/useToast'
import SW from '@constants/sw'

export const BranchContext = createContext(null)

const STORAGE_KEY = 'dukani_branch'

function readStoredBranchId() {
  try {
    return localStorage.getItem(STORAGE_KEY) || null
  } catch {
    return null
  }
}

function writeStoredBranchId(id) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore (private browsing / storage disabled) — falls back to in-memory only
  }
}

export function BranchProvider({ children }) {
  // null means "all branches" (for global roles). Restored from
  // localStorage on mount so a refresh/new-tab doesn't silently drop back to
  // ALL — but re-validated against the user's own authorized branch list
  // below (see the `branches` effect) since a stale id from a previous
  // session/user must never be trusted blindly.
  const [activeBranchId, setActiveBranchId] = useState(readStoredBranchId)
  const [branches, setBranchesState] = useState([])
  const { user, isAuthenticated } = useAuth()
  const toast = useToast()
  const lastUserId = useRef(user?.id ?? null)

  const selectBranch = useCallback((id) => {
    setActiveBranchId(id)
    writeStoredBranchId(id)
  }, [])

  const setBranches = useCallback((list) => {
    setBranchesState(list)
  }, [])

  // Revalidate the persisted/current selection against the freshly-fetched
  // authorized branch list — if it's no longer in there (branch deactivated,
  // user's access changed, or it was a stale id from local storage that was
  // never actually authorized for this user), explicitly notify and fall
  // back to ALL rather than silently keep filtering by a branch the user
  // can no longer see, or silently switching them to a different one.
  useEffect(() => {
    if (branches.length === 0) return
    if (activeBranchId && !branches.some((b) => b.id === activeBranchId)) {
      setActiveBranchId(null)
      writeStoredBranchId(null)
      toast.warning(SW.common.tawiHalipatikaniTena)
    }
  }, [branches, activeBranchId])

  // Clear branch context on logout, and revalidate on a different user
  // logging in — the selection is a per-user/per-session concept, never a
  // value that should survive into someone else's session in the same tab.
  useEffect(() => {
    const currentUserId = user?.id ?? null
    if (!isAuthenticated) {
      if (lastUserId.current !== null) {
        setActiveBranchId(null)
        writeStoredBranchId(null)
        setBranchesState([])
      }
      lastUserId.current = null
      return
    }
    if (lastUserId.current !== currentUserId) {
      // A different user than whoever was last authenticated in this tab —
      // don't inherit their branch selection.
      if (lastUserId.current !== null) {
        setActiveBranchId(null)
        writeStoredBranchId(null)
      }
      setBranchesState([])
      lastUserId.current = currentUserId
    }
  }, [isAuthenticated, user?.id])

  return (
    <BranchContext.Provider value={{ activeBranchId, selectBranch, branches, setBranches }}>
      {children}
    </BranchContext.Provider>
  )
}
