import React, { createContext, useReducer, useCallback, useEffect, useRef } from 'react'
import { useAuth } from '@hooks/useAuth'
import { useBranch } from '@hooks/useBranch'
import { useToast } from '@hooks/useToast'
import SW from '@constants/sw'

export const CartContext = createContext(null)

const STORAGE_KEY = 'dukani_cart'

function readStoredItems() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeStoredItems(items) {
  try {
    if (items.length) localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore (private browsing / storage disabled) — falls back to in-memory only
  }
}

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_ITEM': {
      const existing = state.items.find((i) => i.product_id === action.payload.product_id)
      if (existing) {
        return {
          ...state,
          items: state.items.map((i) =>
            i.product_id === action.payload.product_id
              ? { ...i, quantity: i.quantity + 1 }
              : i
          ),
        }
      }
      return { ...state, items: [...state.items, { ...action.payload, quantity: 1 }] }
    }
    case 'REMOVE_ITEM':
      return { ...state, items: state.items.filter((i) => i.product_id !== action.payload) }
    case 'SET_QTY': {
      const qty = parseInt(action.payload.quantity)
      if (qty <= 0) {
        return { ...state, items: state.items.filter((i) => i.product_id !== action.payload.product_id) }
      }
      return {
        ...state,
        items: state.items.map((i) =>
          i.product_id === action.payload.product_id ? { ...i, quantity: qty } : i
        ),
      }
    }
    case 'CLEAR':
      return { ...state, items: [] }
    default:
      return state
  }
}

export function CartProvider({ children }) {
  // Restored from localStorage on mount, so a refresh/reload on the counter
  // tablet doesn't silently wipe an in-progress sale — but revalidated
  // against the logged-in user below (see the auth effect) since a stale
  // cart from a previous cashier's session must never carry into a
  // different user's login on the same device.
  const [state, dispatch] = useReducer(reducer, undefined, () => ({ items: readStoredItems() }))
  const { user, isAuthenticated } = useAuth()
  const { activeBranchId } = useBranch()
  const toast = useToast()
  const lastUserId = useRef(user?.id ?? null)
  const lastBranchId = useRef(activeBranchId)

  useEffect(() => {
    writeStoredItems(state.items)
  }, [state.items])

  // Clear the cart on logout, and on a different user logging in on the
  // same device/tab — an in-progress sale is per-cashier-session, never a
  // value that should survive into someone else's session.
  useEffect(() => {
    const currentUserId = user?.id ?? null
    if (!isAuthenticated) {
      if (lastUserId.current !== null) {
        dispatch({ type: 'CLEAR' })
      }
      lastUserId.current = null
      return
    }
    if (lastUserId.current !== currentUserId) {
      if (lastUserId.current !== null) {
        dispatch({ type: 'CLEAR' })
      }
      lastUserId.current = currentUserId
    }
  }, [isAuthenticated, user?.id])

  // Clear the cart when the active branch context changes mid-sale (only
  // possible for global roles, via the top branch switcher — a cashier's
  // own branch never changes). Stock availability and the sale's eventual
  // branch attribution both come from whatever branch is active at
  // checkout time, so carrying items across a branch switch would silently
  // risk selling against the wrong branch's stock. Only fires when there
  // was actually something to lose, so it stays silent on login/logout.
  useEffect(() => {
    if (lastBranchId.current === activeBranchId) return
    const hadItems = state.items.length > 0
    lastBranchId.current = activeBranchId
    if (hadItems) {
      dispatch({ type: 'CLEAR' })
      toast.warning(SW.mauzo.kikapuKimefutwaTawiKubadilika)
    }
  }, [activeBranchId])

  const addItem = useCallback((product) => {
    dispatch({ type: 'ADD_ITEM', payload: product })
  }, [])

  const removeItem = useCallback((productId) => {
    dispatch({ type: 'REMOVE_ITEM', payload: productId })
  }, [])

  const setQty = useCallback((productId, quantity) => {
    dispatch({ type: 'SET_QTY', payload: { product_id: productId, quantity } })
  }, [])

  const clear = useCallback(() => {
    dispatch({ type: 'CLEAR' })
  }, [])

  const subtotal = state.items.reduce((sum, i) => sum + i.selling_price * i.quantity, 0)
  const total = subtotal
  const itemCount = state.items.reduce((sum, i) => sum + i.quantity, 0)

  return (
    <CartContext.Provider value={{ items: state.items, addItem, removeItem, setQty, clear, subtotal, total, itemCount }}>
      {children}
    </CartContext.Provider>
  )
}
