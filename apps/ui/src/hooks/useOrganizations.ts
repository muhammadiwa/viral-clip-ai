import { useQuery } from '@tanstack/react-query'
import { useApi } from './useApi'
import type { OrganizationListResponse } from '../types'

export function useOrganizations() {
  const { request, token } = useApi()
  return useQuery({
    queryKey: ['organizations'],
    queryFn: () => request<OrganizationListResponse>('/v1/organizations'),
    enabled: !!token,
    staleTime: 60_000,
  })
}
