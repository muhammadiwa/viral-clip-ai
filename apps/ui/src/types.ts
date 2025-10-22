export interface PaginationMeta {
  limit: number
  offset: number
  count: number
  total: number
  has_more: boolean
  next_offset: number | null
}

export interface User {
  id: string
  email: string
  full_name?: string | null
  owned_org_id?: string | null
  created_at: string
  updated_at: string
  last_login_at?: string | null
}

export interface Organization {
  id: string
  name: string
  slug?: string | null
  created_at: string
  updated_at: string
}

export interface OrganizationListResponse {
  data: Organization[]
  count: number
  pagination: PaginationMeta
}

export interface OrganizationCreateResponse {
  data: Organization
}

export interface Project {
  id: string
  org_id: string
  name: string
  description?: string | null
  source_url?: string | null
  status: string
  export_status: string
  export_settings?: Record<string, unknown> | null
  last_exported_at?: string | null
  export_error?: string | null
  brand_kit_id?: string | null
  brand_overrides?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ProjectResponse {
  data: Project
}

export interface ProjectListResponse {
  data: Project[]
  count: number
  pagination: PaginationMeta
}

export interface BrandKit {
  id: string
  org_id: string
  name: string
  description?: string | null
  primary_color?: string | null
  secondary_color?: string | null
  accent_color?: string | null
  font_family?: string | null
  subtitle_preset?: string | null
  subtitle_overrides: Record<string, unknown>
  watermark_object_key?: string | null
  intro_object_key?: string | null
  outro_object_key?: string | null
  is_default: boolean
  is_archived: boolean
  created_at: string
  updated_at: string
  assets: BrandAsset[]
}

export type BrandAssetKind = 'watermark' | 'font' | 'intro' | 'outro' | 'logo' | 'other'

export interface BrandAsset {
  id: string
  org_id: string
  brand_kit_id: string
  label: string
  kind: BrandAssetKind
  object_key: string
  uri: string
  created_at: string
  updated_at: string
}

export interface BrandAssetResponse {
  data: BrandAsset
}

export interface BrandAssetListResponse {
  data: BrandAsset[]
}

export interface BrandAssetUploadTicket {
  object_key: string
  upload_url: string
  headers: Record<string, string>
  kind: BrandAssetKind
}

export interface BrandAssetUploadResponse {
  data: BrandAssetUploadTicket
}

export interface BrandKitResponse {
  data: BrandKit
}

export interface BrandKitListResponse {
  data: BrandKit[]
  count: number
  pagination: PaginationMeta
}

export interface Video {
  id: string
  project_id: string
  org_id: string
  source_type: 'upload' | 'youtube'
  upload_key?: string | null
  source_url?: string | null
  status: string
  duration_ms?: number | null
  frame_rate?: number | null
  width?: number | null
  height?: number | null
  created_at: string
  updated_at: string
}

export interface VideoListResponse {
  data: Video[]
  count: number
  pagination: PaginationMeta
}

export interface Job {
  id: string
  org_id: string
  project_id: string
  video_id?: string | null
  clip_id?: string | null
  retell_id?: string | null
  transcript_id?: string | null
  job_type: string
  status: string
  progress: number
  message?: string | null
  retry_count: number
  created_at: string
  updated_at: string
}

export interface JobListResponse {
  data: Job[]
  count: number
  pagination: PaginationMeta
}

export interface VideoUploadCredentials {
  object_key: string
  upload_url: string
  expires_in: number
  headers: Record<string, string>
}

export interface VideoIngestResponse {
  video: Video
  job: Job
  upload?: VideoUploadCredentials | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface Membership {
  id: string
  org_id: string
  user_id: string
  role: string
  status: string
  invited_by_user_id?: string | null
  invited_at: string
  joined_at?: string | null
  created_at: string
  updated_at: string
}

export interface MembershipListResponse {
  data: Membership[]
  count: number
  pagination: PaginationMeta
}

export interface UserListResponse {
  data: User[]
  count: number
  pagination: PaginationMeta
}

export interface RegisterResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
  organization: Organization
  membership: Membership
}

export interface Clip {
  id: string
  org_id: string
  project_id: string
  video_id: string
  start_ms: number
  end_ms: number
  title?: string | null
  description?: string | null
  confidence?: number | null
  score_components?: Record<string, number> | null
  style_status: string
  style_preset?: string | null
  style_settings?: Record<string, unknown> | null
  last_styled_at?: string | null
  style_error?: string | null
  voice_status: string
  voice_language?: string | null
  voice_name?: string | null
  voice_settings?: Record<string, unknown> | null
  last_voiced_at?: string | null
  voice_error?: string | null
  created_at: string
  updated_at: string
}

export interface ClipListResponse {
  data: Clip[]
  count: number
  pagination: PaginationMeta
}

export interface TranscriptWord {
  word: string
  start_ms: number
  end_ms: number
  confidence?: number | null
}

export interface TranscriptSegment {
  start_ms: number
  end_ms: number
  text: string
  confidence?: number | null
  words?: TranscriptWord[] | null
}

export interface Transcript {
  id: string
  org_id: string
  project_id: string
  video_id: string
  language_code: string | null
  status: string
  alignment_status: string
  prompt?: string | null
  last_transcribed_at?: string | null
  last_aligned_at?: string | null
  segments?: TranscriptSegment[]
  aligned_segments?: TranscriptSegment[]
  transcription_error?: string | null
  alignment_error?: string | null
  created_at: string
  updated_at: string
}

export interface TranscriptListResponse {
  data: Transcript[]
  count: number
  pagination: PaginationMeta
}

export interface Subscription {
  id: string
  org_id: string
  plan: string
  status: string
  seats: number
  minutes_quota: number
  clip_quota: number
  retell_quota: number
  storage_quota_gb: number
  renews_at?: string | null
  canceled_at?: string | null
  created_at: string
  updated_at: string
}

export interface SubscriptionResponse {
  data: Subscription
}

export interface UsageSnapshot {
  minutes_processed: number
  minutes_quota?: number | null
  clips_generated: number
  clip_quota?: number | null
  retells_created: number
  retell_quota?: number | null
  storage_gb: number
  storage_quota_gb?: number | null
  updated_at: string
}

export interface UsageResponse {
  data: UsageSnapshot
}

export interface Artifact {
  id: string
  org_id: string
  project_id: string
  video_id?: string | null
  clip_id?: string | null
  kind: string
  uri: string
  size_bytes: number
  content_type?: string | null
  created_at: string
}

export interface ArtifactListResponse {
  data: Artifact[]
  count: number
  pagination: PaginationMeta
}

export interface MetricSummary {
  name: string
  metric_type: string
  count: number
  average?: number | null
  minimum?: number | null
  maximum?: number | null
  p50?: number | null
  p95?: number | null
}

export interface MetricSummaryResponse {
  data: MetricSummary
}

export interface QARun {
  id: string
  org_id: string
  dataset_name: string
  dataset_version?: string | null
  clip_cases: number
  subtitle_cases: number
  mix_cases: number
  watermark_cases: number
  clip_failures: number
  subtitle_failures: number
  mix_failures: number
  watermark_failures: number
  failure_details: string[]
  clip_pass_rate: number
  subtitle_pass_rate: number
  mix_pass_rate: number
  watermark_pass_rate: number
  failure_artifact_urls: string[]
  failure_artifact_ids: string[]
  locale_coverage: Record<string, number>
  genre_coverage: Record<string, number>
  frame_diff_failures: number
  latest_review?: QAReview | null
  recorded_at: string
}

export interface QARunListResponse {
  data: QARun[]
  count: number
  pagination: PaginationMeta
}

export interface QAFinding {
  id: string
  run_id: string
  category: string
  case_name: string
  message: string
  reference_urls: string[]
  reference_artifact_ids: string[]
  overlay_url?: string | null
  overlay_metadata?: Record<string, unknown>
  status:
    | 'open'
    | 'acknowledged'
    | 'in_progress'
    | 'blocked'
    | 'ready_for_review'
    | 'resolved'
  notes?: string | null
  assignee_id?: string | null
  assignee_name?: string | null
  assigned_at?: string | null
  due_date?: string | null
  created_at: string
  updated_at: string
}

export interface QAReview {
  id: string
  run_id: string
  reviewer_id?: string | null
  status: 'pending' | 'approved' | 'changes_required'
  notes?: string | null
  reference_artifact_ids: string[]
  created_at: string
  updated_at: string
}

export interface QARunDetail extends QARun {
  findings: QAFinding[]
  reviews: QAReview[]
}

export interface QARunResponse {
  data: QARunDetail
}

export interface QAFindingResponse {
  data: QAFinding
}

export interface QAReviewResponse {
  data: QAReview
}
