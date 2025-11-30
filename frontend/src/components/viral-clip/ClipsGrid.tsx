import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { Clip, ExportJob } from "../../types/api";
import ClipCard from "./ClipCard";

type Props = {
  batchId?: number;
  selectedClipId?: number;
  onSelect: (clip: Clip) => void;
  batchStatus?: string;
};

const ClipsGrid: React.FC<Props> = ({ batchId, selectedClipId, onSelect, batchStatus }) => {
  const { data, isLoading } = useQuery<Clip[]>({
    queryKey: ["clips", batchId],
    queryFn: async () => {
      const res = await api.get(`/viral-clip/clip-batches/${batchId}/clips`);
      return res.data;
    },
    enabled: Boolean(batchId),
    refetchInterval: batchStatus === "processing" ? 3000 : false
  });

  const { data: exportsByClip } = useQuery<Record<number, ExportJob[]>>({
    queryKey: ["exports-map", batchId],
    queryFn: async () => {
      const res = await api.get(`/viral-clip/clip-batches/${batchId}/exports`);
      return res.data;
    },
    enabled: Boolean(batchId),
    refetchInterval: batchStatus === "processing" ? 3000 : 8000
  });

  if (!batchId) {
    return <div className="mt-8 text-sm text-slate-500">Select a batch to view clips.</div>;
  }

  if (isLoading) {
    return <div className="mt-8 text-sm text-slate-500">Loading clips…</div>;
  }

  if (!data || data.length === 0) {
    return <div className="mt-8 text-sm text-slate-500">No clips yet. Generate to see candidates.</div>;
  }

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold">Generated Clips</div>
        {batchStatus === "processing" && <div className="text-xs text-slate-500">Batch processing… auto-refreshing</div>}
      </div>
      <div className="grid grid-cols-3 gap-4">
        {data.map((clip) => {
          const exp = exportsByClip?.[clip.id]?.find((e) => e.status === "completed");
          return (
            <ClipCard
              key={clip.id}
              clip={clip}
              active={selectedClipId === clip.id}
              onSelect={() => onSelect(clip)}
              exportLink={exp?.output_path}
              srtLink={`${api.defaults.baseURL}/viral-clip/clips/${clip.id}/subtitles.srt`}
            />
          );
        })}
      </div>
    </div>
  );
};

export default ClipsGrid;
