import { useCallback } from 'react'
import { apiRequest, ApiError, RequestOptions } from '../lib/api'
import { useAuth } from '../contexts/AuthContext'

export function useApi() {
  const { token, logout } = useAuth()

  const request = useCallback(
    async <T>(path: string, options: Omit<RequestOptions, 'token'> = {}): Promise<T> => {
      try {
        return await apiRequest<T>(path, {
          ...options,
          token,
        })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          logout()
        }
        throw error
      }
    },
    [token, logout]
  )

  return { request }
}
