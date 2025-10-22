import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { useApi } from '../hooks/useApi'
import { useNotifications } from '../contexts/NotificationContext'
import type { Artifact, Clip, Transcript } from '../types'

interface ClipEditorProps {
  clip: Clip
  transcripts: Transcript[]
  videoDurationMs?: number | null
  previewUri?: string | null
  artifacts: Artifact[]
  onClose: () => void
}

interface TimelineSegment {
  id: string
  startMs: number
  endMs: number
  amplitude: number
  text: string
}

function formatSeconds(seconds: number) {
  const absolute = Math.max(0, seconds)
  const wholeSeconds = Math.floor(absolute)
  const minutes = Math.floor(wholeSeconds / 60)
  const remainingSeconds = wholeSeconds % 60
  const fractional = absolute - wholeSeconds
  const paddedSeconds = remainingSeconds.toString().padStart(2, '0')
  if (fractional > 0) {
    return `${minutes}:${paddedSeconds}.${Math.round(fractional * 100)}`
  }
  return `${minutes}:${paddedSeconds}`
}

export function ClipEditor({
  clip,
  transcripts,
  videoDurationMs,
  previewUri,
  artifacts,
  onClose,
}: ClipEditorProps) {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const { addNotification } = useNotifications()
  const previewRef = useRef<HTMLVideoElement | null>(null)
  const [title, setTitle] = useState(clip.title ?? '')
  const [description, setDescription] = useState(clip.description ?? '')
  const [activeHandle, setActiveHandle] = useState<'start' | 'end'>('start')
  const [error, setError] = useState<string | null>(null)
  const [startMs, setStartMs] = useState(clip.start_ms)
  const [endMs, setEndMs] = useState(clip.end_ms)
  const [editableSegments, setEditableSegments] = useState<TimelineSegment[]>([])
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null)

  useEffect(() => {
    setTitle(clip.title ?? '')
    setDescription(clip.description ?? '')
    setStartMs(clip.start_ms)
    setEndMs(clip.end_ms)
    setError(null)
  }, [clip])

  const selectedTranscript = useMemo(() => {
    if (transcripts.length === 0) {
      return null
    }
    const aligned = transcripts.find((candidate) => candidate.alignment_status === 'completed')
    return aligned ?? transcripts[0]
  }, [transcripts])

  const transcriptSegments = useMemo(() => {
    if (!selectedTranscript) {
      return []
    }
    if (selectedTranscript.aligned_segments && selectedTranscript.aligned_segments.length > 0) {
      return selectedTranscript.aligned_segments
    }
    return selectedTranscript.segments ?? []
  }, [selectedTranscript])

  const totalDurationMs = useMemo(() => {
    if (typeof videoDurationMs === 'number' && videoDurationMs > 0) {
      return videoDurationMs
    }
    const longestSegment = transcriptSegments.reduce(
      (max, segment) => Math.max(max, segment.end_ms),
      0,
    )
    return Math.max(longestSegment, clip.end_ms)
  }, [videoDurationMs, transcriptSegments, clip.end_ms])

  const timelineSegments = useMemo<TimelineSegment[]>(() => {
    if (transcriptSegments.length === 0) {
      return [
        {
          id: `${clip.id}-fallback`,
          startMs: 0,
          endMs: totalDurationMs,
          amplitude: 0.3,
          text: 'No transcript available — adjust timings manually.',
        },
      ]
    }
    return transcriptSegments.map((segment, index) => {
      const words = segment.words?.length ?? segment.text.split(/\s+/).length
      const amplitude = Math.min(1, Math.max(0.1, words / 12))
      return {
        id: `${segment.start_ms}-${segment.end_ms}-${index}`,
        startMs: segment.start_ms,
        endMs: segment.end_ms,
        amplitude,
        text: segment.text,
      }
    })
  }, [transcriptSegments, clip.id, totalDurationMs])

  const timelineSeed = useMemo(
    () => timelineSegments.map((segment) => `${segment.startMs}:${segment.endMs}`).join('|'),
    [timelineSegments],
  )

  useEffect(() => {
    setEditableSegments(timelineSegments)
    setSelectedSegmentId(timelineSegments[0]?.id ?? null)
  }, [clip.id, timelineSeed])

  const clampStart = (value: number) => Math.min(Math.max(0, value), endMs - 200)
  const clampEnd = (value: number) => Math.max(Math.min(totalDurationMs, value), startMs + 200)

  const setStartFromSeconds = (seconds: number) => {
    const next = clampStart(Math.round(seconds * 1000))
    setStartMs(next)
  }

  const setEndFromSeconds = (seconds: number) => {
    const next = clampEnd(Math.round(seconds * 1000))
    setEndMs(next)
  }

  const handleTimelineClick = (segment: TimelineSegment) => {
    setSelectedSegmentId(segment.id)
    if (activeHandle === 'start') {
      setStartMs(clampStart(segment.startMs))
    } else {
      setEndMs(clampEnd(segment.endMs))
    }
    if (previewRef.current) {
      previewRef.current.currentTime =
        (activeHandle === 'start' ? clampStart(segment.startMs) : clampEnd(segment.endMs)) / 1000
    }
  }

  const MIN_SEGMENT_DURATION = 400

  const segmentsToRender = editableSegments.length > 0 ? editableSegments : timelineSegments

  const handleSplitSegment = (segmentId: string) => {
    setEditableSegments((segments) => {
      const index = segments.findIndex((segment) => segment.id === segmentId)
      if (index === -1) {
        return segments
      }
      const segment = segments[index]
      const duration = segment.endMs - segment.startMs
      if (duration <= MIN_SEGMENT_DURATION * 2) {
        addNotification({
          title: 'Segment too short',
          message: 'Zoom in with the sliders for finer trims.',
          tone: 'warning',
        })
        return segments
      }
      const midpoint = Math.round((segment.startMs + segment.endMs) / 2)
      const left: TimelineSegment = {
        ...segment,
        id: `${segment.id}-left-${midpoint}`,
        endMs: midpoint,
      }
      const right: TimelineSegment = {
        ...segment,
        id: `${segment.id}-right-${midpoint}`,
        startMs: midpoint,
      }
      const nextSegments = [
        ...segments.slice(0, index),
        left,
        right,
        ...segments.slice(index + 1),
      ]
      setSelectedSegmentId(left.id)
      return nextSegments
    })
  }

  const handleMergeSegment = (segmentId: string) => {
    setEditableSegments((segments) => {
      const index = segments.findIndex((segment) => segment.id === segmentId)
      if (index === -1 || index === segments.length - 1) {
        addNotification({
          title: 'Nothing to merge',
          message: 'Select a segment with a successor to merge.',
          tone: 'warning',
        })
        return segments
      }
      const current = segments[index]
      const next = segments[index + 1]
      const merged: TimelineSegment = {
        ...current,
        id: `${current.id}-merged-${next.id}`,
        endMs: next.endMs,
        amplitude: Math.max(current.amplitude, next.amplitude),
        text: `${current.text} ${next.text}`.trim(),
      }
      const nextSegments = [
        ...segments.slice(0, index),
        merged,
        ...segments.slice(index + 2),
      ]
      setSelectedSegmentId(merged.id)
      return nextSegments
    })
  }

  const handleUseSegmentBounds = () => {
    const segment = segmentsToRender.find((candidate) => candidate.id === selectedSegmentId)
    if (!segment) {
      return
    }
    setStartMs(clampStart(segment.startMs))
    setEndMs(clampEnd(segment.endMs))
    if (previewRef.current) {
      previewRef.current.currentTime = segment.startMs / 1000
    }
  }

  const selectedSegment = useMemo(
    () => segmentsToRender.find((segment) => segment.id === selectedSegmentId) ?? null,
    [segmentsToRender, selectedSegmentId],
  )

  const selectedSegmentIndex = useMemo(
    () => segmentsToRender.findIndex((segment) => segment.id === selectedSegmentId),
    [segmentsToRender, selectedSegmentId],
  )

  const canMergeSelected = selectedSegmentIndex >= 0 && selectedSegmentIndex < segmentsToRender.length - 1

  useEffect(() => {
    const covering = segmentsToRender.find(
      (segment) => startMs >= segment.startMs && endMs <= segment.endMs,
    )
    if (covering && covering.id !== selectedSegmentId) {
      setSelectedSegmentId(covering.id)
    }
  }, [segmentsToRender, startMs, endMs, selectedSegmentId])

  const mutation = useMutation({
    mutationFn: async () => {
      if (startMs >= endMs) {
        throw new Error('End time must be greater than start time')
      }
      await request(`/v1/clips/${clip.id}`, {
        method: 'PATCH',
        body: {
          title: title.trim() || null,
          description: description.trim() || null,
          start_ms: startMs,
          end_ms: endMs,
        },
      })
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['clips', clip.video_id] }),
        queryClient.invalidateQueries({ queryKey: ['artifacts', clip.video_id] }),
      ])
      addNotification({
        title: 'Clip updated',
        message: 'Timing and metadata saved successfully.',
        tone: 'success',
      })
      setError(null)
      onClose()
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : 'Unable to update clip'
      setError(message)
      addNotification({
        title: 'Clip update failed',
        message,
        tone: 'error',
      })
    },
  })

  const handleReset = () => {
    setTitle(clip.title ?? '')
    setDescription(clip.description ?? '')
    setStartMs(clip.start_ms)
    setEndMs(clip.end_ms)
    setError(null)
  }

  const clipPreview = useMemo(() => {
    return artifacts.find((artifact) => artifact.kind === 'clip_preview')?.uri ?? null
  }, [artifacts])

  return (
    <div className="mt-3 space-y-5 rounded-xl border border-white/10 bg-slate-950/80 p-4 text-sm text-slate-100">
      <div className="grid gap-4 lg:grid-cols-[2fr_3fr]">
        <div className="space-y-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Title</span>
            <input
              className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Optional clip title"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Description</span>
            <textarea
              className="min-h-[96px] rounded-md border border-white/10 bg-slate-950 px-3 py-2"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional editorial summary"
            />
          </label>
          <fieldset className="rounded-lg border border-white/10 bg-slate-900/60 p-3 text-xs">
            <legend className="px-1 text-[10px] uppercase tracking-[0.2em] text-slate-400">
              Adjust handle
            </legend>
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="clip-handle"
                  value="start"
                  checked={activeHandle === 'start'}
                  onChange={() => setActiveHandle('start')}
                />
                Start
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="clip-handle"
                  value="end"
                  checked={activeHandle === 'end'}
                  onChange={() => setActiveHandle('end')}
                />
                End
              </label>
            </div>
          </fieldset>
          <div className="space-y-3 text-xs text-slate-300">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="uppercase tracking-wide text-slate-400">Start</span>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="number"
                    step="0.05"
                    min={0}
                    value={(startMs / 1000).toFixed(2)}
                    onChange={(event) => setStartFromSeconds(Number(event.target.value))}
                    className="w-full rounded-md border border-white/10 bg-slate-950 px-2 py-1"
                  />
                  <button
                    type="button"
                    className="rounded-md bg-slate-800 px-2 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-700"
                    onClick={() => {
                      if (previewRef.current) {
                        setStartFromSeconds(previewRef.current.currentTime)
                      }
                    }}
                  >
                    Use preview
                  </button>
                </div>
              </div>
              <div>
                <span className="uppercase tracking-wide text-slate-400">End</span>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="number"
                    step="0.05"
                    min={0}
                    value={(endMs / 1000).toFixed(2)}
                    onChange={(event) => setEndFromSeconds(Number(event.target.value))}
                    className="w-full rounded-md border border-white/10 bg-slate-950 px-2 py-1"
                  />
                  <button
                    type="button"
                    className="rounded-md bg-slate-800 px-2 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-700"
                    onClick={() => {
                      if (previewRef.current) {
                        setEndFromSeconds(previewRef.current.currentTime)
                      }
                    }}
                  >
                    Use preview
                  </button>
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <input
                type="range"
                min={0}
                max={totalDurationMs}
                step={50}
                value={startMs}
                onChange={(event) => setStartMs(clampStart(Number(event.target.value)))}
                className="w-full accent-indigo-500"
              />
              <input
                type="range"
                min={0}
                max={totalDurationMs}
                step={50}
                value={endMs}
                onChange={(event) => setEndMs(clampEnd(Number(event.target.value)))}
                className="w-full accent-emerald-500"
              />
              <p className="text-[11px] uppercase tracking-wide text-slate-500">
                Duration {((endMs - startMs) / 1000).toFixed(2)}s
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-black/60 p-3">
            <div className="relative h-24 rounded-lg border border-white/5 bg-slate-900/60">
              <div className="absolute inset-2">
                <div className="h-full w-full overflow-hidden">
                  <div className="relative flex h-full items-end gap-[2px]">
                    {segmentsToRender.map((segment) => {
                      const isSelected = segment.id === selectedSegmentId
                      const widthPercent = Math.max(
                        0.5,
                        ((segment.endMs - segment.startMs) / totalDurationMs) * 100,
                      )
                      return (
                        <button
                          type="button"
                          key={segment.id}
                          style={{
                            width: `${widthPercent}%`,
                            flexGrow: 0,
                            flexShrink: 0,
                            height: `${segment.amplitude * 100}%`,
                          }}
                          className={`group relative flex-1 items-end rounded-sm transition ${
                            isSelected ? 'bg-emerald-400/60 shadow-lg shadow-emerald-400/30' : 'bg-indigo-400/30 hover:bg-indigo-300/50'
                          }`}
                          onClick={() => handleTimelineClick(segment)}
                          title={`${segment.text.slice(0, 80)}…`}
                        >
                          <span className="pointer-events-none absolute bottom-full left-1/2 hidden w-40 -translate-x-1/2 translate-y-2 rounded bg-slate-900/90 px-2 py-1 text-[10px] text-slate-100 shadow group-hover:block">
                            {segment.text}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>
              <div
                className="pointer-events-none absolute inset-y-2 rounded bg-indigo-500/20"
                style={{
                  left: `${(startMs / totalDurationMs) * 100}%`,
                  width: `${((endMs - startMs) / totalDurationMs) * 100}%`,
                }}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-300">
              <span>Start • {formatSeconds(startMs / 1000)}</span>
              <span className="text-right">End • {formatSeconds(endMs / 1000)}</span>
              {selectedSegment && (
                <div className="col-span-2 flex flex-wrap items-center gap-2">
                  <span className="truncate text-slate-400">
                    Segment • {selectedSegment.text}
                  </span>
                  <button
                    type="button"
                    className="rounded bg-slate-800 px-2 py-1 font-semibold uppercase tracking-wide text-[10px] text-slate-200 hover:bg-slate-700"
                    onClick={() => handleSplitSegment(selectedSegment.id)}
                  >
                    Split
                  </button>
                  <button
                    type="button"
                    className="rounded bg-slate-800 px-2 py-1 font-semibold uppercase tracking-wide text-[10px] text-slate-200 hover:bg-slate-700 disabled:opacity-40"
                    onClick={() => handleMergeSegment(selectedSegment.id)}
                    disabled={!canMergeSelected}
                  >
                    Merge next
                  </button>
                  <button
                    type="button"
                    className="rounded bg-emerald-500/20 px-2 py-1 font-semibold uppercase tracking-wide text-[10px] text-emerald-200 hover:bg-emerald-500/30"
                    onClick={handleUseSegmentBounds}
                  >
                    Use bounds
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/60 p-3">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Preview</h4>
            {previewUri || clipPreview ? (
              <video
                ref={previewRef}
                controls
                preload="metadata"
                src={clipPreview ?? previewUri ?? undefined}
                className="mt-2 w-full rounded-lg border border-white/10"
              />
            ) : (
              <p className="mt-2 text-xs text-slate-400">
                No preview artifact registered yet. Generate clips to render previews.
              </p>
            )}
          </div>

          {selectedTranscript && (
            <div className="rounded-xl border border-white/10 bg-slate-900/70 p-3 text-xs text-slate-200">
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Transcript context ({selectedTranscript.language_code?.toUpperCase() ?? '—'})
              </h4>
              <p className="mt-2 whitespace-pre-line text-slate-300">
                {(selectedTranscript.segments ?? []).slice(0, 3).map((segment) => segment.text).join('\n') ||
                  'Transcript segments will appear here once transcription completes.'}
              </p>
            </div>
          )}
        </div>
      </div>

      {error && <p className="text-xs text-rose-300">{error}</p>}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-2 text-xs sm:flex-row sm:items-center">
          {clip.score_components && (
            <div className="flex flex-wrap items-center gap-2 rounded-md bg-slate-800/80 px-3 py-2 text-emerald-200">
              <span className="font-semibold uppercase tracking-wide text-emerald-400">Confidence</span>
              {Object.entries(clip.score_components).map(([key, value]) => (
                <span key={key} className="flex items-center gap-1">
                  <span className="text-slate-400">{key}:</span>
                  <span>{(value * 100).toFixed(0)}%</span>
                </span>
              ))}
              {typeof clip.confidence === 'number' && (
                <span className="ml-2 flex items-center gap-1 text-slate-300">
                  <span>Total:</span>
                  <span>{(clip.confidence * 100).toFixed(0)}%</span>
                </span>
              )}
            </div>
          )}
          <button
            type="button"
            className="rounded-md bg-slate-800 px-3 py-2 font-semibold text-slate-200 hover:bg-slate-700"
            onClick={handleReset}
          >
            Reset
          </button>
          <button
            type="button"
            className="rounded-md px-3 py-2 font-semibold text-slate-300 hover:text-white"
            onClick={onClose}
          >
            Cancel
          </button>
        </div>
        <button
          type="button"
          onClick={() => mutation.mutate()}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400 disabled:opacity-60"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Saving…' : 'Save clip'}
        </button>
      </div>
    </div>
  )
}
