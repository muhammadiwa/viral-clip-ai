import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { ClipDetail, SubtitleSegment, ExportJob } from "../../types/api";
import { motion, AnimatePresence } from "framer-motion";

type Props = {
  clipId?: number;
  open: boolean;
  onClose: () => void;
};

const ExportStatus: React.FC<{ clipId?: number }> = ({ clipId }) => {
  const { data, refetch } = useQuery<ExportJob[]>({
    queryKey: ["exports", clipId],
    queryFn: async () => {
      const res = await api.get(`/viral-clip/clips/${clipId}/exports`);
      return res.data;
    },
    enabled: Boolean(clipId),
    refetchInterval: 4000
  });

  if (!clipId) return null;
  return (
    <div className="mt-3 border rounded-lg p-3 text-xs space-y-2">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-slate-700">Export Jobs</div>
        <button className="text-[11px] text-primary" onClick={() => refetch()}>
          Refresh
        </button>
      </div>
      {data && data.length > 0 ? (
        data.map((exp) => (
          <div key={exp.id} className="flex items-center justify-between">
            <div>
              #{exp.id} • {exp.status}
              {exp.output_path && (
                <a
                  href={
                    exp.output_path.startsWith("http")
                      ? exp.output_path
                      : `${api.defaults.baseURL}/exports/${exp.id}/download`
                  }
                  className="ml-2 text-primary"
                  target="_blank"
                  rel="noreferrer"
                >
                  Download
                </a>
              )}
            </div>
            {exp.error_message && <span className="text-rose-600">{exp.error_message}</span>}
          </div>
        ))
      ) : (
        <div className="text-slate-500">No exports yet.</div>
      )}
    </div>
  );
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

  const exportMutation = useMutation<{ export: { id: number } }>({
    mutationFn: async () => {
      const res = await api.post(`/viral-clip/clips/${clipId}/exports`, {
        resolution: "1080p",
        fps: 30,
        aspect_ratio: "9:16",
        use_brand_kit: true,
        use_ai_dub: true
      });
      return res.data;
    },
    onSuccess: (data) => {
      if (data?.job?.id) setExportJobId(data.job.id);
    }
  });
  const [exportJobId, setExportJobId] = React.useState<number | null>(null);

  useQuery({
    queryKey: ["job", exportJobId],
    enabled: Boolean(exportJobId),
    queryFn: async () => {
      const res = await api.get(`/viral-clip/jobs/${exportJobId}`);
      return res.data;
    },
    refetchInterval: exportJobId ? 3000 : false,
    onSuccess: async (job) => {
      if (job.status === "completed" || job.status === "failed") {
        setExportJobId(null);
        await api.get(`/viral-clip/clips/${clipId}/exports`); // warm cache
      }
    }
  });

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
            <div className="p-6 grid grid-cols-3 gap-6">
              <div className="col-span-2 space-y-4">
                <div className="h-64 rounded-2xl bg-slate-100 overflow-hidden flex items-center justify-center text-sm text-slate-600">
                  {clip?.video_source_id ? (
                    <video
                      className="w-full h-full object-cover"
                      controls
                      src={`${api.defaults.baseURL}/viral-clip/videos/${clip.video_source_id}/download`}
                    />
                  ) : (
                    <div className="grain w-full h-full flex items-center justify-center">Clip preview</div>
                  )}
                </div>
                <div className="p-4 rounded-2xl bg-slate-50 text-xs space-y-2">
                  <div className="flex items-center gap-4">
                    <div className="text-2xl font-semibold text-primary">
                      {clip?.viral_score?.toFixed(1) ?? "7.5"}
                    </div>
                    <div className="text-slate-500">
                      Hook {clip?.viral_breakdown?.hook || "A"} • Flow {clip?.viral_breakdown?.flow || "A-"} • Value{" "}
                      {clip?.viral_breakdown?.value || "A"} • Trend {clip?.viral_breakdown?.trend || "B+"}
                    </div>
                  </div>
                  <div className="text-slate-600">{clip?.transcript_preview || "Transcript preview unavailable."}</div>
                </div>
              </div>
              <div className="col-span-1 space-y-3">
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
                  <button
                    onClick={() => exportMutation.mutate()}
                    disabled={exportMutation.isPending}
                    className="flex-1 rounded-full bg-slate-900 text-white py-2 text-xs font-semibold disabled:opacity-60"
                  >
                    {exportMutation.isPending ? "Queueing…" : "Queue Export"}
                  </button>
                  <a
                    href={`${api.defaults.baseURL}/viral-clip/clips/${clipId}/subtitles.srt`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 text-center rounded-full border border-slate-300 py-2 text-xs font-semibold text-slate-700"
                  >
                    Download SRT
                  </a>
                </div>
                {exportMutation.isSuccess && (
                  <div className="text-[11px] text-emerald-600">
                    Export job queued. Check /exports/{exportMutation.data?.export?.id || ""}
                  </div>
                )}
                <ExportStatus clipId={clipId} />
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
