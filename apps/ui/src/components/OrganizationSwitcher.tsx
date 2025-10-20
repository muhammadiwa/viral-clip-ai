import { FormEvent, useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../contexts/AuthContext'
import { useOrg } from '../contexts/OrgContext'
import { useOrganizations } from '../hooks/useOrganizations'
import { useApi } from '../hooks/useApi'
import type { OrganizationCreateResponse } from '../types'

export function OrganizationSwitcher() {
  const { user } = useAuth()
  const { orgId, setOrgId } = useOrg()
  const { data, isLoading, error } = useOrganizations()
  const organizations = data?.data ?? []
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const { request } = useApi()
  const queryClient = useQueryClient()

  useEffect(() => {
    if (organizations.length === 0) {
      return
    }
    if (!orgId || !organizations.find((org) => org.id === orgId)) {
      setOrgId(organizations[0].id)
    }
  }, [orgId, organizations, setOrgId])

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault()
    if (!name) {
      setFormError('Organization name is required')
      return
    }
    try {
      setFormError(null)
      const response = await request<OrganizationCreateResponse>('/v1/organizations', {
        method: 'POST',
        body: { name, slug: slug || undefined, owner_user_id: user?.id },
      })
      await queryClient.invalidateQueries({ queryKey: ['organizations'] })
      setOrgId(response.data.id)
      setShowForm(false)
      setName('')
      setSlug('')
    } catch (err) {
      if (err instanceof Error) {
        setFormError(err.message)
      } else {
        setFormError('Unable to create organization')
      }
    }
  }

  if (isLoading) {
    return <span className="text-sm text-slate-400">Loading organizations…</span>
  }

  if (error) {
    return <span className="text-sm text-red-400">Failed to load organizations</span>
  }

  return (
    <div className="flex items-center gap-3">
      <select
        className="rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm"
        value={orgId ?? ''}
        onChange={(event) => setOrgId(event.target.value || null)}
      >
        {organizations.map((org) => (
          <option key={org.id} value={org.id}>
            {org.name}
          </option>
        ))}
        {organizations.length === 0 && <option value="">No organizations</option>}
      </select>
      <div className="relative">
        <button
          type="button"
          onClick={() => setShowForm((prev) => !prev)}
          className="rounded-lg border border-white/10 px-3 py-2 text-xs uppercase tracking-wide text-slate-200 hover:bg-white/10"
        >
          {showForm ? 'Cancel' : 'New Org'}
        </button>
        {showForm && (
          <form
            onSubmit={handleCreate}
            className="absolute right-0 z-10 mt-3 w-72 space-y-3 rounded-2xl border border-white/10 bg-slate-900 p-4 shadow-xl"
          >
            <div>
              <label className="block text-xs uppercase tracking-wide text-slate-400">
                Name
              </label>
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Studio Nebula"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wide text-slate-400">
                Slug
              </label>
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder="studio-nebula"
              />
            </div>
            {formError && <p className="text-xs text-red-400">{formError}</p>}
            <button
              type="submit"
              className="w-full rounded-lg bg-indigo-500 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-400"
            >
              Create organization
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
