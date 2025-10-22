import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiRequest, ApiError } from '../lib/api'
import type { TokenResponse, RegisterResponse, User } from '../types'

interface AuthContextValue {
  user: User | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string, organizationName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const TOKEN_KEY = 'viral-clip-ai:token'
const USER_KEY = 'viral-clip-ai:user'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem(USER_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as User
    } catch (err) {
      console.warn('Failed to parse cached user', err)
      return null
    }
  })
  const [loading, setLoading] = useState<boolean>(!!token && !user)

  useEffect(() => {
    if (!token || user) {
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const response = await apiRequest<{ data: User }>(`/v1/auth/me`, {
          token,
        })
        if (!cancelled) {
          setUser(response.data)
          localStorage.setItem(USER_KEY, JSON.stringify(response.data))
        }
      } catch (error) {
        console.error('Unable to hydrate session', error)
        if (!cancelled) {
          clearSession()
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [token, user])

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  const login = useCallback(
    async (email: string, password: string) => {
      setLoading(true)
      try {
        const payload: TokenResponse = await apiRequest(`/v1/auth/token`, {
          method: 'POST',
          body: { email, password },
        })
        setToken(payload.access_token)
        setUser(payload.user)
        localStorage.setItem(TOKEN_KEY, payload.access_token)
        localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
        queryClient.clear()
      } catch (error) {
        if (error instanceof ApiError) {
          throw error
        }
        throw new ApiError('Unable to login, please try again', 500)
      } finally {
        setLoading(false)
      }
    },
    [queryClient]
  )

  const register = useCallback(
    async (email: string, password: string, fullName: string, organizationName: string) => {
      setLoading(true)
      try {
        const payload: TokenResponse = await apiRequest(`/v1/auth/register`, {
          method: 'POST',
          body: { 
            email, 
            password, 
            full_name: fullName,
            organization_name: organizationName,
          },
        })
        setToken(payload.access_token)
        setUser(payload.user)
        localStorage.setItem(TOKEN_KEY, payload.access_token)
        localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
        queryClient.clear()
      } catch (error) {
        if (error instanceof ApiError) {
          throw error
        }
        throw new ApiError('Unable to register, please try again', 500)
      } finally {
        setLoading(false)
      }
    },
    [queryClient]
  )

  const logout = useCallback(() => {
    clearSession()
  }, [clearSession])

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, loading, login, register, logout }),
    [user, token, loading, login, register, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
