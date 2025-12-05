import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { SubtitleStyle, VideoSource } from "../../types/api";
import { motion } from "framer-motion";

type Props = {
  video?: VideoSource;
  onBatchCreated: (batchId: number) => void;
};

const AiClippingPanel: React.FC<Props> = ({ video, onBatchCreated }) => {
  const [videoType, setVideoType] = useState("podcast");
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [clipLengthPreset, setClipLengthPreset] = useState("auto_0_60");
  const [subtitleEnabled, setSubtitleEnabled] = useState(true);
  const [includeMoments, setIncludeMoments] = useState("");
  const [timeframe, setTimeframe] = useState<[number, number]>([0, 90]);
  const qc = useQueryClient();
  const [batchJobId, setBatchJobId] = useState<number | null>(null);
  const [batchProgress, setBatchProgress] = useState<string | null>(null);
  const maxTime = Math.max(60, Math.ceil(video?.duration_seconds ?? 180));

  useEffect(() => {
    setTimeframe([0, Math.min(90, maxTime)]);
  }, [video?.id]);

  const { data: styles } = useQuery<SubtitleStyle[]>({
    queryKey: ["subtitle-styles"],
    queryFn: async () => {
      const res = await api.get("/subtitle-styles");
      return res.data;
    },
    enabled: Boolean(video)
  });

  const [selectedStyleId, setSelectedStyleId] = useState<number | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!video) return null;
      const res = await api.post(`/viral-clip/videos/${video.id}/clip-batches`, {
        video_type: videoType,
        aspect_ratio: aspectRatio,
        clip_length_preset: clipLengthPreset,
        subtitle_enabled: subtitleEnabled,
        subtitle_style_id: selectedStyleId,
        include_specific_moments: includeMoments,
        processing_timeframe_start: timeframe[0],
        processing_timeframe_end: timeframe[1]
      });
      return res.data;
    },
    onSuccess: async (data) => {
      if (data?.batch?.id) {
        onBatchCreated(data.batch.id);
      }
      if (data?.job?.id) {
        setBatchJobId(data.job.id);
      }
      await qc.invalidateQueries({ queryKey: ["clip-batches", video?.id] });
    }
  });

  const { data: jobData } = useQuery({
    queryKey: ["job", batchJobId],
    enabled: Boolean(batchJobId),
    queryFn: async () => {
      const res = await api.get(`/viral-clip/jobs/${batchJobId}`);
      return res.data;
    },
    refetchInterval: batchJobId ? 3000 : false,
  });

  // Handle job status updates (replaces deprecated onSuccess)
  useEffect(() => {
    if (jobData) {
      setBatchProgress(`${jobData.status} ${jobData.progress?.toFixed?.(0) ?? ""}%`);
      if (jobData.status === "completed" || jobData.status === "failed") {
        setBatchJobId(null);
      }
    }
  }, [jobData]);

  const selectedStyle = useMemo(
    () => styles?.find((s) => s.id === selectedStyleId) || styles?.find((s) => s.is_default_global),
    [styles, selectedStyleId]
  );

  if (!video) return null;

  // Check if video is ready for clip generation
  const isVideoReady = video.status === "ready" || video.status === "analyzed";
  const isProcessing = video.status === "processing" || video.status === "pending";

  return (
    <section className="mt-8 rounded-3xl bg-white p-5 shadow-sm border border-slate-100">
      <div className="flex items-center gap-4 mb-4">
        <div className="h-16 w-28 bg-slate-200 rounded-lg flex items-center justify-center text-xs text-slate-600 grain relative overflow-hidden">
          {video.thumbnail_path ? (
            <img
              src={video.thumbnail_path}
              alt={video.title || "Video thumbnail"}
              className="w-full h-full object-cover"
            />
          ) : (
            <>
              <span className="z-10">No thumbnail</span>
              <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-black/5" />
            </>
          )}
        </div>
        <div>
          <div className="text-sm font-semibold">{video.title || "Untitled video"}</div>
          <div className="text-xs text-slate-500">
            Source: {video.source_type} • Status: {video.status}
            {batchProgress ? ` • Batch: ${batchProgress}` : ""}
          </div>
        </div>
      </div>

      {/* Processing Warning Banner */}
      {isProcessing && (
        <div className="mb-4 p-3 rounded-xl bg-blue-50 border border-blue-200 flex items-center gap-3">
          <svg className="animate-spin h-5 w-5 text-blue-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <div>
            <div className="text-sm font-medium text-blue-800">Video sedang diproses</div>
            <div className="text-xs text-blue-600">Tunggu sampai proses selesai sebelum generate clips</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 text-xs">
        <div>
          <label className="block mb-1 text-slate-500">Video type</label>
          <select
            className="w-full rounded-lg border border-slate-200 px-2 py-2"
            value={videoType}
            onChange={(e) => setVideoType(e.target.value)}
          >
            <option value="podcast">Podcast</option>
            <option value="talking_head">Talking head</option>
            <option value="gaming">Gaming</option>
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-500">Aspect ratio</label>
          <select
            className="w-full rounded-lg border border-slate-200 px-2 py-2"
            value={aspectRatio}
            onChange={(e) => setAspectRatio(e.target.value)}
          >
            <option value="9:16">9:16</option>
            <option value="16:9">16:9</option>
            <option value="1:1">1:1</option>
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-500">Clip length</label>
          <select
            className="w-full rounded-lg border border-slate-200 px-2 py-2"
            value={clipLengthPreset}
            onChange={(e) => setClipLengthPreset(e.target.value)}
          >
            <option value="auto_0_60">Auto (0–60s)</option>
            <option value="0_30">0–30s</option>
            <option value="0_90">0–90s</option>
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-500">Subtitle</label>
          <select
            className="w-full rounded-lg border border-slate-200 px-2 py-2"
            value={subtitleEnabled ? "yes" : "no"}
            onChange={(e) => setSubtitleEnabled(e.target.value === "yes")}
          >
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </div>
      </div>

      <div className="mt-6 text-xs">
        <label className="block mb-1 text-slate-500">Include specific moments</label>
        <input
          className="w-full rounded-xl border border-slate-200 px-3 py-2"
          placeholder="e.g. intro joke at 02:10, product pitch at 10:30"
          value={includeMoments}
          onChange={(e) => setIncludeMoments(e.target.value)}
        />
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between text-xs mb-2 text-slate-500">
          <span>Processing timeframe (seconds)</span>
          <span>
            {timeframe[0]}s – {timeframe[1]}s
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <input
            type="range"
            min={0}
            max={timeframe[1]}
            value={timeframe[0]}
            onChange={(e) => setTimeframe([Number(e.target.value), timeframe[1]])}
          />
          <input
            type="range"
            min={timeframe[0]}
            max={maxTime}
            value={timeframe[1]}
            onChange={(e) => setTimeframe([timeframe[0], Number(e.target.value)])}
          />
        </div>
      </div>

      <div className="mt-6">
        <div className="text-xs font-semibold text-slate-600 mb-2">Subtitle Style</div>
        <div className="grid grid-cols-4 gap-3">
          {styles?.map((style) => (
            <button
              key={style.id}
              onClick={() => setSelectedStyleId(style.id)}
              className={`rounded-xl border px-3 py-2 text-left text-xs ${selectedStyleId === style.id ? "border-primary bg-primary/5" : "border-slate-200"
                }`}
            >
              <div className="font-semibold text-slate-800">{style.name}</div>
              <div className="text-[11px] text-slate-500">
                {String(style.style_json.font_family || "Sans")} • {String(style.style_json.position || "bottom")}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <div className="text-xs text-slate-500">
          Selected style: {selectedStyle?.name || "Bold Pop"} • Subtitle {subtitleEnabled ? "enabled" : "disabled"}
        </div>
        <motion.button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !isVideoReady}
          className={`inline-flex items-center justify-center rounded-full px-5 py-3 text-sm font-semibold shadow-md disabled:opacity-60 ${isVideoReady ? "bg-primary text-white" : "bg-slate-300 text-slate-500 cursor-not-allowed"
            }`}
          whileHover={{ scale: mutation.isPending || !isVideoReady ? 1 : 1.02 }}
          whileTap={{ scale: mutation.isPending || !isVideoReady ? 1 : 0.98 }}
          title={!isVideoReady ? "Video masih diproses, tunggu sampai selesai" : ""}
        >
          {mutation.isPending ? "Generating…" : !isVideoReady ? "Waiting for video..." : "Generate Clips"}
        </motion.button>
      </div>
    </section>
  );
};

export default AiClippingPanel;
