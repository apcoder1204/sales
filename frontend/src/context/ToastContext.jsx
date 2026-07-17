import React, { createContext, useReducer, useCallback } from 'react'

export const ToastContext = createContext(null)

let nextId = 0

function reducer(state, action) {
  switch (action.type) {
    case 'ADD':
      return [...state, action.payload]
    case 'REMOVE':
      return state.filter((t) => t.id !== action.payload)
    default:
      return state
  }
}

export function ToastProvider({ children }) {
  const [toasts, dispatch] = useReducer(reducer, [])

  const toast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++nextId
    dispatch({ type: 'ADD', payload: { id, message, type, duration } })
    setTimeout(() => dispatch({ type: 'REMOVE', payload: id }), duration)
    return id
  }, [])

  const dismiss = useCallback((id) => {
    dispatch({ type: 'REMOVE', payload: id })
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
    </ToastContext.Provider>
  )
}
