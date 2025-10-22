import { Dispatch, SetStateAction, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../hooks/useApi'
import type { Transcript, TranscriptSegment, TranscriptWord } from '../types'

interface TranscriptEditorProps {
  transcript: Transcript
  videoId: string
  onClose: () => void
}

type SegmentDraft = TranscriptSegment & { key: string }

const emptySegment = (): TranscriptSegment => ({
  start_ms: 0,
  end_ms: 0,
  text: '',
  confidence: null,
  words: [],
})

export function TranscriptEditor({ transcript, videoId, onClose }: TranscriptEditorProps) {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const initialSegments = useMemo(() => transcript.segments ?? [], [transcript.segments])
  const initialAligned = useMemo(
    () => transcript.aligned_segments ?? [],
    [transcript.aligned_segments],
  )

  const [segments, setSegments] = useState<SegmentDraft[]>(() =>
    initialSegments.map((segment, index) => ({ ...segment, key: `${index}-${segment.start_ms}` })),
  )
  const [alignedSegments, setAlignedSegments] = useState<SegmentDraft[]>(() =>
    initialAligned.map((segment, index) => ({ ...segment, key: `aligned-${index}-${segment.start_ms}` })),
  )
  const [activeTab, setActiveTab] = useState<'segments' | 'aligned'>(
    segments.length > 0 ? 'segments' : 'aligned',
  )

  const mutation = useMutation({
    mutationFn: async () => {
      const normalize = (items: SegmentDraft[]): TranscriptSegment[] =>
        items
          .filter((segment) => segment.text.trim().length > 0)
          .map((segment) => ({
            start_ms: Math.max(0, Math.round(segment.start_ms)),
            end_ms: Math.max(0, Math.round(segment.end_ms)),
            text: segment.text.trim(),
            confidence: segment.confidence ?? null,
            words: normalizeWords(segment.words),
          }))
          .sort((a, b) => a.start_ms - b.start_ms)

      const payload = {
        segments: normalize(segments),
        aligned_segments: normalize(alignedSegments),
      }

      await request(`/v1/videos/${videoId}/transcripts/${transcript.id}`, {
        method: 'PATCH',
        body: payload,
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['transcripts', videoId] })
      await queryClient.invalidateQueries({ queryKey: ['jobs'], exact: false })
      onClose()
    },
  })

  const setSegmentValue = (
    listSetter: Dispatch<SetStateAction<SegmentDraft[]>>,
    index: number,
    updater: (segment: SegmentDraft) => SegmentDraft,
  ) => {
    listSetter((current) => current.map((segment, idx) => (idx === index ? updater(segment) : segment)))
  }

  const handleAddSegment = (target: 'segments' | 'aligned') => {
    const segment: SegmentDraft = {
      ...emptySegment(),
      key: typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now()),
      words: [],
    }
    if (target === 'segments') {
      setSegments((current) => [...current, segment])
    } else {
      setAlignedSegments((current) => [...current, segment])
    }
  }

  const handleRemoveSegment = (target: 'segments' | 'aligned', index: number) => {
    if (target === 'segments') {
      setSegments((current) => current.filter((_, idx) => idx !== index))
    } else {
      setAlignedSegments((current) => current.filter((_, idx) => idx !== index))
    }
  }

  const segmentList = activeTab === 'segments' ? segments : alignedSegments

  return (
    <div className="mt-3 space-y-4 rounded-lg border border-white/10 bg-slate-900/80 p-4">
      <div className="flex items-center justify-between">
        <div className="inline-flex items-center gap-2 rounded-md bg-slate-800 p-1 text-xs">
          <button
            type="button"
            className={`rounded px-2 py-1 font-semibold transition ${
              activeTab === 'segments' ? 'bg-indigo-500 text-white' : 'text-slate-300'
            }`}
            onClick={() => setActiveTab('segments')}
          >
            Transcript segments
          </button>
          <button
            type="button"
            className={`rounded px-2 py-1 font-semibold transition ${
              activeTab === 'aligned' ? 'bg-indigo-500 text-white' : 'text-slate-300'
            }`}
            onClick={() => setActiveTab('aligned')}
          >
            Aligned segments
          </button>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            className="rounded-md bg-slate-800 px-2 py-1 font-semibold text-slate-200 hover:bg-slate-700"
            onClick={() => handleAddSegment(activeTab)}
          >
            Add segment
          </button>
          <button
            type="button"
            className="rounded-md px-2 py-1 font-semibold text-slate-300 hover:text-white"
            onClick={onClose}
          >
            Cancel
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {segmentList.length === 0 ? (
          <p className="text-xs text-slate-400">No segments available. Add one to begin editing.</p>
        ) : (
          segmentList.map((segment, index) => (
            <div
              key={segment.key}
              className="rounded-lg border border-white/5 bg-slate-950/80 p-3 text-xs text-slate-100"
            >
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
                <label className="flex flex-col">
                  <span className="font-semibold uppercase tracking-wide text-slate-400">Start (s)</span>
                  <input
                    type="number"
                    step="0.1"
                    min={0}
                    className="mt-1 rounded-md border border-white/10 bg-slate-900 px-2 py-1 text-slate-100"
                    value={msToSeconds(segment.start_ms)}
                    onChange={(event) => {
                      const seconds = Number(event.target.value)
                      setSegmentValue(
                        activeTab === 'segments' ? setSegments : setAlignedSegments,
                        index,
                        (current) => ({ ...current, start_ms: secondsToMs(seconds) }),
                      )
                    }}
                  />
                </label>
                <label className="flex flex-col">
                  <span className="font-semibold uppercase tracking-wide text-slate-400">End (s)</span>
                  <input
                    type="number"
                    step="0.1"
                    min={0}
                    className="mt-1 rounded-md border border-white/10 bg-slate-900 px-2 py-1 text-slate-100"
                    value={msToSeconds(segment.end_ms)}
                    onChange={(event) => {
                      const seconds = Number(event.target.value)
                      setSegmentValue(
                        activeTab === 'segments' ? setSegments : setAlignedSegments,
                        index,
                        (current) => ({ ...current, end_ms: secondsToMs(seconds) }),
                      )
                    }}
                  />
                </label>
                <div className="sm:col-span-3">
                  <span className="font-semibold uppercase tracking-wide text-slate-400">Text</span>
                  <textarea
                    className="mt-1 w-full rounded-md border border-white/10 bg-slate-900 px-2 py-1 text-slate-100"
                    rows={3}
                    value={segment.text}
                    onChange={(event) => {
                      const text = event.target.value
                      setSegmentValue(
                        activeTab === 'segments' ? setSegments : setAlignedSegments,
                        index,
                        (current) => ({ ...current, text }),
                      )
                    }}
                  />
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-[11px] text-slate-400">
                  {segment.confidence != null
                    ? `Confidence: ${(segment.confidence * 100).toFixed(1)}%`
                    : 'Confidence: —'}
                </span>
                <button
                  type="button"
                  className="rounded-md px-2 py-1 text-[11px] font-semibold text-rose-300 hover:text-rose-200"
                  onClick={() => handleRemoveSegment(activeTab, index)}
                >
                  Remove
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400 disabled:opacity-60"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </div>
  )
}

const msToSeconds = (value: number) => (value ? (value / 1000).toFixed(2) : '0.00')

const secondsToMs = (value: number) => {
  if (Number.isNaN(value)) {
    return 0
  }
  return Math.max(0, Math.round(value * 1000))
}

const normalizeWords = (
  words: TranscriptWord[] | undefined | null,
): TranscriptWord[] | null => {
  if (!words || words.length === 0) {
    return null
  }
  return words.map((word) => ({
    word: word.word,
    start_ms: Math.max(0, Math.round(word.start_ms)),
    end_ms: Math.max(0, Math.round(word.end_ms)),
    confidence: word.confidence ?? null,
  }))
}
