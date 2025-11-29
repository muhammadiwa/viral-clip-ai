export type VideoSource = {
  id: number;
  title?: string | null;
  source_type: string;
  source_url?: string | null;
  duration_seconds?: number | null;
  status: string;
};
