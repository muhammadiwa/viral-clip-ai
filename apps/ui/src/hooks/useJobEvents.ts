import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { API_BASE_URL } from '../lib/api'
import type { Job, JobListResponse } from '../types'
import { useOrg } from '../contexts/OrgContext'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../contexts/NotificationContext'

const TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'cancelled'])

type JobEventPayload = {
  event: 'snapshot' | 'update'
  data: Job
}

function buildWebSocketUrl(path: string, orgId: string, token: string | null) {
  const url = new URL(path, API_BASE_URL)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.searchParams.set('org_id', orgId)
  if (token) {
    url.searchParams.set('token', token)
  }
  return url.toString()
}

export function useJobEvents(projectId: string | undefined, jobs: Job[]) {
  const { orgId } = useOrg()
  const { token } = useAuth()
  const queryClient = useQueryClient()
  const socketsRef = useRef<Map<string, WebSocket>>(new Map())
  const previousStatusesRef = useRef<Map<string, string>>(new Map())
  const { addNotification } = useNotifications()

  useEffect(() => {
    const sockets = socketsRef.current
    if (!projectId || !orgId || !token) {
      for (const socket of sockets.values()) {
        socket.close()
      }
      sockets.clear()
      previousStatusesRef.current.clear()
      return
    }

    const desiredJobIds = new Set(
      jobs
        .filter((job) => !TERMINAL_STATUSES.has(job.status))
        .map((job) => job.id)
    )

    for (const [jobId, socket] of sockets) {
      if (!desiredJobIds.has(jobId)) {
        socket.close()
        sockets.delete(jobId)
        previousStatusesRef.current.delete(jobId)
      }
    }

    for (const job of jobs) {
      if (TERMINAL_STATUSES.has(job.status)) {
        continue
      }
      if (sockets.has(job.id)) {
        continue
      }
      const socket = new WebSocket(
        buildWebSocketUrl(`/v1/jobs/${job.id}/events`, orgId, token)
      )
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as JobEventPayload
          if (!payload?.data) {
            return
          }
          const previousStatus = previousStatusesRef.current.get(payload.data.id)
          if (previousStatus !== payload.data.status) {
            previousStatusesRef.current.set(payload.data.id, payload.data.status)
            if (TERMINAL_STATUSES.has(payload.data.status)) {
              const baseMessage = payload.data.message?.trim()
              const jobLabel = payload.data.job_type.replace(/_/g, ' ')
              if (payload.data.status === 'failed') {
                addNotification({
                  title: `${jobLabel} failed`,
                  message: baseMessage ?? 'Review the job activity log for details.',
                  tone: 'error',
                })
              } else if (payload.data.status === 'succeeded') {
                addNotification({
                  title: `${jobLabel} completed`,
                  message: baseMessage ?? 'Outputs are now available for review.',
                  tone: 'success',
                })
              } else if (payload.data.status === 'cancelled') {
                addNotification({
                  title: `${jobLabel} cancelled`,
                  message: baseMessage ?? 'The job will not continue processing.',
                  tone: 'warning',
                })
              }
            }
          }
          queryClient.setQueryData<JobListResponse | undefined>(
            ['jobs', projectId],
            (existing) => {
              if (!existing) {
                return existing
              }
              const jobList = existing.data
              const existingIndex = jobList.findIndex((item) => item.id === payload.data.id)
              let updatedData: Job[]
              if (existingIndex >= 0) {
                updatedData = jobList.map((item, index) =>
                  index === existingIndex ? payload.data : item
                )
              } else {
                updatedData = [payload.data, ...jobList]
              }
              return {
                ...existing,
                data: updatedData,
              }
            }
          )
        } catch (error) {
          console.error('Failed to process job event', error)
        }
      }
      socket.onerror = () => {
        socket.close()
        addNotification({
          title: 'Job stream interrupted',
          message: 'Real-time updates may be delayed. Retrying automatically.',
          tone: 'warning',
          durationMs: 4000,
        })
      }
      socket.onclose = () => {
        sockets.delete(job.id)
        previousStatusesRef.current.delete(job.id)
      }
      sockets.set(job.id, socket)
    }
  }, [jobs, orgId, token, projectId, queryClient, addNotification])

  useEffect(() => {
    return () => {
      const sockets = socketsRef.current
      for (const socket of sockets.values()) {
        socket.close()
      }
      sockets.clear()
      previousStatusesRef.current.clear()
    }
  }, [])
}
