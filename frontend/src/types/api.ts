export type ProcessingJob = {
  id: number;
  video_source_id?: number | null;
  job_type: string;
  status: string;
  progress: number;
  error_message?: string | null;
};

export type VideoSource = {
  id: number;
  title?: string | null;
  source_type: string;
  source_url?: string | null;
  file_path?: string | null;
  duration_seconds?: number | null;
  status: string;
  error_message?: string | null;
};

export type ClipBatch = {
  id: number;
  video_source_id: number;
  name: string;
  status: string;
  config_json?: Record<string, unknown>;
};

export type Clip = {
  id: number;
  clip_batch_id: number;
  start_time_sec: number;
  end_time_sec: number;
  duration_sec: number;
  title?: string | null;
  description?: string | null;
  viral_score?: number | null;
  grade_hook?: string | null;
  grade_flow?: string | null;
  grade_value?: string | null;
  grade_trend?: string | null;
  language?: string | null;
  status: string;
  thumbnail_path?: string | null;
  video_path?: string | null;
};

export type ClipDetail = Clip & {
  transcript_preview?: string | null;
  subtitle_language?: string | null;
  viral_breakdown?: {
    hook?: string;
    flow?: string;
    value?: string;
    trend?: string;
  } | null;
};

export type VideoCreateResponse = {
  video: VideoSource;
  job: ProcessingJob;
};

export type SubtitleStyle = {
  id: number;
  name: string;
  style_json: Record<string, unknown>;
  is_default_global: boolean;
};

export type SubtitleSegment = {
  id: number;
  clip_id: number;
  start_time_sec: number;
  end_time_sec: number;
  text: string;
  language: string;
};

export type ExportJob = {
  id: number;
  clip_id: number;
  resolution: string;
  fps: number;
  aspect_ratio: string;
  status: string;
  output_path?: string | null;
  error_message?: string | null;
};
