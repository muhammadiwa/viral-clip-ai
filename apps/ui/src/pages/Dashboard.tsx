import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../hooks/useApi'
import { ProjectList } from '../components/ProjectList'
import { BillingSummary } from '../components/BillingSummary'
import { QAQualitySummary } from '../components/QAQualitySummary'
import type { ProjectListResponse, ProjectResponse } from '../types'

export default function DashboardPage() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => request<ProjectListResponse>('/v1/projects'),
  })

  const createProject = useMutation({
    mutationFn: () =>
      request<ProjectResponse>('/v1/projects', {
        method: 'POST',
        body: {
          name,
          description: description || undefined,
          source_url: sourceUrl || undefined,
        },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowForm(false)
      setName('')
      setDescription('')
      setSourceUrl('')
      setError(null)
    },
    onError: (err) => {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Unable to create project')
      }
    },
  })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    createProject.mutate()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Projects</h1>
          <p className="text-sm text-slate-400">
            Manage ingest pipelines, monitor job progress, and export finished stories.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((prev) => !prev)}
          className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400"
        >
          {showForm ? 'Close form' : 'New project'}
        </button>
      </div>

      <BillingSummary />
      <QAQualitySummary />

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5"
        >
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400">Name</label>
            <input
              className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400">Description</label>
            <textarea
              className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400">Source URL</label>
            <input
              type="url"
              className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"
              placeholder="Optional reference for this project"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
            disabled={createProject.isPending}
          >
            {createProject.isPending ? 'Creating…' : 'Create project'}
          </button>
        </form>
      )}

      {projectsQuery.isLoading ? (
        <p className="text-sm text-slate-400">Loading projects…</p>
      ) : projectsQuery.data ? (
        <ProjectList projects={projectsQuery.data.data} />
      ) : (
        <p className="text-sm text-red-400">Failed to load projects.</p>
      )}
    </div>
  )
}
