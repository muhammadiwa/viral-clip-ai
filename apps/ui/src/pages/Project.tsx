import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../hooks/useApi'
import { useJobEvents } from '../hooks/useJobEvents'
import { useOrg } from '../contexts/OrgContext'
import { VideoIngestForm } from '../components/VideoIngestForm'
import { VideoList } from '../components/VideoList'
import { JobTable } from '../components/JobTable'
import { BrandKitManager } from '../components/BrandKitManager'
import { useNotifications } from '../contexts/NotificationContext'
import type { JobListResponse, ProjectResponse, VideoListResponse } from '../types'

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { orgId } = useOrg()
  const { request } = useApi()
  const { addNotification } = useNotifications()
  const queryClient = useQueryClient()

  const projectQuery = useQuery({
    queryKey: ['project', projectId, orgId],
    enabled: !!projectId && !!orgId,
    queryFn: () => request<ProjectResponse>(`/v1/projects/${projectId}`),
  })

  const videosQuery = useQuery({
    queryKey: ['videos', projectId],
    enabled: !!projectId && !!orgId,
    queryFn: () => request<VideoListResponse>(`/v1/projects/${projectId}/videos`),
  })

  const jobsQuery = useQuery({
    queryKey: ['jobs', projectId],
    enabled: !!projectId && !!orgId,
    queryFn: () => request<JobListResponse>(`/v1/jobs/projects/${projectId}`),
  })

  const updateBrandKitMutation = useMutation({
    mutationFn: (brandKitId: string | null) =>
      request<ProjectResponse>(`/v1/projects/${projectId}`, {
        method: 'PATCH',
        body: { brand_kit_id: brandKitId },
      }),
    onSuccess: (response, brandKitId) => {
      queryClient.setQueryData<ProjectResponse | undefined>(
        ['project', projectId, orgId],
        response,
      )
      queryClient.invalidateQueries({ queryKey: ['projects'], exact: false })
      addNotification({
        title: 'Project branding updated',
        message: brandKitId ? 'Brand kit applied to all downstream renders.' : 'Brand kit unassigned.',
        tone: 'success',
      })
    },
    onError: () => {
      addNotification({
        title: 'Unable to update branding',
        message: 'Check your permissions and try again.',
        tone: 'error',
      })
    },
  })

  if (!projectId) {
    return <p className="text-sm text-slate-400">Missing project identifier.</p>
  }

  if (!orgId) {
    return <p className="text-sm text-slate-400">Select an organization to continue.</p>
  }

  if (projectQuery.isLoading) {
    return <p className="text-sm text-slate-400">Loading project…</p>
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <p className="text-sm text-red-400">Unable to load this project.</p>
  }

  const project = projectQuery.data.data
  const videos = videosQuery.data?.data ?? []
  const jobs = jobsQuery.data?.data ?? []
  const currentBrandKitId = project.brand_kit_id ?? null

  useJobEvents(projectId, jobs)

  return (
    <div className="space-y-8">
      <header className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
        <h1 className="text-2xl font-semibold text-white">{project.name}</h1>
        {project.description && (
          <p className="mt-2 max-w-3xl text-sm text-slate-300">{project.description}</p>
        )}
        <dl className="mt-4 grid grid-cols-2 gap-4 text-xs text-slate-400 sm:grid-cols-4">
          <div>
            <dt className="uppercase tracking-wide">Status</dt>
            <dd>{project.status.replace(/_/g, ' ')}</dd>
          </div>
          <div>
            <dt className="uppercase tracking-wide">Export status</dt>
            <dd>{project.export_status.replace(/_/g, ' ')}</dd>
          </div>
          <div>
            <dt className="uppercase tracking-wide">Created</dt>
            <dd>{new Date(project.created_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="uppercase tracking-wide">Updated</dt>
            <dd>{new Date(project.updated_at).toLocaleString()}</dd>
          </div>
        </dl>
      </header>

      <BrandKitManager
        selectedBrandKitId={currentBrandKitId}
        onSelect={(nextId) => {
          if (nextId === currentBrandKitId || updateBrandKitMutation.isPending) {
            return
          }
          updateBrandKitMutation.mutate(nextId)
        }}
      />

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Video ingest</h2>
          <span className="text-sm text-slate-400">{videos.length} tracked videos</span>
        </div>
        <VideoIngestForm projectId={project.id} />
        {videosQuery.isLoading ? (
          <p className="text-sm text-slate-400">Loading videos…</p>
        ) : videosQuery.isError ? (
          <p className="text-sm text-red-400">Unable to load videos.</p>
        ) : (
          <VideoList projectId={project.id} videos={videos} />
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Pipeline jobs</h2>
          <span className="text-sm text-slate-400">{jobs.length} runs</span>
        </div>
        {jobsQuery.isLoading ? (
          <p className="text-sm text-slate-400">Loading jobs…</p>
        ) : jobsQuery.isError ? (
          <p className="text-sm text-red-400">Unable to load jobs.</p>
        ) : (
          <JobTable jobs={jobs} />
        )}
      </section>
    </div>
  )
}
