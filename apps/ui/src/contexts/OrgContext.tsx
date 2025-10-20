import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

interface OrgContextValue {
  orgId: string | null
  setOrgId: (id: string | null) => void
}

const OrgContext = createContext<OrgContextValue | undefined>(undefined)
const STORAGE_KEY = 'viral-clip-ai:org-id'

export function OrgProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [orgId, setOrgIdState] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY))

  const setOrgId = useCallback(
    (id: string | null) => {
      setOrgIdState(id)
      if (id) {
        localStorage.setItem(STORAGE_KEY, id)
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['project'] })
      queryClient.invalidateQueries({ queryKey: ['videos'] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['transcripts'] })
      queryClient.invalidateQueries({ queryKey: ['clips'] })
      queryClient.invalidateQueries({ queryKey: ['artifacts'] })
    },
    [queryClient]
  )

  useEffect(() => {
    if (!orgId) {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [orgId])

  const value = useMemo<OrgContextValue>(() => ({ orgId, setOrgId }), [orgId, setOrgId])

  return <OrgContext.Provider value={value}>{children}</OrgContext.Provider>
}

export function useOrg(): OrgContextValue {
  const context = useContext(OrgContext)
  if (!context) {
    throw new Error('useOrg must be used within OrgProvider')
  }
  return context
}
