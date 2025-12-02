import React from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { VideoSource } from "../../types/api";
import { motion } from "framer-motion";

type Props = {
  selectedId?: number;
  onSelect?: (video: VideoSource) => void;
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

  // Check if video is ready to be selected (not processing/pending)
  const isVideoReady = (status: string) => {
    return status === "ready" || status === "analyzed";
  };

  return (
    <div className="mt-6">
      <div className="text-sm font-semibold mb-3">Recent videos</div>
      <div className="grid grid-cols-4 gap-4">
        {data.map((v) => {
          const canSelect = isVideoReady(v.status);

          const handleClick = () => {
            if (canSelect) {
              // Navigate to video detail page
              navigate(`/video/${v.id}`);
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
              title={!canSelect ? "Video masih diproses, tunggu sampai selesai" : ""}
            >
              <div className="h-32 bg-slate-200 flex items-center justify-center text-xs text-slate-600 grain relative overflow-hidden">
                {v.thumbnail_path ? (
                  <img
                    src={v.thumbnail_path}
                    alt={v.title || "Video thumbnail"}
                    className={`w-full h-full object-cover ${!canSelect ? "grayscale-[30%]" : ""}`}
                  />
                ) : (
                  <>
                    <span className="z-10">No thumbnail</span>
                    <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-black/5" />
                  </>
                )}
                {/* Processing overlay */}
                {!canSelect && (
                  <div className="absolute inset-0 bg-black/20 flex items-center justify-center">
                    <div className="bg-white/90 rounded-full px-3 py-1.5 flex items-center gap-2">
                      <svg className="animate-spin h-3 w-3 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span className="text-[10px] font-medium text-slate-700">Processing...</span>
                    </div>
                  </div>
                )}
              </div>
              <div className="p-3 space-y-1">
                <div className="text-xs font-semibold line-clamp-2">
                  {v.title || "Untitled video"}
                </div>
                <div className="text-[11px] text-slate-500">
                  <span className="capitalize">{v.source_type}</span>
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
