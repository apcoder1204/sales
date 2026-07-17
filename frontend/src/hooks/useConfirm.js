import { useState, useCallback } from 'react'

export function useConfirm() {
  const [state, setState] = useState({ open: false, message: '', resolve: null })

  const confirm = useCallback((message) => {
    return new Promise((resolve) => {
      setState({ open: true, message, resolve })
    })
  }, [])

  const handleConfirm = useCallback(() => {
    state.resolve?.(true)
    setState({ open: false, message: '', resolve: null })
  }, [state])

  const handleCancel = useCallback(() => {
    state.resolve?.(false)
    setState({ open: false, message: '', resolve: null })
  }, [state])

  return {
    confirmState: state,
    confirm,
    handleConfirm,
    handleCancel,
  }
}
