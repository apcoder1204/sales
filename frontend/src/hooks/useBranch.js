import { useContext } from 'react'
import { BranchContext } from '@context/BranchContext'

export function useBranch() {
  const ctx = useContext(BranchContext)
  if (!ctx) throw new Error('useBranch must be used within BranchProvider')
  return ctx
}
