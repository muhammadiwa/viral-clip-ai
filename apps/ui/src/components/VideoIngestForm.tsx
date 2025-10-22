import { FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../hooks/useApi'
import type { VideoIngestResponse } from '../types'

interface VideoIngestFormProps {
  projectId: string
}

export function VideoIngestForm({ projectId }: VideoIngestFormProps) {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const [sourceType, setSourceType] = useState<'upload' | 'youtube'>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [sourceUrl, setSourceUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      if (sourceType === 'upload') {
        if (!file) {
          throw new Error('Select a video file to upload')
        }
        const ingestResponse = await request<VideoIngestResponse>('/v1/videos:ingest', {
          method: 'POST',
          body: {
            project_id: projectId,
            source_type: 'upload',
          },
        })
        if (!ingestResponse.upload) {
          throw new Error('Upload credentials were not returned')
        }
        const headers = new Headers(ingestResponse.upload.headers)
        if (file.type) {
          headers.set('Content-Type', file.type)
        }
        await fetch(ingestResponse.upload.upload_url, {
          method: 'PUT',
          headers,
          body: file,
        })
        return ingestResponse
      }

      if (!sourceUrl) {
        throw new Error('Provide a valid source URL')
      }
      return request<VideoIngestResponse>('/v1/videos:ingest', {
        method: 'POST',
        body: {
          project_id: projectId,
          source_type: 'youtube',
          source_url: sourceUrl,
        },
      })
    },
    onSuccess: async () => {
      setError(null)
      setSuccess(
        sourceType === 'upload'
          ? 'Upload received. Ingest job queued.'
          : 'Remote source queued for ingest.'
      )
      setFile(null)
      setSourceUrl('')
      await queryClient.invalidateQueries({ queryKey: ['videos', projectId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs', projectId] })
    },
    onError: (err) => {
      setSuccess(null)
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Unable to queue video')
      }
    },
  })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5"
    >
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="source-type"
            value="upload"
            checked={sourceType === 'upload'}
            onChange={() => setSourceType('upload')}
          />
          Direct upload
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="source-type"
            value="youtube"
            checked={sourceType === 'youtube'}
            onChange={() => setSourceType('youtube')}
          />
          YouTube link
        </label>
      </div>

      {sourceType === 'upload' ? (
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-400">Video file</label>
          <input
            type="file"
            accept="video/*"
            className="mt-1 block w-full text-sm text-slate-200"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>
      ) : (
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-400">Source URL</label>
          <input
            type="url"
            className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"
            placeholder="https://www.youtube.com/watch?v=..."
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
          />
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}
      {success && <p className="text-sm text-emerald-400">{success}</p>}

      <button
        type="submit"
        className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
        disabled={mutation.isPending}
      >
        {mutation.isPending ? 'Queuing…' : 'Queue ingest job'}
      </button>
    </form>
  )
}
