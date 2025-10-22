import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../hooks/useApi'
import type {
  Artifact,
  ArtifactListResponse,
  Clip,
  ClipListResponse,
  Transcript,
  TranscriptListResponse,
  Video,
} from '../types'
import { ClipEditor } from './ClipEditor'
import { TranscriptEditor } from './TranscriptEditor'

interface VideoListProps {
  projectId: string
  videos: Video[]
}

const statusLabels: Record<string, string> = {
  pending_ingest: 'Pending ingest',
  ingest_queued: 'Ingest queued',
  ingesting: 'Ingesting',
  ready_for_transcode: 'Ready for transcode',
  transcode_queued: 'Transcode queued',
  transcoding: 'Transcoding',
  ready_for_transcription: 'Ready for transcription',
  transcription_queued: 'Transcription queued',
  transcribing: 'Transcribing',
  ready_for_alignment: 'Ready for alignment',
  alignment_queued: 'Alignment queued',
  aligning: 'Aligning',
  ready_for_analysis: 'Ready for analysis',
  analysis_queued: 'Clip analysis queued',
  analyzing: 'Analyzing clips',
  ready_for_clip_review: 'Ready for review',
  ingest_failed: 'Ingest failed',
  transcode_failed: 'Transcode failed',
  transcription_failed: 'Transcription failed',
  alignment_failed: 'Alignment failed',
  analysis_failed: 'Clip analysis failed',
}

export function VideoList({ projectId, videos }: VideoListProps) {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState<string | null>(null)

  const transcodeMutation = useMutation({
    mutationFn: (videoId: string) =>
      request(`/v1/videos/${videoId}:transcode`, {
        method: 'POST',
      }),
    onSuccess: async (_, videoId) => {
      await queryClient.invalidateQueries({ queryKey: ['videos', projectId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs', projectId] })
      await queryClient.invalidateQueries({ queryKey: ['clips', videoId] })
    },
  })

  const transcriptionMutation = useMutation({
    mutationFn: (videoId: string) =>
      request(`/v1/videos/${videoId}/transcripts`, {
        method: 'POST',
        body: { language_code: 'en' },
      }),
    onSuccess: async (_, videoId) => {
      await queryClient.invalidateQueries({ queryKey: ['videos', projectId] })
      await queryClient.invalidateQueries({ queryKey: ['transcripts', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs', projectId] })
    },
  })

  const clipGenerationMutation = useMutation({
    mutationFn: (videoId: string) =>
      request(`/v1/videos/${videoId}/generate-clips`, {
        method: 'POST',
        body: { max_clips: 5 },
      }),
    onSuccess: async (_, videoId) => {
      await queryClient.invalidateQueries({ queryKey: ['videos', projectId] })
      await queryClient.invalidateQueries({ queryKey: ['clips', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs', projectId] })
    },
  })

  const renderMetadata = (video: Video) => {
    const label = statusLabels[video.status] ?? video.status.replace(/_/g, ' ')
    const durationSeconds = video.duration_ms ? video.duration_ms / 1000 : null
    const durationLabel =
      durationSeconds !== null
        ? `${Math.floor(durationSeconds / 60)
            .toString()
            .padStart(2, '0')}:${Math.floor(durationSeconds % 60)
            .toString()
            .padStart(2, '0')}`
        : '—'
    const resolutionLabel =
      video.width && video.height ? `${video.width}×${video.height}` : '—'
    const frameRateLabel =
      typeof video.frame_rate === 'number' && video.frame_rate > 0
        ? `${video.frame_rate.toFixed(2)} fps`
        : '—'
    return (
      <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-400 sm:grid-cols-6">
        <div>
          <dt className="uppercase tracking-wide">Status</dt>
          <dd>{label}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide">Source</dt>
          <dd className="capitalize">{video.source_type}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide">Created</dt>
          <dd>{new Date(video.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide">Updated</dt>
          <dd>{new Date(video.updated_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide">Duration</dt>
          <dd>{durationLabel}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide">Frame &amp; Rate</dt>
          <dd>
            <span>{resolutionLabel}</span>
            <span className="ml-2 text-slate-500">{frameRateLabel}</span>
          </dd>
        </div>
      </dl>
    )
  }

  return (
    <div className="space-y-4">
      {videos.map((video) => {
        const canTranscode =
          video.status === 'ready_for_transcode' || video.status === 'transcode_failed'
        const canTranscribe =
          video.status === 'ready_for_transcription' || video.status === 'transcription_failed'
        const canGenerateClips =
          video.status === 'ready_for_analysis' || video.status === 'analysis_failed'
        const isExpanded = expanded === video.id
        const toggle = () => setExpanded((prev) => (prev === video.id ? null : video.id))

        return (
          <div key={video.id} className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-white">Video {video.id.slice(0, 8)}</h3>
                {renderMetadata(video)}
              </div>
              <div className="flex flex-col items-end gap-2 text-sm">
                {canTranscode && (
                  <button
                    type="button"
                    className="rounded-lg bg-indigo-500 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
                    disabled={transcodeMutation.isPending}
                    onClick={() => transcodeMutation.mutate(video.id)}
                  >
                    {transcodeMutation.isPending ? 'Queueing…' : 'Queue transcode'}
                  </button>
                )}
                {canTranscribe && (
                  <button
                    type="button"
                    className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-semibold text-white hover:bg-sky-400 disabled:opacity-60"
                    disabled={transcriptionMutation.isPending}
                    onClick={() => transcriptionMutation.mutate(video.id)}
                  >
                    {transcriptionMutation.isPending ? 'Queueing…' : 'Queue transcription'}
                  </button>
                )}
                {canGenerateClips && (
                  <button
                    type="button"
                    className="rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-400 disabled:opacity-60"
                    disabled={clipGenerationMutation.isPending}
                    onClick={() => clipGenerationMutation.mutate(video.id)}
                  >
                    {clipGenerationMutation.isPending ? 'Queueing…' : 'Generate clips'}
                  </button>
                )}
                <button
                  type="button"
                  className="text-xs text-slate-300 hover:text-white"
                  onClick={toggle}
                >
                  {isExpanded ? 'Hide details' : 'Show details'}
                </button>
              </div>
            </div>
            {isExpanded && <VideoDetails video={video} />}
          </div>
        )
      })}
    </div>
  )
}

function VideoDetails({ video }: { video: Video }) {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const [editingTranscriptId, setEditingTranscriptId] = useState<string | null>(null)
  const [editingClipId, setEditingClipId] = useState<string | null>(null)
  const [previewClipId, setPreviewClipId] = useState<string | null>(null)
  const videoId = video.id

  const transcriptsQuery = useQuery({
    queryKey: ['transcripts', videoId],
    queryFn: () =>
      request<TranscriptListResponse>(`/v1/videos/${videoId}/transcripts`, {
        method: 'GET',
      }),
  })

  const clipsQuery = useQuery({
    queryKey: ['clips', videoId],
    queryFn: () =>
      request<ClipListResponse>(`/v1/videos/${videoId}/clips`, {
        method: 'GET',
      }),
  })

  const artifactsQuery = useQuery({
    queryKey: ['artifacts', videoId],
    queryFn: () =>
      request<ArtifactListResponse>(`/v1/videos/${videoId}/artifacts`, {
        method: 'GET',
      }),
  })

  const alignMutation = useMutation({
    mutationFn: (transcriptId: string) =>
      request(`/v1/videos/${videoId}/transcripts/${transcriptId}:align`, {
        method: 'POST',
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['transcripts', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs'], exact: false })
    },
  })

  const styleMutation = useMutation({
    mutationFn: (clipId: string) =>
      request(`/v1/clips/${clipId}/subtitles:style`, {
        method: 'POST',
        body: {},
      }),
    onSuccess: async (_, clipId) => {
      await queryClient.invalidateQueries({ queryKey: ['clips', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['artifacts', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs'], exact: false })
    },
  })

  const ttsMutation = useMutation({
    mutationFn: (clipId: string) =>
      request(`/v1/clips/${clipId}/tts`, {
        method: 'POST',
        body: {},
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['clips', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['artifacts', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs'], exact: false })
    },
  })

  const transcripts: Transcript[] = transcriptsQuery.data?.data ?? []
  const clips: Clip[] = clipsQuery.data?.data ?? []
  const artifacts: Artifact[] = artifactsQuery.data?.data ?? []
  const videoPreview = artifacts.find((artifact) => artifact.kind === 'video_preview')

  return (
    <div className="mt-4 space-y-4 rounded-xl border border-white/5 bg-slate-950/60 p-4 text-sm">
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Media preview</h4>
        {artifactsQuery.isLoading ? (
          <p className="mt-1 text-slate-400">Loading media…</p>
        ) : videoPreview ? (
          <div className="mt-3 space-y-2 rounded-lg border border-white/5 bg-black/40 p-3">
            <video
              controls
              src={videoPreview.uri}
              className="w-full rounded-md border border-white/10"
              preload="metadata"
            />
            <p className="text-[11px] text-slate-400">
              {videoPreview.kind.replace(/_/g, ' ')} ·{' '}
              <a
                href={videoPreview.uri}
                className="text-indigo-300 hover:text-indigo-200"
                target="_blank"
                rel="noreferrer"
              >
                Open in new tab
              </a>
            </p>
          </div>
        ) : (
          <p className="mt-1 text-slate-500">No preview artifact registered yet.</p>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Transcripts</h4>
        {transcriptsQuery.isLoading ? (
          <p className="mt-1 text-slate-400">Loading transcripts…</p>
        ) : transcripts.length > 0 ? (
          <ul className="mt-2 space-y-3">
            {transcripts.map((transcript) => {
              const isEditing = editingTranscriptId === transcript.id
              const snippet = transcript.segments?.slice(0, 2).map((segment) => segment.text).join(' ')
              return (
                <li
                  key={transcript.id}
                  className="rounded-lg border border-white/5 bg-slate-900/70 p-3 text-slate-100"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-col gap-1">
                      <span className="text-sm font-semibold text-white">
                        {(transcript.language_code ?? '—').toUpperCase()} transcript
                      </span>
                      <span className="text-xs text-slate-400">
                        Status {transcript.status.replace(/_/g, ' ')} · Alignment{' '}
                        {transcript.alignment_status.replace(/_/g, ' ')}
                      </span>
                      {snippet && <p className="text-xs text-slate-300">{snippet}</p>}
                      {transcript.transcription_error && (
                        <p className="text-xs text-rose-300">{transcript.transcription_error}</p>
                      )}
                      {transcript.alignment_error && (
                        <p className="text-xs text-rose-300">Alignment error: {transcript.alignment_error}</p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2 text-xs">
                      {transcript.status === 'completed' &&
                        (transcript.alignment_status === 'not_requested' ||
                          transcript.alignment_status === 'failed') && (
                          <button
                            type="button"
                            className="rounded-md bg-slate-800 px-2 py-1 font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-60"
                            disabled={alignMutation.isPending}
                            onClick={() => alignMutation.mutate(transcript.id)}
                          >
                            {alignMutation.isPending ? 'Queuing…' : 'Align words'}
                          </button>
                        )}
                      <button
                        type="button"
                        className="rounded-md bg-indigo-500 px-3 py-1 font-semibold text-white hover:bg-indigo-400"
                        onClick={() =>
                          setEditingTranscriptId((current) =>
                            current === transcript.id ? null : transcript.id,
                          )
                        }
                      >
                        {isEditing ? 'Close editor' : 'Edit transcript'}
                      </button>
                    </div>
                  </div>
                  {isEditing && (
                    <TranscriptEditor
                      transcript={transcript}
                      videoId={videoId}
                      onClose={() => setEditingTranscriptId(null)}
                    />
                  )}
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="mt-1 text-slate-500">No transcripts yet.</p>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Clips</h4>
        {clipsQuery.isLoading ? (
          <p className="mt-1 text-slate-400">Loading clips…</p>
        ) : clips.length > 0 ? (
          <ul className="mt-2 space-y-3">
            {clips.map((clip) => {
              const isEditing = editingClipId === clip.id
              const isPreviewing = previewClipId === clip.id
              const clipArtifacts = artifacts.filter((artifact) => artifact.clip_id === clip.id)
              const clipPreview = clipArtifacts.find((artifact) => artifact.kind === 'clip_preview')
              const clipAudio = clipArtifacts.find((artifact) => artifact.kind === 'clip_audio')
              const subtitleArtifact = clipArtifacts.find((artifact) => artifact.kind === 'clip_subtitle')
              return (
                <li
                  key={clip.id}
                  className="rounded-lg border border-white/5 bg-slate-900/70 p-3 text-slate-100"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex flex-col gap-1">
                      <span className="text-sm font-semibold text-white">
                        {clip.title?.trim() || `Clip ${clip.id.slice(0, 6)}`}
                      </span>
                      <span className="text-xs text-slate-400">
                        {formatMillis(clip.start_ms)} – {formatMillis(clip.end_ms)} · confidence{' '}
                        {clip.confidence != null ? `${Math.round(clip.confidence * 100)}%` : '—'}
                      </span>
                      <span className="text-xs text-slate-400">
                        Style {clip.style_status.replace(/_/g, ' ')} · Voice {clip.voice_status.replace(/_/g, ' ')}
                      </span>
                      {clip.style_error && <p className="text-xs text-rose-300">Style error: {clip.style_error}</p>}
                      {clip.voice_error && <p className="text-xs text-rose-300">Voice error: {clip.voice_error}</p>}
                      {subtitleArtifact && (
                        <a
                          href={subtitleArtifact.uri}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-indigo-300 hover:text-indigo-200"
                        >
                          Download subtitles
                        </a>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2 text-xs">
                      {(clip.style_status === 'not_styled' || clip.style_status === 'style_failed') && (
                        <button
                          type="button"
                          className="rounded-md bg-slate-800 px-2 py-1 font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-60"
                          disabled={styleMutation.isPending}
                          onClick={() => styleMutation.mutate(clip.id)}
                        >
                          {styleMutation.isPending ? 'Queuing…' : 'Style subtitles'}
                        </button>
                      )}
                      {(clip.voice_status === 'not_requested' || clip.voice_status === 'voice_failed') && (
                        <button
                          type="button"
                          className="rounded-md bg-slate-800 px-2 py-1 font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-60"
                          disabled={ttsMutation.isPending}
                          onClick={() => ttsMutation.mutate(clip.id)}
                        >
                          {ttsMutation.isPending ? 'Queuing…' : 'Synthesize voice'}
                        </button>
                      )}
                      {clipPreview && (
                        <button
                          type="button"
                          className="rounded-md bg-indigo-500 px-3 py-1 font-semibold text-white hover:bg-indigo-400"
                          onClick={() =>
                            setPreviewClipId((current) =>
                              current === clip.id ? null : clip.id,
                            )
                          }
                        >
                          {isPreviewing ? 'Hide preview' : 'Preview clip'}
                        </button>
                      )}
                      <button
                        type="button"
                        className="rounded-md bg-emerald-500 px-3 py-1 font-semibold text-white hover:bg-emerald-400"
                        onClick={() =>
                          setEditingClipId((current) => (current === clip.id ? null : clip.id))
                        }
                      >
                        {isEditing ? 'Close editor' : 'Edit clip'}
                      </button>
                    </div>
                  </div>

                  {isPreviewing && (
                    <div className="mt-3 space-y-2 rounded-lg border border-white/5 bg-black/40 p-3">
                      {clipPreview && (
                        <video
                          controls
                          src={clipPreview.uri}
                          className="w-full rounded-md border border-white/10"
                          preload="metadata"
                        />
                      )}
                      {clipAudio && (
                        <audio controls className="w-full">
                          <source src={clipAudio.uri} type={clipAudio.content_type ?? 'audio/mpeg'} />
                          Your browser does not support the audio element.
                        </audio>
                      )}
                    </div>
                  )}

                  {isEditing && (
                    <ClipEditor
                      clip={clip}
                      transcripts={transcripts}
                      videoDurationMs={video.duration_ms ?? null}
                      previewUri={clipPreview?.uri ?? videoPreview?.uri ?? null}
                      artifacts={clipArtifacts}
                      onClose={() => setEditingClipId(null)}
                    />
                  )}
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="mt-1 text-slate-500">No clips generated yet.</p>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Artifacts</h4>
        {artifactsQuery.isLoading ? (
          <p className="mt-1 text-slate-400">Loading artifacts…</p>
        ) : artifacts.length > 0 ? (
          <ul className="mt-2 space-y-2">
            {artifacts.map((artifact) => (
              <li
                key={artifact.id}
                className="flex items-center justify-between rounded-lg border border-white/5 bg-slate-900/70 px-3 py-2"
              >
                <div className="flex flex-col gap-1">
                  <span>{artifact.kind.replace(/_/g, ' ')}</span>
                  <span className="text-xs text-slate-400">{artifact.content_type ?? 'Unknown type'}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span>{artifact.size_bytes ? Math.round(artifact.size_bytes / (1024 * 1024)) : 0} MB</span>
                  <a
                    href={artifact.uri}
                    target="_blank"
                    rel="noreferrer"
                    className="text-indigo-300 hover:text-indigo-200"
                  >
                    Open
                  </a>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-slate-500">No artifacts registered yet.</p>
        )}
      </section>
    </div>
  )
}

function formatMillis(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}
