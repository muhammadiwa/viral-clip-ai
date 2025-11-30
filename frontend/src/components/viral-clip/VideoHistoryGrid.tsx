import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { VideoSource } from "../../types/api";
import { motion } from "framer-motion";

type Props = {
  selectedId?: number;
  onSelect: (video: VideoSource) => void;
};

const statusColor: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  processing: "bg-blue-100 text-blue-700",
  analyzed: "bg-indigo-100 text-indigo-700",
  ready: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700"
};

const VideoHistoryGrid: React.FC<Props> = ({ selectedId, onSelect }) => {
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

  return (
    <div className="mt-6">
      <div className="text-sm font-semibold mb-3">Recent videos</div>
      <div className="grid grid-cols-4 gap-4">
        {data.map((v) => (
          <motion.button
            key={v.id}
            onClick={() => onSelect(v)}
            className={`rounded-2xl bg-white shadow-sm text-left overflow-hidden border transition-all ${
              selectedId === v.id ? "border-primary shadow-md shadow-primary/10" : "border-transparent"
            }`}
            whileHover={{ y: -3 }}
          >
            <div className="h-32 bg-slate-200 flex items-center justify-center text-xs text-slate-600 grain relative overflow-hidden">
              {v.thumbnail_path ? (
                <img
                  src={v.thumbnail_path}
                  alt={v.title || "Video thumbnail"}
                  className="w-full h-full object-cover"
                />
              ) : (
                <>
                  <span className="z-10">No thumbnail</span>
                  <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-black/5" />
                </>
              )}
            </div>
            <div className="p-3 space-y-1">
              <div className="text-xs font-semibold line-clamp-2">
                {v.title || "Untitled video"}
              </div>
              <div className="text-[11px] text-slate-500 flex justify-between items-center">
                <span className="capitalize">{v.source_type}</span>
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusColor[v.status] || "bg-slate-100 text-slate-700"}`}
                >
                  {v.status}
                </span>
              </div>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
};

export default VideoHistoryGrid;
