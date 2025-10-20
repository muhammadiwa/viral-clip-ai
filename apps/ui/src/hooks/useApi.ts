import { useCallback } from 'react'
import { apiRequest, ApiError, RequestOptions } from '../lib/api'
import { useAuth } from '../contexts/AuthContext'
import { useOrg } from '../contexts/OrgContext'

export function useApi() {
  const { token, logout } = useAuth()
  const { orgId } = useOrg()

  const request = useCallback(
    async <T,>(path: string, options: Omit<RequestOptions, 'token' | 'orgId'> = {}) => {
      try {
        return await apiRequest<T>(path, { ...options, token, orgId })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          logout()
        }
        throw error
      }
    },
    [token, orgId, logout]
  )

  return { request, token, orgId }
}
