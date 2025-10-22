import { FormEvent, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useApi } from '../hooks/useApi'
import { useNotifications } from '../contexts/NotificationContext'
import type {
  BrandAssetKind,
  BrandAssetResponse,
  BrandAssetUploadResponse,
  BrandKit,
  BrandKitListResponse,
  BrandKitResponse,
} from '../types'

interface BrandKitManagerProps {
  selectedBrandKitId: string | null
  onSelect: (brandKitId: string | null) => void
}

interface CreateBrandKitForm {
  name: string
  description: string
  primaryColor: string
  secondaryColor: string
  accentColor: string
  fontFamily: string
  subtitlePreset: string
  watermarkKey: string
  introKey: string
  outroKey: string
}

const INITIAL_FORM: CreateBrandKitForm = {
  name: '',
  description: '',
  primaryColor: '#FF3B81',
  secondaryColor: '#191D30',
  accentColor: '#FFC857',
  fontFamily: 'Inter',
  subtitlePreset: 'default/bold-outline',
  watermarkKey: '',
  introKey: '',
  outroKey: '',
}

const ASSET_KIND_OPTIONS: { value: BrandAssetKind; label: string }[] = [
  { value: 'watermark', label: 'Watermark' },
  { value: 'font', label: 'Font' },
  { value: 'intro', label: 'Intro slate' },
  { value: 'outro', label: 'Outro slate' },
  { value: 'logo', label: 'Logo' },
  { value: 'other', label: 'Other' },
]

export function BrandKitManager({ selectedBrandKitId, onSelect }: BrandKitManagerProps) {
  const { request } = useApi()
  const { addNotification } = useNotifications()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<CreateBrandKitForm>(INITIAL_FORM)
  const [subtitleOverrides, setSubtitleOverrides] = useState('')
  const [assetLabel, setAssetLabel] = useState('')
  const [assetKind, setAssetKind] = useState<BrandAssetKind>('watermark')
  const [assetFile, setAssetFile] = useState<File | null>(null)
  const assetFileInputRef = useRef<HTMLInputElement | null>(null)

  const brandKitsQuery = useQuery({
    queryKey: ['brand-kits'],
    queryFn: () => request<BrandKitListResponse>('/v1/branding/brand-kits'),
    staleTime: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: () => {
      let overrides: Record<string, unknown> = {}
      if (subtitleOverrides.trim().length > 0) {
        try {
          overrides = JSON.parse(subtitleOverrides)
        } catch (error) {
          throw new Error('Subtitle overrides must be valid JSON')
        }
      }
      return request<BrandKitResponse>('/v1/branding/brand-kits', {
        method: 'POST',
        body: {
          name: form.name,
          description: form.description || null,
          primary_color: form.primaryColor || null,
          secondary_color: form.secondaryColor || null,
          accent_color: form.accentColor || null,
          font_family: form.fontFamily || null,
          subtitle_preset: form.subtitlePreset || null,
          subtitle_overrides: overrides,
          watermark_object_key: form.watermarkKey || null,
          intro_object_key: form.introKey || null,
          outro_object_key: form.outroKey || null,
          is_default: !selectedBrandKitId,
        },
      })
    },
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['brand-kits'] })
      if (!selectedBrandKitId) {
        onSelect(response.data.id)
      }
      setForm(INITIAL_FORM)
      setSubtitleOverrides('')
      addNotification({
        title: 'Brand kit created',
        message: 'New brand profile is ready for assignment.',
        tone: 'success',
      })
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Failed to create brand kit'
      addNotification({ title: 'Unable to save brand kit', message, tone: 'error' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ brandKitId, body }: { brandKitId: string; body: Record<string, unknown> }) =>
      request<BrandKitResponse>(`/v1/branding/brand-kits/${brandKitId}`, {
        method: 'PATCH',
        body,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['brand-kits'] })
      addNotification({ title: 'Brand kit updated', tone: 'success' })
    },
    onError: () => {
      addNotification({
        title: 'Update failed',
        message: 'Double-check your permissions and try again.',
        tone: 'error',
      })
    },
  })

  const assetUploadMutation = useMutation({
    mutationFn: async ({
      brandKitId,
      label,
      kind,
      file,
    }: {
      brandKitId: string
      label: string
      kind: BrandAssetKind
      file: File
    }) => {
      const presign = await request<BrandAssetUploadResponse>(
        `/v1/branding/brand-kits/${brandKitId}/assets:presign`,
        {
          method: 'POST',
          body: {
            filename: file.name,
            content_type: file.type || 'application/octet-stream',
            kind,
          },
        },
      )
      const { upload_url, headers, object_key } = presign.data
      const uploadHeaders = new Headers()
      Object.entries(headers).forEach(([key, value]) => uploadHeaders.append(key, value))
      await fetch(upload_url, {
        method: 'PUT',
        headers: uploadHeaders,
        body: file,
      })
      return request<BrandAssetResponse>(
        `/v1/branding/brand-kits/${brandKitId}/assets`,
        {
          method: 'POST',
          body: {
            label: label || file.name,
            kind,
            object_key,
          },
        },
      )
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['brand-kits'] })
      setAssetLabel('')
      setAssetKind('watermark')
      setAssetFile(null)
      if (assetFileInputRef.current) {
        assetFileInputRef.current.value = ''
      }
      addNotification({
        title: 'Asset uploaded',
        message: 'Brand asset is ready for editors and exports.',
        tone: 'success',
      })
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Unable to upload asset'
      addNotification({
        title: 'Upload failed',
        message,
        tone: 'error',
      })
    },
  })

  const deleteAssetMutation = useMutation({
    mutationFn: ({ brandKitId, assetId }: { brandKitId: string; assetId: string }) =>
      request<void>(`/v1/branding/brand-kits/${brandKitId}/assets/${assetId}`, {
        method: 'DELETE',
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['brand-kits'] })
      addNotification({ title: 'Asset removed', tone: 'success' })
    },
    onError: () => {
      addNotification({
        title: 'Unable to delete asset',
        message: 'Check your permissions and try again.',
        tone: 'error',
      })
    },
  })

  const brandKits: BrandKit[] = brandKitsQuery.data?.data ?? []
  const activeBrandKit = useMemo(
    () => brandKits.find((kit) => kit.id === selectedBrandKitId) ?? null,
    [brandKits, selectedBrandKitId],
  )

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    createMutation.mutate()
  }

  const handleAssetUpload = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!activeBrandKit) {
      addNotification({
        title: 'Select a brand kit',
        message: 'Choose a brand kit before uploading assets.',
        tone: 'warning',
      })
      return
    }
    if (!assetFile) {
      addNotification({
        title: 'Choose a file',
        message: 'Select a brand asset file to upload.',
        tone: 'warning',
      })
      return
    }
    assetUploadMutation.mutate({
      brandKitId: activeBrandKit.id,
      label: assetLabel.trim() || assetFile.name,
      kind: assetKind,
      file: assetFile,
    })
  }

  return (
    <section className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Brand kits</h2>
          <p className="text-sm text-slate-400">
            Manage visual identities and assign them to exports and subtitle renders.
          </p>
        </div>
        <div className="flex flex-col text-xs text-slate-400">
          <span>{brandKits.length} kits</span>
          {activeBrandKit && <span>Assigned to this project: {activeBrandKit.name}</span>}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <div className="space-y-3">
          <label className="flex flex-col gap-2 text-xs text-slate-300">
            <span className="font-semibold uppercase tracking-wide text-slate-400">Assigned kit</span>
            <select
              value={selectedBrandKitId ?? ''}
              onChange={(event) => onSelect(event.target.value || null)}
              className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm"
            >
              <option value="">No brand kit</option>
              {brandKits.map((kit) => (
                <option key={kit.id} value={kit.id}>
                  {kit.name} {kit.is_default ? '(default)' : ''}
                </option>
              ))}
            </select>
          </label>

          {activeBrandKit ? (
            <div className="space-y-3 rounded-xl border border-white/10 bg-slate-950/70 p-4 text-xs text-slate-200">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">{activeBrandKit.name}</h3>
                  {activeBrandKit.description && (
                    <p className="text-xs text-slate-400">{activeBrandKit.description}</p>
                  )}
                </div>
                <div className="flex gap-2 text-[11px] uppercase tracking-wide text-slate-400">
                  {activeBrandKit.is_default && <span>Default</span>}
                  {activeBrandKit.is_archived && <span className="text-rose-300">Archived</span>}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-[11px]">
                <ColorSwatch label="Primary" value={activeBrandKit.primary_color} />
                <ColorSwatch label="Secondary" value={activeBrandKit.secondary_color} />
                <ColorSwatch label="Accent" value={activeBrandKit.accent_color} />
              </div>
              <dl className="grid grid-cols-2 gap-3 text-[11px] text-slate-400">
                <div>
                  <dt>Font family</dt>
                  <dd className="text-slate-200">{activeBrandKit.font_family ?? 'System'}</dd>
                </div>
                <div>
                  <dt>Subtitle preset</dt>
                  <dd className="text-slate-200">{activeBrandKit.subtitle_preset ?? 'Default'}</dd>
                </div>
                <div className="col-span-2">
                  <dt>Overrides</dt>
                  <dd>
                    <pre className="mt-1 max-h-32 overflow-auto rounded bg-slate-950/80 p-3 text-[10px] text-slate-200">
                      {JSON.stringify(activeBrandKit.subtitle_overrides, null, 2)}
                    </pre>
                  </dd>
                </div>
              </dl>
              <div className="space-y-3 rounded-lg border border-white/5 bg-slate-900/60 p-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Assets</h4>
                  <span className="text-[11px] text-slate-400">
                    {activeBrandKit.assets.length} item{activeBrandKit.assets.length === 1 ? '' : 's'}
                  </span>
                </div>
                {activeBrandKit.assets.length > 0 ? (
                  <ul className="space-y-2">
                    {activeBrandKit.assets.map((asset) => (
                      <li
                        key={asset.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded bg-slate-950/60 px-3 py-2"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-white">{asset.label}</p>
                          <a
                            href={asset.uri}
                            target="_blank"
                            rel="noreferrer"
                            className="block truncate text-xs text-indigo-300 hover:text-indigo-200"
                          >
                            {asset.uri}
                          </a>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="rounded-full bg-slate-800 px-2 py-1 text-[10px] uppercase tracking-wide text-slate-300">
                            {asset.kind}
                          </span>
                          <button
                            type="button"
                            className="rounded bg-rose-500/20 px-2 py-1 text-[11px] font-semibold text-rose-200 hover:bg-rose-500/30"
                            disabled={deleteAssetMutation.isPending}
                            onClick={() =>
                              deleteAssetMutation.mutate({
                                brandKitId: activeBrandKit.id,
                                assetId: asset.id,
                              })
                            }
                          >
                            Remove
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] text-slate-400">No assets uploaded yet.</p>
                )}
                <form onSubmit={handleAssetUpload} className="space-y-2 text-[11px] text-slate-200">
                  <div className="grid gap-2 md:grid-cols-3">
                    <label className="flex flex-col gap-1">
                      <span className="uppercase tracking-wide text-slate-400">Label</span>
                      <input
                        value={assetLabel}
                        onChange={(event) => setAssetLabel(event.target.value)}
                        className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                        placeholder="Watermark transparent PNG"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="uppercase tracking-wide text-slate-400">Type</span>
                      <select
                        value={assetKind}
                        onChange={(event) => setAssetKind(event.target.value as BrandAssetKind)}
                        className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                      >
                        {ASSET_KIND_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="uppercase tracking-wide text-slate-400">File</span>
                      <input
                        ref={assetFileInputRef}
                        type="file"
                        onChange={(event) => setAssetFile(event.target.files?.[0] ?? null)}
                        className="rounded-md border border-dashed border-white/20 bg-slate-950 px-3 py-2"
                      />
                    </label>
                  </div>
                  <button
                    type="submit"
                    className="rounded bg-indigo-500 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
                    disabled={assetUploadMutation.isPending}
                  >
                    {assetUploadMutation.isPending ? 'Uploading…' : 'Upload asset'}
                  </button>
                </form>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <button
                  type="button"
                  className="rounded-md bg-indigo-500 px-3 py-1 font-semibold text-white hover:bg-indigo-400"
                  onClick={() => updateMutation.mutate({ brandKitId: activeBrandKit.id, body: { is_default: true } })}
                  disabled={updateMutation.isPending}
                >
                  Set default
                </button>
                <button
                  type="button"
                  className="rounded-md bg-slate-800 px-3 py-1 font-semibold text-slate-100 hover:bg-slate-700"
                  onClick={() =>
                    updateMutation.mutate({
                      brandKitId: activeBrandKit.id,
                      body: { is_archived: !activeBrandKit.is_archived },
                    })
                  }
                  disabled={updateMutation.isPending}
                >
                  {activeBrandKit.is_archived ? 'Restore' : 'Archive'}
                </button>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              Select a kit to view palette, typography, and subtitle overrides.
            </p>
          )}
        </div>

        <form
          onSubmit={handleCreate}
          className="space-y-3 rounded-xl border border-dashed border-white/10 bg-slate-950/40 p-4 text-xs text-slate-200"
        >
          <h3 className="text-sm font-semibold text-white">Create brand kit</h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="uppercase tracking-wide text-slate-400">Name</span>
              <input
                required
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                placeholder="Creator Studio"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="uppercase tracking-wide text-slate-400">Subtitle preset</span>
              <input
                value={form.subtitlePreset}
                onChange={(event) =>
                  setForm((current) => ({ ...current, subtitlePreset: event.target.value }))
                }
                className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                placeholder="default/bold-outline"
              />
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="uppercase tracking-wide text-slate-400">Description</span>
              <textarea
                value={form.description}
                onChange={(event) =>
                  setForm((current) => ({ ...current, description: event.target.value }))
                }
                className="min-h-[72px] rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                placeholder="Optional notes for editors"
              />
            </label>
            <ColorInput
              label="Primary color"
              value={form.primaryColor}
              onChange={(value) => setForm((current) => ({ ...current, primaryColor: value }))}
            />
            <ColorInput
              label="Secondary color"
              value={form.secondaryColor}
              onChange={(value) => setForm((current) => ({ ...current, secondaryColor: value }))}
            />
            <ColorInput
              label="Accent color"
              value={form.accentColor}
              onChange={(value) => setForm((current) => ({ ...current, accentColor: value }))}
            />
            <label className="flex flex-col gap-1">
              <span className="uppercase tracking-wide text-slate-400">Font family</span>
              <input
                value={form.fontFamily}
                onChange={(event) =>
                  setForm((current) => ({ ...current, fontFamily: event.target.value }))
                }
                className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                placeholder="Inter"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="uppercase tracking-wide text-slate-400">Watermark object key</span>
              <input
                value={form.watermarkKey}
                onChange={(event) =>
                  setForm((current) => ({ ...current, watermarkKey: event.target.value }))
                }
                className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                placeholder="brand/watermark.png"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="uppercase tracking-wide text-slate-400">Intro slate key</span>
              <input
                value={form.introKey}
                onChange={(event) => setForm((current) => ({ ...current, introKey: event.target.value }))}
                className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                placeholder="brand/intro.mp4"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="uppercase tracking-wide text-slate-400">Outro slate key</span>
              <input
                value={form.outroKey}
                onChange={(event) => setForm((current) => ({ ...current, outroKey: event.target.value }))}
                className="rounded-md border border-white/10 bg-slate-950 px-3 py-2"
                placeholder="brand/outro.mp4"
              />
            </label>
          </div>
          <label className="flex flex-col gap-1">
            <span className="uppercase tracking-wide text-slate-400">Subtitle overrides (JSON)</span>
            <textarea
              value={subtitleOverrides}
              onChange={(event) => setSubtitleOverrides(event.target.value)}
              className="min-h-[88px] rounded-md border border-white/10 bg-slate-950 px-3 py-2 font-mono text-[11px]"
              placeholder={`{
  "fontSize": 64,
  "outline": 4
}`}
            />
          </label>
          <button
            type="submit"
            className="w-full rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-400 disabled:opacity-60"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Saving…' : 'Create brand kit'}
          </button>
        </form>
      </div>

      {brandKitsQuery.isError && (
        <p className="text-xs text-rose-300">
          Unable to load brand kits. Confirm your network connection and permissions.
        </p>
      )}
    </section>
  )
}

function ColorSwatch({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-6 w-6 rounded border border-white/10" style={{ background: value ?? '#111827' }} />
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
        <span className="text-[11px] text-slate-200">{value ?? '—'}</span>
      </div>
    </div>
  )
}

function ColorInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="uppercase tracking-wide text-slate-400">{label}</span>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-9 w-9 rounded border border-white/20 bg-transparent"
        />
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="flex-1 rounded-md border border-white/10 bg-slate-950 px-3 py-2"
        />
      </div>
    </label>
  )
}
