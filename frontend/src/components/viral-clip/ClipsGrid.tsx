import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { Clip } from "../../types/api";
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

  if (!batchId) {
    return <div className="mt-8 text-sm text-slate-500">Select a batch to view clips.</div>;
  }

  if (isLoading) {
    return <div className="mt-8 text-sm text-slate-500">Loading clips…</div>;
  }

  if (!data || data.length === 0) {
    return <div className="mt-8 text-sm text-slate-500">No clips yet. Generate to see candidates.</div>;
  }

  const readyCount = data.filter((c) => c.status === "ready").length;

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold">
          Generated Clips ({readyCount}/{data.length} ready)
        </div>
        {batchStatus === "processing" && (
          <div className="text-xs text-slate-500">Processing clips… auto-refreshing</div>
        )}
      </div>
      <div className="grid grid-cols-4 gap-4">
        {data.map((clip) => (
          <ClipCard
            key={clip.id}
            clip={clip}
            active={selectedClipId === clip.id}
            onSelect={() => onSelect(clip)}
          />
        ))}
      </div>
    </div>
  );
};

export default ClipsGrid;
