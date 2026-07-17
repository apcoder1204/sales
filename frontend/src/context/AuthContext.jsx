import React, { createContext, useReducer, useEffect, useCallback } from 'react'
import { authService } from '@services/authService'
import { tokenStorage } from '@services/api'

export const AuthContext = createContext(null)

const initialState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_USER':
      return { ...state, user: action.payload, isAuthenticated: true, isLoading: false }
    case 'CLEAR_USER':
      return { ...state, user: null, isAuthenticated: false, isLoading: false }
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload }
    default:
      return state
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const loadUser = useCallback(async () => {
    if (!tokenStorage.getAccess()) {
      dispatch({ type: 'CLEAR_USER' })
      return
    }
    try {
      const user = await authService.getMe()
      dispatch({ type: 'SET_USER', payload: user })
    } catch {
      tokenStorage.clear()
      dispatch({ type: 'CLEAR_USER' })
    }
  }, [])

  useEffect(() => {
    loadUser()
  }, [loadUser])

  const login = async (username, password) => {
    const data = await authService.login(username, password)
    tokenStorage.setTokens(data.access_token, data.refresh_token)
    dispatch({ type: 'SET_USER', payload: data.user })
    return data
  }

  const logout = async () => {
    try {
      await authService.logout()
    } finally {
      // Always clear tokens even if the server-side logout fails
      tokenStorage.clear()
      dispatch({ type: 'CLEAR_USER' })
    }
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, reload: loadUser }}>
      {children}
    </AuthContext.Provider>
  )
}
