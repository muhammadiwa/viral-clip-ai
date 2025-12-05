import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../../lib/apiClient";
import { useQueryClient } from "@tanstack/react-query";
import { VideoSource, VideoCreateResponse } from "../../types/api";
import YouTubePlayer from "./YouTubePlayer";

type Props = {
  onVideoCreated: (video?: VideoSource, jobId?: number) => void;
};

type PreviewState = {
  loading: boolean;
  video: VideoSource | null;
  error: string | null;
};

// Helper to extract YouTube video ID from URL for preview validation
const extractYouTubeVideoId = (url: string): string | null => {
  if (!url) return null;

  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/,
  ];

  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  return null;
};

// Debounce hook
const useDebounce = <T,>(value: T, delay: number): T => {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

const UploadCard: React.FC<Props> = ({ onVideoCreated }) => {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewState>({
    loading: false,
    video: null,
    error: null,
  });
  const qc = useQueryClient();

  // Debounce the URL input to avoid too many API calls
  const debouncedUrl = useDebounce(youtubeUrl, 500);

  // Fetch metadata when URL changes (instant preview)
  const fetchMetadata = useCallback(async (url: string) => {
    const videoId = extractYouTubeVideoId(url);

    if (!videoId) {
      if (url.trim()) {
        setPreview({ loading: false, video: null, error: "Invalid YouTube URL" });
      } else {
        setPreview({ loading: false, video: null, error: null });
      }
      return;
    }

    setPreview({ loading: true, video: null, error: null });

    try {
      const form = new FormData();
      form.append("youtube_url", url);
      const res = await api.post<{ video: VideoSource }>("/viral-clip/video/youtube/instant", form);
      setPreview({ loading: false, video: res.data.video, error: null });
    } catch (err: any) {
      const errorMessage = err?.response?.data?.detail || "Failed to fetch video info";
      setPreview({ loading: false, video: null, error: errorMessage });
    }
  }, []);

  // Effect to fetch metadata when debounced URL changes
  useEffect(() => {
    if (debouncedUrl) {
      fetchMetadata(debouncedUrl);
    } else {
      setPreview({ loading: false, video: null, error: null });
    }
  }, [debouncedUrl, fetchMetadata]);

  // Clear preview when switching to file upload
  useEffect(() => {
    if (file) {
      setYoutubeUrl("");
      setPreview({ loading: false, video: null, error: null });
    }
  }, [file]);

  const handleSubmit = async () => {
    if (!youtubeUrl && !file) {
      setStatus("Paste a link or choose a file first.");
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      if (youtubeUrl) {
        const form = new FormData();
        form.append("youtube_url", youtubeUrl);
        const res = await api.post<VideoCreateResponse>("/viral-clip/video/youtube", form);
        onVideoCreated(res.data.video, res.data.job?.id);
      } else if (file) {
        const form = new FormData();
        form.append("file", file);
        const res = await api.post<VideoCreateResponse>("/viral-clip/video/upload", form);
        onVideoCreated(res.data.video, res.data.job?.id);
      }
      setYoutubeUrl("");
      setFile(null);
      setPreview({ loading: false, video: null, error: null });
      await qc.invalidateQueries({ queryKey: ["videos"] });
      setStatus("Video uploaded! Processing will start automatically.");
    } catch (err: any) {
      setStatus(err?.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const clearPreview = () => {
    setYoutubeUrl("");
    setPreview({ loading: false, video: null, error: null });
  };

  const formatDuration = (seconds: number | null | undefined): string => {
    if (!seconds) return "";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <motion.div
      className="rounded-3xl bg-gradient-to-br from-[#ffe9da] via-[#fff3ea] to-[#ffe5d5] p-6 flex flex-col gap-4 shadow-sm border border-white/60 items-center"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="text-sm font-semibold text-slate-800">Autoclip</div>

      {/* URL Input */}
      <div className="w-full max-w-xl relative">
        <input
          className="w-full rounded-xl border border-dashed border-primary/40 bg-white/80 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/40 text-center pr-10"
          placeholder="Drop a YouTube link or paste URL..."
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          disabled={!!file}
        />
        {youtubeUrl && (
          <button
            onClick={clearPreview}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
            type="button"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Loading State */}
      <AnimatePresence mode="wait">
        {preview.loading && (
          <motion.div
            key="loading"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="w-full max-w-xl"
          >
            <div className="flex items-center justify-center gap-2 py-4 text-slate-600">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
              <span className="text-sm">Fetching video info...</span>
            </div>
          </motion.div>
        )}

        {/* Error State */}
        {preview.error && !preview.loading && (
          <motion.div
            key="error"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="w-full max-w-xl"
          >
            <div className="flex items-center justify-center gap-2 py-3 px-4 bg-red-50 rounded-xl border border-red-200">
              <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm text-red-600">{preview.error}</span>
            </div>
          </motion.div>
        )}

        {/* Preview State */}
        {preview.video && !preview.loading && (
          <motion.div
            key="preview"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="w-full max-w-xl"
          >
            <div className="bg-white rounded-xl overflow-hidden shadow-sm border border-slate-200">
              {/* YouTube Player Preview */}
              {preview.video.youtube_video_id && (
                <div className="aspect-video">
                  <YouTubePlayer
                    videoId={preview.video.youtube_video_id}
                    className="w-full h-full"
                  />
                </div>
              )}

              {/* Video Info */}
              <div className="p-4">
                <h3 className="font-medium text-slate-800 text-sm line-clamp-2 mb-2">
                  {preview.video.title || "Untitled Video"}
                </h3>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  {preview.video.duration_seconds && (
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      {formatDuration(preview.video.duration_seconds)}
                    </span>
                  )}
                  <span className="flex items-center gap-1 text-emerald-600">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Ready to generate clips
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* File Upload Option */}
      <div className="flex gap-3 text-xs justify-center">
        <label className="px-4 py-2 rounded-full bg-white cursor-pointer border border-slate-200 hover:border-primary/40 transition-colors">
          Upload
          <input
            type="file"
            className="hidden"
            accept="video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {file && (
          <span className="px-3 py-2 rounded-full bg-emerald-100 text-emerald-700 text-xs flex items-center gap-2">
            {file.name.slice(0, 20)}...
            <button
              onClick={() => setFile(null)}
              className="hover:text-emerald-900"
              type="button"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </span>
        )}
      </div>

      {/* Submit Button */}
      <motion.button
        onClick={handleSubmit}
        disabled={loading || preview.loading}
        className="w-full max-w-xl inline-flex items-center justify-center rounded-full bg-primary text-white px-6 py-3 text-sm font-semibold shadow-md disabled:opacity-60"
        whileHover={{ scale: loading || preview.loading ? 1 : 1.02 }}
        whileTap={{ scale: loading || preview.loading ? 1 : 0.97 }}
      >
        {loading ? "Processing..." : "Get Clips"}
      </motion.button>

      {status && <div className="text-xs text-slate-600 text-center">{status}</div>}
    </motion.div>
  );
};

export default UploadCard;
