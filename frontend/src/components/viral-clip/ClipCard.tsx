import React from "react";
import { motion } from "framer-motion";
import { Clip } from "../../types/api";
import { api } from "../../lib/apiClient";

type Props = {
  clip: Clip;
  onSelect: () => void;
  active: boolean;
};

const formatDuration = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${mins}:${secs}`;
};

const ClipCard: React.FC<Props> = ({ clip, onSelect, active }) => {
  const hasVideo = Boolean(clip.video_path);
  const downloadUrl = `${api.defaults.baseURL}/viral-clip/clips/${clip.id}/download`;
  const srtUrl = `${api.defaults.baseURL}/viral-clip/clips/${clip.id}/subtitles.srt`;

  return (
    <motion.button
      onClick={onSelect}
      className={`relative rounded-2xl border text-left overflow-hidden bg-white shadow-sm ${active ? "border-primary shadow-lg shadow-primary/10" : "border-slate-200"
        }`}
      whileHover={{ y: -3 }}
    >
      <div className="aspect-[9/16] bg-black flex items-center justify-center text-xs text-slate-400 relative overflow-hidden">
        {hasVideo ? (
          <video
            className="w-full h-full object-cover"
            src={clip.video_path!}
            muted
            preload="metadata"
            onMouseEnter={(e) => (e.target as HTMLVideoElement).play()}
            onMouseLeave={(e) => {
              const video = e.target as HTMLVideoElement;
              video.pause();
              video.currentTime = 0;
            }}
          />
        ) : clip.thumbnail_path ? (
          <div
            className="w-full h-full"
            style={{
              backgroundImage: `url(${clip.thumbnail_path})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          />
        ) : (
          "Preview"
        )}
      </div>
      <div className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/70 text-white px-2 py-1 text-[11px]">
        <span className="font-semibold">{clip.viral_score?.toFixed(1) ?? "7.2"}</span>
        <span className="text-[10px] opacity-70">viral</span>
      </div>
      <div className="absolute top-2 right-2 text-[11px] bg-white/90 text-slate-700 rounded-full px-2 py-1">
        {formatDuration(clip.duration_sec)}
      </div>
      <div className="p-3 space-y-2">
        <div className="text-sm font-semibold line-clamp-2">{clip.title || "Viral moment"}</div>
        {clip.description && (
          <div className="text-[11px] text-slate-600 line-clamp-2">{clip.description}</div>
        )}
        <div className="text-[11px] text-slate-500 flex items-center gap-2">
          <span className="uppercase tracking-wide">{clip.language || "EN"}</span>
          {clip.status !== "ready" && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
              <svg className="animate-spin h-2.5 w-2.5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              Processing
            </span>
          )}
        </div>
        <div className="flex gap-2 text-[11px]">
          {hasVideo && (
            <a
              href={downloadUrl}
              className="px-2 py-1 rounded-md bg-primary/10 text-primary font-semibold"
              onClick={(e) => e.stopPropagation()}
            >
              Download MP4
            </a>
          )}
          <a
            href={srtUrl}
            target="_blank"
            rel="noreferrer"
            className="px-2 py-1 rounded-md bg-slate-100 text-slate-700"
            onClick={(e) => e.stopPropagation()}
          >
            SRT
          </a>
        </div>
      </div>
    </motion.button>
  );
};

export default ClipCard;
