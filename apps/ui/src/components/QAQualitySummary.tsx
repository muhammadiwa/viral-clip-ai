import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'

import { useApi } from '../hooks/useApi'
import { useNotifications } from '../contexts/NotificationContext'
import type {
  MetricSummaryResponse,
  QAFindingResponse,
  QARunListResponse,
  QARunResponse,
  QAReviewResponse,
  MembershipListResponse,
  UserListResponse,
  User,
  Membership,
} from '../types'
import { useAuth } from '../contexts/AuthContext'

const METRIC_NAMES = [
  'qa.clip.pass_rate',
  'qa.subtitle.pass_rate',
  'qa.mix.pass_rate',
  'qa.watermark.pass_rate',
  'qa.total.failure_count',
]

const FINDING_STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'ready_for_review', label: 'Ready for review' },
  { value: 'resolved', label: 'Resolved' },
] as const

type FindingStatus = (typeof FINDING_STATUS_OPTIONS)[number]['value']

const REVIEW_STATUS_OPTIONS = [
  { value: 'approved', label: 'Approved' },
  { value: 'changes_required', label: 'Changes required' },
] as const

function formatPercent(value?: number | null) {
  if (value === undefined || value === null) {
    return '—'
  }
  return `${Math.round(value * 100)}%`
}

function formatDateTime(value?: string) {
  if (!value) return 'Unknown'
  try {
    return new Date(value).toLocaleString()
  } catch (error) {
    return value
  }
}

function toDateTimeLocalInput(value?: string | null) {
  if (!value) {
    return ''
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return ''
  }
  const offset = parsed.getTimezoneOffset()
  const adjusted = new Date(parsed.getTime() - offset * 60000)
  return adjusted.toISOString().slice(0, 16)
}

function formatOverlayValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—'
  }
  if (Array.isArray(value)) {
    return value.map((entry) => formatOverlayValue(entry)).join(', ')
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch (error) {
      return String(value)
    }
  }
  if (typeof value === 'number') {
    return value.toLocaleString()
  }
  return String(value)
}

export function QAQualitySummary() {
  const { request } = useApi()
  const { addNotification } = useNotifications()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [reviewStatus, setReviewStatus] = useState<'approved' | 'changes_required'>('approved')
  const [reviewNotes, setReviewNotes] = useState('')
  const [findingNotes, setFindingNotes] = useState<Record<string, string>>({})
  const [assignmentDrafts, setAssignmentDrafts] = useState<Record<string, string | null>>({})
  const [dueDateDrafts, setDueDateDrafts] = useState<Record<string, string | null>>({})

  const metricQueries = useQueries({
    queries: METRIC_NAMES.map((name) => ({
      queryKey: ['qa-metric-summary', name],
      staleTime: 30_000,
      queryFn: () =>
        request<MetricSummaryResponse>(
          `/v1/observability/metrics/summary?name=${encodeURIComponent(name)}`
        ),
    })),
  })

  const qaRunsQuery = useQuery({
    queryKey: ['qa-runs'],
    staleTime: 30_000,
    queryFn: () =>
      request<QARunListResponse>(
        '/v1/observability/qa-runs?limit=5&offset=0'
      ),
  })

  const runDetailQuery = useQuery({
    queryKey: ['qa-run', selectedRunId],
    enabled: !!selectedRunId,
    queryFn: () => request<QARunResponse>(`/v1/observability/qa-runs/${selectedRunId}`),
    staleTime: 10_000,
  })

  const membersQuery = useQuery({
    queryKey: ['org-members'],
    staleTime: 30_000,
    queryFn: () =>
      request<MembershipListResponse>(
        `/v1/users?limit=200&offset=0`,
      ),
  })

  const usersQuery = useQuery({
    queryKey: ['users'],
    staleTime: 60_000,
    queryFn: () => request<UserListResponse>('/v1/users?limit=200&offset=0'),
  })

  const latestRun = qaRunsQuery.data?.data?.[0]

  const members = membersQuery.data?.data ?? []
  const users = usersQuery.data?.data ?? []

  const usersById = useMemo(() => {
    const map: Record<string, User> = {}
    for (const entry of users) {
      map[entry.id] = entry
    }
    return map
  }, [users])

  const activeMembers = useMemo(
    () => members.filter((member: Membership) => member.status === 'active'),
    [members],
  )

  const memberOptions = useMemo(
    () =>
      activeMembers.map((member: Membership) => {
        const userRecord = usersById[member.user_id]
        const label = userRecord?.full_name || userRecord?.email || member.user_id
        return {
          value: member.user_id,
          label,
        }
      }),
    [activeMembers, usersById],
  )

  const canSelfAssign = useMemo(
    () => !!user && activeMembers.some((member: Membership) => member.user_id === user.id),
    [activeMembers, user],
  )

  const metricsByName = useMemo(() => {
    const result: Record<string, number | null | undefined> = {}
    for (let index = 0; index < metricQueries.length; index++) {
      const query = metricQueries[index]
      const name = METRIC_NAMES[index]
      if (query.data) {
        result[name] = query.data.data.average ?? query.data.data.p50
      } else if (query.isError) {
        result[name] = null
      }
    }
    return result
  }, [metricQueries])

  const isLoading =
    metricQueries.some((query) => query.isLoading) ||
    qaRunsQuery.isLoading ||
    membersQuery.isLoading ||
    usersQuery.isLoading
  const hasError =
    metricQueries.some((query) => query.isError) ||
    qaRunsQuery.isError ||
    membersQuery.isError ||
    usersQuery.isError

  useEffect(() => {
    const runs = qaRunsQuery.data?.data ?? []
    if (!selectedRunId && runs.length > 0) {
      setSelectedRunId(runs[0].id)
    }
  }, [qaRunsQuery.data, selectedRunId])

  const updateFindingMutation = useMutation({
    mutationFn: ({
      findingId,
      status,
      notes,
      assigneeId,
      dueDate,
    }: {
      findingId: string
      status:
        | 'open'
        | 'acknowledged'
        | 'in_progress'
        | 'blocked'
        | 'ready_for_review'
        | 'resolved'
      notes: string
      assigneeId?: string | null
      dueDate?: string | null
    }) => {
      const body: Record<string, unknown> = {
        status,
        notes: notes.trim() || null,
      }
      if (assigneeId !== undefined) {
        body.assignee_id = assigneeId
      }
      if (dueDate !== undefined) {
        body.due_date = dueDate
      }
      return request<QAFindingResponse>(
        `/v1/observability/qa-runs/${selectedRunId}/findings/${findingId}`,
        {
          method: 'PATCH',
          body,
        },
      )
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['qa-run', selectedRunId] })
      queryClient.invalidateQueries({ queryKey: ['qa-runs'] })
      addNotification({
        title: 'Finding updated',
        message: 'Status saved for this regression finding.',
        tone: 'success',
      })
    },
    onError: () => {
      addNotification({
        title: 'Unable to update finding',
        message: 'Try again or refresh the page to reload the QA run.',
        tone: 'error',
      })
    },
  })

  const createReviewMutation = useMutation({
    mutationFn: () =>
      request<QAReviewResponse>(`/v1/observability/qa-runs/${selectedRunId}/reviews`, {
        method: 'POST',
        body: {
          status: reviewStatus,
          notes: reviewNotes.trim() || null,
          reference_artifact_ids: [],
        },
      }),
    onSuccess: () => {
      setReviewNotes('')
      queryClient.invalidateQueries({ queryKey: ['qa-run', selectedRunId] })
      queryClient.invalidateQueries({ queryKey: ['qa-runs'] })
      addNotification({
        title: 'QA review recorded',
        message: 'Creative approval has been captured for this run.',
        tone: 'success',
      })
    },
    onError: () => {
      addNotification({
        title: 'Review submission failed',
        message: 'Confirm your session is active and try again.',
        tone: 'error',
      })
    },
  })

  const runDetail = runDetailQuery.data?.data
  const selectedRun = (qaRunsQuery.data?.data ?? []).find((run) => run.id === selectedRunId)
  const findings = runDetail?.findings ?? []
  const reviews = runDetail?.reviews ?? []
  const localeCoverage = useMemo(
    () => Object.entries(latestRun?.locale_coverage ?? {}).sort((a, b) => b[1] - a[1]),
    [latestRun],
  )
  const genreCoverage = useMemo(
    () => Object.entries(latestRun?.genre_coverage ?? {}).sort((a, b) => b[1] - a[1]),
    [latestRun],
  )

  useEffect(() => {
    if (!runDetail) {
      setAssignmentDrafts({})
      return
    }
    const next: Record<string, string | null> = {}
    for (const finding of runDetail.findings) {
      next[finding.id] = finding.assignee_id ?? null
    }
    setAssignmentDrafts(next)
  }, [runDetail])

  const assignmentLoading = membersQuery.isLoading || usersQuery.isLoading

  return (
    <section className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Quality assurance</h2>
          <p className="text-sm text-slate-400">
            Regression coverage across clip scoring, subtitles, mixes, and
            watermark templates.
          </p>
        </div>
        {latestRun && (
          <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
            Dataset: {latestRun.dataset_name}
            {latestRun.dataset_version ? ` · v${latestRun.dataset_version}` : ''}
          </span>
        )}
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-slate-400">Loading QA coverage…</p>
      ) : hasError ? (
        <p className="mt-4 text-sm text-red-400">
          Unable to load QA metrics. Confirm the observability service is
          reachable.
        </p>
      ) : (
        <div className="mt-4 space-y-6">
          <div className="grid gap-4 md:grid-cols-5">
            <MetricCard
              title="Clip pass rate"
              value={formatPercent(metricsByName['qa.clip.pass_rate'])}
              helper="Passing clips / total"
            />
            <MetricCard
              title="Subtitle pass rate"
              value={formatPercent(metricsByName['qa.subtitle.pass_rate'])}
              helper="Brand + language checks"
            />
            <MetricCard
              title="Mix pass rate"
              value={formatPercent(metricsByName['qa.mix.pass_rate'])}
              helper="Loudness & gain targets"
            />
            <MetricCard
              title="Watermark pass rate"
              value={formatPercent(metricsByName['qa.watermark.pass_rate'])}
              helper="Template safe zones"
            />
            <MetricCard
              title="Open issues"
              value={(() => {
                const failures = metricsByName['qa.total.failure_count']
                if (failures === undefined || failures === null) return '—'
                return failures.toFixed(0)
              })()}
              helper="Total failing assertions"
            />
          </div>

          {latestRun ? (
            <div className="space-y-4 rounded-xl border border-white/10 bg-slate-950/60 p-4">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Summary • {formatDateTime(latestRun.recorded_at)}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Clips failing: {latestRun.clip_failures} / {latestRun.clip_cases} • Subtitles failing:{' '}
                    {latestRun.subtitle_failures} / {latestRun.subtitle_cases} • Mixes failing: {latestRun.mix_failures} /{' '}
                    {latestRun.mix_cases} • Watermarks failing: {latestRun.watermark_failures} /{' '}
                    {latestRun.watermark_cases}
                  </p>
                </div>
                <label className="flex flex-col text-xs text-slate-300">
                  <span className="font-semibold uppercase tracking-wide text-slate-400">Inspect run</span>
                  <select
                    className="mt-1 rounded-md border border-white/10 bg-slate-950 px-2 py-1"
                    value={selectedRunId ?? ''}
                    onChange={(event) => setSelectedRunId(event.target.value || null)}
                  >
                    {(qaRunsQuery.data?.data ?? []).map((run) => (
                      <option key={run.id} value={run.id}>
                        {formatDateTime(run.recorded_at)} • {run.dataset_name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {selectedRun ? (
                <div className="space-y-3 text-xs text-slate-300">
                  <p>
                    Dataset <span className="font-semibold text-white">{selectedRun.dataset_name}</span> · Clips failing{' '}
                    {selectedRun.clip_failures} / {selectedRun.clip_cases} · Subtitles failing {selectedRun.subtitle_failures} /
                    {selectedRun.subtitle_cases}
                  </p>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">
                    {selectedRun.dataset_version ? `Version ${selectedRun.dataset_version} · ` : ''}Frame diff failures{' '}
                    {selectedRun.frame_diff_failures}
                  </p>
                  {(localeCoverage.length > 0 || genreCoverage.length > 0) && (
                    <div className="grid gap-3 md:grid-cols-2">
                      {localeCoverage.length > 0 && (
                        <div className="rounded-lg bg-slate-900/70 p-3">
                          <p className="text-[11px] uppercase tracking-wide text-slate-400">Locale coverage</p>
                          <ul className="mt-2 space-y-1">
                            {localeCoverage.slice(0, 5).map(([locale, count]) => (
                              <li key={locale} className="flex items-center justify-between text-slate-200">
                                <span>{locale}</span>
                                <span>{count}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {genreCoverage.length > 0 && (
                        <div className="rounded-lg bg-slate-900/70 p-3">
                          <p className="text-[11px] uppercase tracking-wide text-slate-400">Genre coverage</p>
                          <ul className="mt-2 space-y-1">
                            {genreCoverage.slice(0, 5).map(([genre, count]) => (
                              <li key={genre} className="flex items-center justify-between text-slate-200">
                                <span>{genre}</span>
                                <span>{count}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                  {selectedRun.failure_details.length > 0 ? (
                    <ul className="space-y-2 text-rose-200">
                      {selectedRun.failure_details.slice(0, 6).map((failure) => (
                        <li key={failure} className="rounded bg-rose-500/10 px-3 py-2">
                          {failure}
                        </li>
                      ))}
                      {selectedRun.failure_details.length > 6 && (
                        <li className="text-[11px] uppercase tracking-wide text-rose-300/70">
                          +{selectedRun.failure_details.length - 6} additional issues
                        </li>
                      )}
                    </ul>
                  ) : (
                    <p className="text-xs text-emerald-300">No failures recorded. Creative checks can proceed.</p>
                  )}
                  {selectedRun.failure_artifact_ids.length > 0 && (
                    <div className="rounded-lg bg-slate-900/60 p-3">
                      <p className="text-[11px] uppercase tracking-wide text-slate-400">Reference artifact IDs</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {selectedRun.failure_artifact_ids.map((artifactId) => (
                          <code
                            key={artifactId}
                            className="rounded bg-slate-800 px-2 py-1 text-[11px] text-indigo-200"
                          >
                            {artifactId}
                          </code>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}

              <div className="space-y-4">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Findings</h4>
                {runDetailQuery.isLoading ? (
                  <p className="text-xs text-slate-400">Loading findings…</p>
                ) : findings.length > 0 ? (
                  <ul className="space-y-3">
                    {findings.map((finding) => {
                      const currentAssigneeId =
                        assignmentDrafts[finding.id] ?? finding.assignee_id ?? null
                      const assigneeUser = currentAssigneeId
                        ? usersById[currentAssigneeId]
                        : undefined
                      const assigneeLabel =
                        finding.assignee_name ||
                        assigneeUser?.full_name ||
                        assigneeUser?.email ||
                        (currentAssigneeId ? 'Pending member assignment' : 'Unassigned')
                      const hasDueDateDraft = finding.id in dueDateDrafts
                      const dueDateInput = hasDueDateDraft
                        ? dueDateDrafts[finding.id] ?? ''
                        : toDateTimeLocalInput(finding.due_date ?? null)
                      const dueDateIso = dueDateInput
                        ? new Date(dueDateInput).toISOString()
                        : null
                      const dueDateLabel = finding.due_date
                        ? formatDateTime(finding.due_date)
                        : 'Unscheduled'
                      const overlayEntries = Object.entries(finding.overlay_metadata ?? {})

                      return (
                        <li
                          key={finding.id}
                          className="space-y-2 rounded-lg border border-white/10 bg-slate-900/70 p-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3 text-xs text-slate-200">
                            <div className="space-y-1">
                              <p className="text-sm font-semibold text-white">{finding.case_name}</p>
                              <p className="text-slate-300">{finding.message}</p>
                              <p className="text-[11px] uppercase tracking-wide text-slate-500">
                                Category • {finding.category}
                              </p>
                              <p className="text-[11px] text-slate-400">
                                Assigned to {assigneeLabel}
                                {finding.assigned_at
                                  ? ` • ${formatDateTime(finding.assigned_at)}`
                                  : ''}
                              </p>
                              <p className="text-[11px] text-slate-400">
                                Due date • {dueDateLabel}
                              </p>
                            </div>
                            <div className="flex flex-col gap-2 text-[11px] text-slate-300">
                              <label className="flex flex-col">
                                <span className="font-semibold uppercase tracking-wide text-slate-400">
                                  Status
                                </span>
                                <select
                                  value={finding.status}
                                  onChange={(event) => {
                                    const newStatus = event.target.value as FindingStatus
                                    updateFindingMutation.mutate({
                                      findingId: finding.id,
                                      status: newStatus,
                                      notes: findingNotes[finding.id] ?? finding.notes ?? '',
                                      assigneeId: currentAssigneeId,
                                      dueDate: dueDateIso,
                                    })
                                  }}
                                  className="rounded-md border border-white/10 bg-slate-950 px-2 py-1"
                                >
                                  {FINDING_STATUS_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label className="flex flex-col">
                                <span className="font-semibold uppercase tracking-wide text-slate-400">
                                  Assignee
                                </span>
                                <select
                                  value={currentAssigneeId ?? ''}
                                  onChange={(event) => {
                                    const value = event.target.value
                                    setAssignmentDrafts((current) => ({
                                      ...current,
                                      [finding.id]: value || null,
                                    }))
                                    updateFindingMutation.mutate({
                                      findingId: finding.id,
                                      status: finding.status,
                                      notes: findingNotes[finding.id] ?? finding.notes ?? '',
                                      assigneeId: value || null,
                                      dueDate: dueDateIso,
                                    })
                                  }}
                                  className="rounded-md border border-white/10 bg-slate-950 px-2 py-1"
                                  disabled={assignmentLoading}
                                >
                                  <option value="">Unassigned</option>
                                  {memberOptions.map((option: { value: string; label: string }) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <button
                                type="button"
                                className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-800 disabled:opacity-40"
                                onClick={() =>
                                  user &&
                                  canSelfAssign &&
                                  (setAssignmentDrafts((current) => ({
                                    ...current,
                                    [finding.id]: user.id,
                                  })),
                                  updateFindingMutation.mutate({
                                    findingId: finding.id,
                                    status: finding.status,
                                    notes: findingNotes[finding.id] ?? finding.notes ?? '',
                                    assigneeId: user.id,
                                    dueDate: dueDateIso,
                                  }))
                                }
                                disabled={!canSelfAssign || assignmentLoading || !user}
                              >
                                Assign to me
                              </button>
                              <label className="flex flex-col">
                                <span className="font-semibold uppercase tracking-wide text-slate-400">
                                  Due date
                                </span>
                                <div className="flex items-center gap-2">
                                  <input
                                    type="datetime-local"
                                    value={dueDateInput}
                                    onChange={(event) => {
                                      const rawValue = event.target.value
                                      const value = rawValue === '' ? '' : rawValue
                                      setDueDateDrafts((current) => ({
                                        ...current,
                                        [finding.id]: value,
                                      }))
                                      updateFindingMutation.mutate({
                                        findingId: finding.id,
                                        status: finding.status,
                                        notes: findingNotes[finding.id] ?? finding.notes ?? '',
                                        assigneeId: currentAssigneeId,
                                        dueDate:
                                          value === '' ? null : new Date(value).toISOString(),
                                      })
                                    }}
                                    className="w-full rounded-md border border-white/10 bg-slate-950 px-2 py-1"
                                  />
                                  <button
                                    type="button"
                                    className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-800 disabled:opacity-40"
                                    onClick={() => {
                                      setDueDateDrafts((current) => ({
                                        ...current,
                                        [finding.id]: '',
                                      }))
                                      updateFindingMutation.mutate({
                                        findingId: finding.id,
                                        status: finding.status,
                                        notes: findingNotes[finding.id] ?? finding.notes ?? '',
                                        assigneeId: currentAssigneeId,
                                        dueDate: null,
                                      })
                                    }}
                                    disabled={!finding.due_date && dueDateIso === null && !hasDueDateDraft}
                                  >
                                    Clear
                                  </button>
                                </div>
                              </label>
                            </div>
                          </div>
                          <div className="space-y-2 text-xs text-slate-300">
                            {finding.reference_urls.length > 0 && (
                              <div className="flex flex-wrap gap-2">
                                {finding.reference_urls.map((url) => (
                                  <a
                                    key={url}
                                    href={url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="rounded bg-slate-800 px-2 py-1 text-[11px] text-indigo-200 hover:bg-slate-700"
                                  >
                                    Reference
                                  </a>
                                ))}
                              </div>
                            )}
                            {finding.reference_artifact_ids.length > 0 && (
                              <div className="flex flex-wrap gap-2">
                                {finding.reference_artifact_ids.map((artifactId) => (
                                  <code
                                    key={artifactId}
                                    className="rounded bg-slate-800 px-2 py-1 text-[11px] text-indigo-200"
                                  >
                                    {artifactId}
                                  </code>
                                ))}
                              </div>
                            )}
                            {(finding.overlay_url || overlayEntries.length > 0) && (
                              <div className="space-y-1 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-amber-100">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-300">
                                  Overlay guidance
                                </p>
                                {finding.overlay_url && (
                                  <a
                                    href={finding.overlay_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-200 hover:text-amber-100"
                                  >
                                    View overlay reference
                                  </a>
                                )}
                                {overlayEntries.length > 0 && (
                                  <ul className="space-y-1 text-[11px]">
                                    {overlayEntries.map(([key, value]) => (
                                      <li key={key}>
                                        <span className="font-semibold text-amber-200">{key}:</span>{' '}
                                        {formatOverlayValue(value)}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            )}
                            <label className="flex flex-col gap-1 text-[11px] text-slate-300">
                              <span className="font-semibold uppercase tracking-wide text-slate-400">
                                Reviewer notes
                              </span>
                              <textarea
                                className="rounded-md border border-white/10 bg-slate-950 px-2 py-2 text-xs"
                                placeholder="Add resolution details or next steps"
                                value={findingNotes[finding.id] ?? finding.notes ?? ''}
                                onChange={(event) =>
                                  setFindingNotes((current) => ({
                                    ...current,
                                    [finding.id]: event.target.value,
                                  }))
                                }
                              />
                            </label>
                            <button
                              type="button"
                              className="rounded-md bg-emerald-500 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-400 disabled:opacity-60"
                              onClick={() =>
                                updateFindingMutation.mutate({
                                  findingId: finding.id,
                                  status: finding.status,
                                  notes: findingNotes[finding.id] ?? finding.notes ?? '',
                                  assigneeId: currentAssigneeId,
                                })
                              }
                              disabled={updateFindingMutation.isPending}
                            >
                              Save notes
                            </button>
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-400">No findings recorded for this run.</p>
                )}
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Creative review</h4>
                {reviews.length > 0 ? (
                  <ul className="space-y-2 text-xs text-slate-300">
                    {reviews.map((review) => (
                      <li key={review.id} className="rounded-lg border border-white/10 bg-slate-900/70 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-semibold text-white">{review.status.replace(/_/g, ' ')}</span>
                          <span className="text-[11px] text-slate-500">
                            {formatDateTime(review.created_at)}
                          </span>
                        </div>
                        {review.notes && <p className="mt-1 text-slate-300">{review.notes}</p>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-400">No creative review has been submitted yet.</p>
                )}
                <form
                  className="space-y-2 rounded-lg border border-dashed border-white/10 bg-slate-950/40 p-3 text-xs text-slate-200"
                  onSubmit={(event) => {
                    event.preventDefault()
                    createReviewMutation.mutate()
                  }}
                >
                  <label className="flex flex-col gap-1">
                    <span className="font-semibold uppercase tracking-wide text-slate-400">Approval status</span>
                    <select
                      value={reviewStatus}
                      onChange={(event) =>
                        setReviewStatus(event.target.value as 'approved' | 'changes_required')
                      }
                      className="rounded-md border border-white/10 bg-slate-950 px-2 py-1"
                    >
                      {REVIEW_STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="font-semibold uppercase tracking-wide text-slate-400">Notes</span>
                    <textarea
                      value={reviewNotes}
                      onChange={(event) => setReviewNotes(event.target.value)}
                      className="rounded-md border border-white/10 bg-slate-950 px-2 py-2"
                      placeholder="Summarize approval decision or requested adjustments"
                    />
                  </label>
                  <button
                    type="submit"
                    className="rounded-md bg-indigo-500 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
                    disabled={createReviewMutation.isPending || !selectedRunId}
                  >
                    {createReviewMutation.isPending ? 'Submitting…' : 'Submit review'}
                  </button>
                </form>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-400">
              No QA runs have been reported for this organization yet.
            </p>
          )}
        </div>
      )}
    </section>
  )
}

interface MetricCardProps {
  title: string
  value: string
  helper: string
}

function MetricCard({ title, value, helper }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-white/5 bg-slate-950/60 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{helper}</p>
    </div>
  )
}
