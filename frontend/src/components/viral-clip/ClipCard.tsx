import React from "react";
import { motion } from "framer-motion";
import { Clip } from "../../types/api";

type Props = {
  clip: Clip;
  onSelect: () => void;
  active: boolean;
  exportLink?: string | null;
  srtLink?: string | null;
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

const ClipCard: React.FC<Props> = ({ clip, onSelect, active, exportLink, srtLink }) => {
  return (
    <motion.button
      onClick={onSelect}
      className={`relative rounded-2xl border text-left overflow-hidden bg-white shadow-sm ${
        active ? "border-primary shadow-lg shadow-primary/10" : "border-slate-200"
      }`}
      whileHover={{ y: -3 }}
    >
      <div
        className="h-36 bg-slate-100 grain flex items-center justify-center text-xs text-slate-600"
        style={
          clip.thumbnail_path
            ? { backgroundImage: `url(${clip.thumbnail_path})`, backgroundSize: "cover", backgroundPosition: "center" }
            : undefined
        }
      >
        {!clip.thumbnail_path && "Preview"}
      </div>
      <div className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/70 text-white px-2 py-1 text-[11px]">
        <span className="font-semibold">{clip.viral_score?.toFixed(1) ?? "7.2"}</span>
        <span className="text-[10px] opacity-70">viral</span>
      </div>
      <div className="absolute top-2 right-2 text-[11px] bg-white/90 text-slate-700 rounded-full px-2 py-1">
        {formatDuration(clip.duration_sec)}
      </div>
      <div className="p-3 space-y-1">
        <div className="text-sm font-semibold line-clamp-2">{clip.title || "Viral moment"}</div>
        <div className="text-[11px] text-slate-500 flex items-center gap-2">
          <span className="uppercase tracking-wide">{clip.language || "EN"}</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-100 capitalize">{clip.status}</span>
        </div>
        <div className="flex gap-2 text-[11px]">
          {exportLink && (
            <a
              href={exportLink}
              target="_blank"
              rel="noreferrer"
              className="px-2 py-1 rounded-md bg-primary/10 text-primary font-semibold"
              onClick={(e) => e.stopPropagation()}
            >
              MP4
            </a>
          )}
          {srtLink && (
            <a
              href={srtLink}
              target="_blank"
              rel="noreferrer"
              className="px-2 py-1 rounded-md bg-slate-100 text-slate-700"
              onClick={(e) => e.stopPropagation()}
            >
              SRT
            </a>
          )}
        </div>
      </div>
    </motion.button>
  );
};

export default ClipCard;
