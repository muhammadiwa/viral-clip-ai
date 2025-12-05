import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api } from "../../lib/apiClient";
import { useQueryClient } from "@tanstack/react-query";
import { VideoSource, VideoCreateResponse } from "../../types/api";
import { useNavigate } from "react-router-dom";

type Props = {
  onVideoCreated: (video?: VideoSource, jobId?: number) => void;
};

// Response type for instant YouTube endpoint
type VideoInstantResponse = {
  video: VideoSource;
  is_existing: boolean;
};

/**
 * Extract YouTube video ID from various URL formats.
 * Returns null if URL is not a valid YouTube URL.
 * 
 * Supports:
 * - youtube.com/watch?v=VIDEO_ID
 * - youtu.be/VIDEO_ID
 * - youtube.com/embed/VIDEO_ID
 * - youtube.com/shorts/VIDEO_ID
 * - Direct VIDEO_ID (11 characters)
 * 
 * Requirements: 2.3
 */
const extractYouTubeVideoId = (url: string): string | null => {
  if (!url || !url.trim()) return null;

  const trimmedUrl = url.trim();

  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/,
  ];

  for (const pattern of patterns) {
    const match = trimmedUrl.match(pattern);
    if (match) return match[1];
  }
  return null;
};

const UploadCard: React.FC<Props> = ({ onVideoCreated }) => {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();

  // Validate URL format on input change (frontend only, no API call)
  // Requirements: 2.3, 2.4, 2.5
  useEffect(() => {
    if (!youtubeUrl.trim()) {
      setValidationError(null);
      return;
    }

    const videoId = extractYouTubeVideoId(youtubeUrl);
    if (!videoId) {
      setValidationError("Invalid YouTube URL format");
    } else {
      setValidationError(null);
    }
  }, [youtubeUrl]);

  // Clear validation when switching to file upload
  useEffect(() => {
    if (file) {
      setYoutubeUrl("");
      setValidationError(null);
    }
  }, [file]);

  // Check if URL is valid for enabling the button
  const isValidYoutubeUrl = youtubeUrl.trim() !== "" && extractYouTubeVideoId(youtubeUrl) !== null;

  // Handle "Get Clips" button click
  // Requirements: 5.1, 5.2, 5.3, 5.4
  const handleGetClips = async () => {
    if (!isValidYoutubeUrl) {
      setStatus("Please enter a valid YouTube URL.");
      return;
    }

    setLoading(true);
    setStatus(null);

    try {
      const form = new FormData();
      form.append("youtube_url", youtubeUrl);

      // Call POST /viral-clip/video/youtube/instant only when button clicked
      const res = await api.post<VideoInstantResponse>("/viral-clip/video/youtube/instant", form);

      // On success (new or existing video), redirect to video detail page
      const video = res.data.video;

      // Clear form state
      setYoutubeUrl("");
      await qc.invalidateQueries({ queryKey: ["videos"] });

      // Redirect to video detail page using slug
      navigate(`/ai-viral-clip/video/${video.slug}`);
    } catch (err: any) {
      // Show error message if API fails
      const errorMessage = err?.response?.data?.detail || "Failed to process video. Please try again.";
      setStatus(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Handle file upload submit (legacy flow)
  const handleFileSubmit = async () => {
    if (!file) {
      setStatus("Please choose a file first.");
      return;
    }

    setLoading(true);
    setStatus(null);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.post<VideoCreateResponse>("/viral-clip/video/upload", form);
      onVideoCreated(res.data.video, res.data.job?.id);
      setFile(null);
      await qc.invalidateQueries({ queryKey: ["videos"] });
      setStatus("Video uploaded! Processing will start automatically.");
    } catch (err: any) {
      setStatus(err?.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const clearUrl = () => {
    setYoutubeUrl("");
    setValidationError(null);
    setStatus(null);
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
          className={`w-full rounded-xl border border-dashed ${validationError ? "border-red-400" : "border-primary/40"
            } bg-white/80 px-4 py-3 text-sm outline-none focus:ring-2 ${validationError ? "focus:ring-red-400" : "focus:ring-primary/40"
            } text-center pr-10`}
          placeholder="Drop a YouTube link or paste URL..."
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          disabled={!!file || loading}
        />
        {youtubeUrl && (
          <button
            onClick={clearUrl}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
            type="button"
            disabled={loading}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Inline Validation Error - Requirements: 2.5 */}
      {validationError && youtubeUrl && (
        <div className="w-full max-w-xl">
          <div className="flex items-center justify-center gap-2 py-2 px-4 bg-red-50 rounded-xl border border-red-200">
            <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm text-red-600">{validationError}</span>
          </div>
        </div>
      )}

      {/* File Upload Option */}
      <div className="flex gap-3 text-xs justify-center">
        <label className="px-4 py-2 rounded-full bg-white cursor-pointer border border-slate-200 hover:border-primary/40 transition-colors">
          Upload
          <input
            type="file"
            className="hidden"
            accept="video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={loading}
          />
        </label>
        {file && (
          <span className="px-3 py-2 rounded-full bg-emerald-100 text-emerald-700 text-xs flex items-center gap-2">
            {file.name.slice(0, 20)}...
            <button
              onClick={() => setFile(null)}
              className="hover:text-emerald-900"
              type="button"
              disabled={loading}
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </span>
        )}
      </div>

      {/* Submit Button - Requirements: 2.4 */}
      <motion.button
        onClick={file ? handleFileSubmit : handleGetClips}
        disabled={loading || (!file && !isValidYoutubeUrl)}
        className="w-full max-w-xl inline-flex items-center justify-center rounded-full bg-primary text-white px-6 py-3 text-sm font-semibold shadow-md disabled:opacity-60"
        whileHover={{ scale: loading ? 1 : 1.02 }}
        whileTap={{ scale: loading ? 1 : 0.97 }}
      >
        {loading ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
            Processing...
          </>
        ) : (
          "Get Clips"
        )}
      </motion.button>

      {status && <div className="text-xs text-slate-600 text-center">{status}</div>}
    </motion.div>
  );
};

export default UploadCard;
