import React, { createContext, useReducer, useCallback } from 'react'

export const CartContext = createContext(null)

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
  const [state, dispatch] = useReducer(reducer, { items: [] })

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
