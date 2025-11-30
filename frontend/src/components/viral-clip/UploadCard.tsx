import React, { useState } from "react";
import { motion } from "framer-motion";
import { api } from "../../lib/apiClient";
import { useQueryClient } from "@tanstack/react-query";
import { VideoSource, VideoCreateResponse } from "../../types/api";

type Props = {
  onVideoCreated: (video?: VideoSource, jobId?: number) => void;
};

const UploadCard: React.FC<Props> = ({ onVideoCreated }) => {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const qc = useQueryClient();

  const handleSubmit = async () => {
    if (!youtubeUrl && !file) {
      setStatus("Paste a link or choose a file first.");
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      if (youtubeUrl) {
        const form = new FormData();
        form.append("youtube_url", youtubeUrl);
        form.append("video_type", "podcast");
        form.append("aspect_ratio", "9:16");
        form.append("clip_length_preset", "auto_0_60");
        form.append("subtitle", "true");
        const res = await api.post<VideoCreateResponse>("/viral-clip/video/youtube", form);
        onVideoCreated(res.data.video, res.data.job?.id);
      } else if (file) {
        const form = new FormData();
        form.append("file", file);
        form.append("video_type", "podcast");
        form.append("aspect_ratio", "9:16");
        form.append("clip_length_preset", "auto_0_60");
        form.append("subtitle", "true");
        const res = await api.post<VideoCreateResponse>("/viral-clip/video/upload", form);
        onVideoCreated(res.data.video, res.data.job?.id);
      }
      setYoutubeUrl("");
      setFile(null);
      await qc.invalidateQueries({ queryKey: ["videos"] });
      setStatus("Job created. Worker will auto-transcribe & segment.");
    } catch (err: any) {
      setStatus(err?.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      className="rounded-3xl bg-gradient-to-br from-[#ffe9da] via-[#fff3ea] to-[#ffe5d5] p-6 flex flex-col gap-4 shadow-sm border border-white/60"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="text-sm font-semibold text-slate-800">Autoclip</div>
      <input
        className="w-full rounded-xl border border-dashed border-primary/40 bg-white/80 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
        placeholder="Drop a YouTube link or paste URL..."
        value={youtubeUrl}
        onChange={(e) => setYoutubeUrl(e.target.value)}
      />
      <div className="flex gap-3 text-xs">
        <label className="px-3 py-2 rounded-full bg-white cursor-pointer border border-slate-200">
          Upload
          <input
            type="file"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button className="px-3 py-2 rounded-full bg-white border border-slate-200">
          Google Drive
        </button>
      </div>
      <motion.button
        onClick={handleSubmit}
        disabled={loading}
        className="mt-2 inline-flex items-center justify-center rounded-full bg-primary text-white px-6 py-3 text-sm font-semibold shadow-md disabled:opacity-60"
        whileHover={{ scale: loading ? 1 : 1.02 }}
        whileTap={{ scale: loading ? 1 : 0.97 }}
      >
        {loading ? "Processing..." : "Get Clips"}
      </motion.button>
      <button className="mt-1 text-xs text-slate-600 underline text-left">
        Click here to try a sample project
      </button>
      {status && <div className="text-xs text-slate-600">{status}</div>}
    </motion.div>
  );
};

export default UploadCard;
