import React, { createContext, useState, useCallback } from 'react'

export const BranchContext = createContext(null)

export function BranchProvider({ children }) {
  // null means "all branches" (for global roles)
  const [activeBranchId, setActiveBranchId] = useState(null)
  const [branches, setBranches] = useState([])

  const selectBranch = useCallback((id) => {
    setActiveBranchId(id)
  }, [])

  return (
    <BranchContext.Provider value={{ activeBranchId, selectBranch, branches, setBranches }}>
      {children}
    </BranchContext.Provider>
  )
}
