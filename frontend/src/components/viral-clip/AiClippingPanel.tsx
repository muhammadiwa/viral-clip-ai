import React from "react";
import { VideoSource } from "../../types/api";

type Props = {
  video?: VideoSource;
};

const AiClippingPanel: React.FC<Props> = ({ video }) => {
  if (!video) return null;

  return (
    <section className="mt-8 rounded-3xl bg-white p-5 shadow-sm">
      <div className="flex items-center gap-4 mb-4">
        <div className="h-16 w-28 bg-slate-200 rounded-lg flex items-center justify-center text-xs text-slate-600">
          Thumb
        </div>
        <div>
          <div className="text-sm font-semibold">{video.title || "Untitled video"}</div>
          <div className="text-xs text-slate-500">
            Source: {video.source_type} • Status: {video.status}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 text-xs">
        <div>
          <label className="block mb-1 text-slate-500">Video type</label>
          <select className="w-full rounded-lg border border-slate-200 px-2 py-2">
            <option>Podcast</option>
            <option>Talking head</option>
            <option>Gaming</option>
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-500">Aspect ratio</label>
          <select className="w-full rounded-lg border border-slate-200 px-2 py-2">
            <option>9:16</option>
            <option>16:9</option>
            <option>1:1</option>
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-500">Clip length</label>
          <select className="w-full rounded-lg border border-slate-200 px-2 py-2">
            <option>Auto (0–60s)</option>
            <option>0–30s</option>
            <option>0–90s</option>
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-500">Subtitle</label>
          <select className="w-full rounded-lg border border-slate-200 px-2 py-2">
            <option>Yes</option>
            <option>No</option>
          </select>
        </div>
      </div>

      <div className="mt-6 text-xs text-slate-500">
        Subtitle styles, timeframe slider, dan tombol "Generate Clips" bisa ditambahkan
        di sini mengikuti spesifikasi di docs.
      </div>
    </section>
  );
};

export default AiClippingPanel;
