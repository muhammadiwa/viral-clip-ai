import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { ClipDetail, SubtitleSegment } from "../../types/api";
import { motion, AnimatePresence } from "framer-motion";

type Props = {
  clipId?: number;
  open: boolean;
  onClose: () => void;
};

const ClipDetailModal: React.FC<Props> = ({ clipId, open, onClose }) => {
  const { data: clip, isLoading } = useQuery<ClipDetail>({
    queryKey: ["clip-detail", clipId],
    queryFn: async () => {
      const res = await api.get(`/viral-clip/clips/${clipId}`);
      return res.data;
    },
    enabled: open && Boolean(clipId)
  });

  const { data: subtitles } = useQuery<SubtitleSegment[]>({
    queryKey: ["subtitles", clipId],
    queryFn: async () => {
      const res = await api.get(`/viral-clip/clips/${clipId}/subtitles`);
      return res.data;
    },
    enabled: open && Boolean(clipId)
  });

  const hasVideo = Boolean(clip?.video_path);
  const downloadUrl = `${api.defaults.baseURL}/viral-clip/clips/${clipId}/download`;
  const srtUrl = `${api.defaults.baseURL}/viral-clip/clips/${clipId}/subtitles.srt`;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="w-full max-w-4xl bg-white rounded-3xl shadow-xl overflow-hidden"
            initial={{ scale: 0.96, y: 12 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.98, y: 8 }}
          >
            <div className="p-6 flex gap-6">
              <div className="flex-shrink-0 space-y-4">
                <div className="w-[280px] aspect-[9/16] rounded-2xl bg-black overflow-hidden flex items-center justify-center text-sm text-slate-600">
                  {hasVideo ? (
                    <video
                      className="w-full h-full object-cover"
                      controls
                      src={clip?.video_path!}
                    />
                  ) : (
                    <div className="grain w-full h-full flex items-center justify-center text-white/60">
                      {clip?.status === "ready" ? "Video preview" : "Video generating..."}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex-1 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold">{clip?.title || "Clip detail"}</div>
                    <div className="text-xs text-slate-500">
                      {clip?.duration_sec ? `${Math.round(clip.duration_sec)}s • ${clip?.language || "EN"}` : ""}
                    </div>
                  </div>
                  <button onClick={onClose} className="text-xs text-slate-500 hover:text-slate-800">
                    Close
                  </button>
                </div>
                <div className="text-xs text-slate-600">{clip?.description}</div>
                <div className="flex items-center gap-3">
                  <div className="text-2xl font-bold text-primary">
                    {clip?.viral_score?.toFixed(1) ?? "7.5"}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Hook {clip?.viral_breakdown?.hook || "A"} • Flow {clip?.viral_breakdown?.flow || "A-"}<br />
                    Value {clip?.viral_breakdown?.value || "A"} • Trend {clip?.viral_breakdown?.trend || "B+"}
                  </div>
                </div>
                <div className={`inline-flex px-3 py-1 rounded-full text-xs font-medium ${
                  clip?.status === "ready" 
                    ? "bg-emerald-100 text-emerald-700" 
                    : "bg-amber-100 text-amber-700"
                }`}>
                  {clip?.status === "ready" ? "Ready to download" : `Status: ${clip?.status}`}
                </div>
                <div className="p-3 rounded-xl bg-slate-50 text-xs text-slate-600">
                  {clip?.transcript_preview || "Transcript preview unavailable."}
                </div>
                <div className="border rounded-xl p-3 text-xs space-y-2">
                  <div className="font-semibold text-slate-700">Subtitle segments</div>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {subtitles && subtitles.length > 0 ? (
                      subtitles.map((sub) => (
                        <div key={sub.id} className="flex justify-between gap-2">
                          <span className="text-[11px] text-slate-500">
                            {sub.start_time_sec.toFixed(1)}–{sub.end_time_sec.toFixed(1)}
                          </span>
                          <span className="text-[12px] text-slate-800 flex-1 text-right">{sub.text}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-slate-400">No subtitles yet.</div>
                    )}
                  </div>
                </div>
                <div className="flex gap-3">
                  {hasVideo ? (
                    <a
                      href={downloadUrl}
                      className="flex-1 text-center rounded-full bg-primary text-white py-2 text-xs font-semibold"
                    >
                      Download MP4
                    </a>
                  ) : (
                    <button
                      disabled
                      className="flex-1 rounded-full bg-slate-300 text-slate-500 py-2 text-xs font-semibold cursor-not-allowed"
                    >
                      Video not ready
                    </button>
                  )}
                  <a
                    href={srtUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 text-center rounded-full border border-slate-300 py-2 text-xs font-semibold text-slate-700"
                  >
                    Download SRT
                  </a>
                </div>
              </div>
            </div>
            {isLoading && <div className="p-4 text-sm text-slate-500 text-center">Loading clip details…</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ClipDetailModal;
