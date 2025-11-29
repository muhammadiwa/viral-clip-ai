import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { VideoSource } from "../../types/api";
import { motion } from "framer-motion";

type Props = {
  selectedId?: number;
  onSelect: (video: VideoSource) => void;
};

const VideoHistoryGrid: React.FC<Props> = ({ selectedId, onSelect }) => {
  const { data, isLoading } = useQuery<VideoSource[]>({
    queryKey: ["videos"],
    queryFn: async () => {
      const res = await api.get("/viral-clip/videos");
      return res.data;
    }
  });

  if (isLoading) {
    return <div className="mt-6 text-sm text-slate-500">Loading videos…</div>;
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
            className={`rounded-2xl bg-white shadow-sm text-left overflow-hidden border ${
              selectedId === v.id ? "border-primary" : "border-transparent"
            }`}
            whileHover={{ y: -3 }}
          >
            <div className="h-32 bg-slate-200 flex items-center justify-center text-xs text-slate-600">
              Thumbnail
            </div>
            <div className="p-3 space-y-1">
              <div className="text-xs font-semibold line-clamp-2">
                {v.title || "Untitled video"}
              </div>
              <div className="text-[11px] text-slate-500 flex justify-between">
                <span className="capitalize">{v.source_type}</span>
                <span>{v.status}</span>
              </div>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
};

export default VideoHistoryGrid;
