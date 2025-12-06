import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { VideoSource } from "../../types/api";
import { motion } from "framer-motion";

type Props = {
  selectedId?: number;
  onSelect?: (video: VideoSource) => void;
};

// Status badge component - only show for active states (downloading, processing, failed)
const StatusBadge: React.FC<{ video: VideoSource }> = ({ video }) => {
  // Determine status based on video state - only show important states
  const getStatusInfo = () => {
    // Show downloading progress
    if (video.youtube_video_id && !video.is_downloaded) {
      if (video.download_progress > 0 && video.download_progress < 100) {
        return {
          label: `Downloading ${Math.round(video.download_progress)}%`,
          color: "bg-blue-100 text-blue-700",
          icon: (
            <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )
        };
      }
      // Don't show "Ready to Generate" badge - it's unnecessary
      return null;
    }

    // Check processing status - only show for active processing or failed
    switch (video.status) {
      case "pending":
      case "processing":
        return {
          label: "Processing",
          color: "bg-amber-100 text-amber-700",
          icon: (
            <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )
        };
      case "failed":
        return {
          label: "Failed",
          color: "bg-red-100 text-red-700",
          icon: (
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )
        };
      // Don't show badge for ready/analyzed - it's the normal state
      default:
        return null;
    }
  };

  const statusInfo = getStatusInfo();
  if (!statusInfo) return null;

  return (
    <div className={`absolute top-2 right-2 rounded-full px-2 py-1 flex items-center gap-1 text-[10px] font-medium ${statusInfo.color}`}>
      {statusInfo.icon}
      <span>{statusInfo.label}</span>
    </div>
  );
};

// Thumbnail component with fallback support (Requirement 3.1, 3.2, 3.3)
const VideoThumbnail: React.FC<{ video: VideoSource; canSelect: boolean }> = ({ video, canSelect }) => {
  const [imageError, setImageError] = useState(false);

  // Determine which thumbnail URL to use
  const getThumbnailUrl = (): string | null => {
    // For YouTube videos, prefer youtube_thumbnail_url (Requirement 3.1)
    if (video.youtube_video_id && video.youtube_thumbnail_url && !imageError) {
      return video.youtube_thumbnail_url;
    }
    // For local uploads or as fallback, use thumbnail_path (Requirement 3.3)
    if (video.thumbnail_path && !imageError) {
      return video.thumbnail_path;
    }
    return null;
  };

  const thumbnailUrl = getThumbnailUrl();

  const handleImageError = () => {
    // Fallback for failed thumbnail loads (Requirement 3.2)
    setImageError(true);
  };

  if (thumbnailUrl) {
    return (
      <img
        src={thumbnailUrl}
        alt={video.title || "Video thumbnail"}
        className={`w-full h-full object-cover ${!canSelect ? "grayscale-[30%]" : ""}`}
        onError={handleImageError}
      />
    );
  }

  // Fallback placeholder when no thumbnail available (Requirement 3.2)
  return (
    <>
      <div className="flex flex-col items-center justify-center gap-1 z-10">
        <svg className="h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        <span className="text-[10px]">No thumbnail</span>
      </div>
      <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-black/5" />
    </>
  );
};

const VideoHistoryGrid: React.FC<Props> = ({ selectedId, onSelect }) => {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery<VideoSource[]>({
    queryKey: ["videos"],
    queryFn: async () => {
      const res = await api.get("/viral-clip/videos");
      return res.data;
    },
    refetchInterval: 5000
  });

  if (isLoading) {
    return <div className="mt-6 text-sm text-slate-500">Loading videos…</div>;
  }

  if (error) {
    return (
      <div className="mt-6 text-sm text-rose-600">
        Failed to load videos. Please ensure backend is running.
      </div>
    );
  }

  if (!data || data.length === 0) {
    return <div className="mt-6 text-sm text-slate-500">No videos yet.</div>;
  }

  // Check if video is ready to be selected
  // All videos are selectable except failed ones
  const isVideoSelectable = (video: VideoSource) => {
    // Failed videos cannot be selected
    if (video.status === "failed") return false;
    // All other videos are selectable (including YouTube videos not yet downloaded)
    return true;
  };

  return (
    <div className="mt-6">
      <div className="text-sm font-semibold mb-3">Recent videos</div>
      <div className="grid grid-cols-4 gap-4">
        {data.map((v) => {
          const canSelect = isVideoSelectable(v);

          const handleClick = () => {
            if (canSelect) {
              // Navigate to video detail page using slug or fallback to ID (Requirement 6.4)
              const identifier = v.slug || `id-${v.id}`;
              navigate(`/ai-viral-clip/video/${identifier}`);
              // Also call onSelect if provided (for backward compatibility)
              onSelect?.(v);
            }
          };

          return (
            <motion.button
              key={v.id}
              onClick={handleClick}
              disabled={!canSelect}
              className={`rounded-2xl bg-white shadow-sm text-left overflow-hidden border transition-all ${selectedId === v.id ? "border-primary shadow-md shadow-primary/10" : "border-transparent"
                } ${!canSelect ? "opacity-70 cursor-not-allowed" : "cursor-pointer"}`}
              whileHover={canSelect ? { y: -3 } : {}}
              title={!canSelect ? "Video sedang diproses, tunggu sampai selesai" : ""}
            >
              <div className="aspect-video bg-slate-200 flex items-center justify-center text-xs text-slate-600 grain relative overflow-hidden">
                <VideoThumbnail video={v} canSelect={canSelect} />
                <StatusBadge video={v} />
              </div>
              <div className="p-3 space-y-1">
                <div className="text-xs font-semibold line-clamp-2">
                  {v.title || "Untitled video"}
                </div>
                <div className="text-[11px] text-slate-500">
                  <span className="capitalize">{v.source_type}</span>
                  {v.youtube_video_id && (
                    <span className="ml-1 text-red-500">• YouTube</span>
                  )}
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
};

export default VideoHistoryGrid;
