import React, { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import UploadCard from "../../components/viral-clip/UploadCard";
import VideoHistoryGrid from "../../components/viral-clip/VideoHistoryGrid";
import AiClippingPanel from "../../components/viral-clip/AiClippingPanel";
import ClipsGrid from "../../components/viral-clip/ClipsGrid";
import ClipDetailModal from "../../components/viral-clip/ClipDetailModal";
import { Clip, ClipBatch, VideoSource, ProcessingJob } from "../../types/api";
import { api } from "../../lib/apiClient";

const AiViralClipPage: React.FC = () => {
  const [selectedVideo, setSelectedVideo] = useState<VideoSource | undefined>();
  const [selectedBatchId, setSelectedBatchId] = useState<number | undefined>();
  const [selectedClip, setSelectedClip] = useState<Clip | undefined>();
  const [ingestJobId, setIngestJobId] = useState<number | undefined>();
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);
  const qc = useQueryClient();

  const { data: batches } = useQuery<ClipBatch[]>({
    queryKey: ["clip-batches", selectedVideo?.id],
    enabled: Boolean(selectedVideo?.id),
    queryFn: async () => {
      if (!selectedVideo?.id) return [];
      const res = await api.get(`/viral-clip/videos/${selectedVideo.id}/clip-batches`);
      return res.data;
    },
    refetchInterval: selectedVideo ? 4000 : false
  });

  useQuery<ProcessingJob>({
    queryKey: ["job", ingestJobId],
    enabled: Boolean(ingestJobId),
    queryFn: async () => {
      const res = await api.get(`/viral-clip/jobs/${ingestJobId}`);
      return res.data;
    },
    refetchInterval: ingestJobId ? 3000 : false,
    onSuccess: async (job) => {
      if (job.status === "completed" || job.status === "failed") {
        setIngestJobId(undefined);
        setIngestStatus(job.status);
        await qc.invalidateQueries({ queryKey: ["videos"] });
      }
    }
  });

  useEffect(() => {
    if (batches && batches.length > 0 && !selectedBatchId) {
      setSelectedBatchId(batches[0].id);
    }
  }, [batches, selectedBatchId]);

  const handleVideoCreated = (video?: VideoSource, jobId?: number) => {
    if (video) {
      setSelectedVideo(video);
      setSelectedBatchId(undefined);
      setSelectedClip(undefined);
      if (jobId) setIngestJobId(jobId);
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">AI Viral Clip</h1>
            <p className="text-sm text-slate-500">
              Turn one long video into many viral shorts – automatically.
            </p>
          </div>
          <div className="text-xs text-slate-500">
            Worker must be running to process jobs. Status is visible per video.
          </div>
        </div>
        {ingestStatus && (
          <div className="mt-2 text-xs">
            <span className={ingestStatus === "completed" ? "text-emerald-600" : "text-amber-600"}>
              Latest ingest job: {ingestStatus}
            </span>
          </div>
        )}
      </header>

      <UploadCard onVideoCreated={handleVideoCreated} />
      <VideoHistoryGrid
        selectedId={selectedVideo?.id}
        onSelect={(v) => {
          setSelectedVideo(v);
          setSelectedBatchId(undefined);
          setSelectedClip(undefined);
        }}
      />
      <AiClippingPanel
        video={selectedVideo}
        onBatchCreated={(batchId) => {
          setSelectedBatchId(batchId);
          setSelectedClip(undefined);
        }}
      />

      {batches && batches.length > 0 && (
        <div className="mt-6">
          <div className="text-sm font-semibold mb-2">Clip batches</div>
          <div className="flex gap-2 flex-wrap">
            {batches.map((batch) => (
              <button
                key={batch.id}
                onClick={() => {
                  setSelectedBatchId(batch.id);
                  setSelectedClip(undefined);
                }}
                className={`px-3 py-2 rounded-full text-xs border ${
                  selectedBatchId === batch.id ? "border-primary bg-primary/5" : "border-slate-200 bg-white"
                }`}
              >
                {batch.name} • {batch.status}
              </button>
            ))}
          </div>
        </div>
      )}

      <ClipsGrid
        batchId={selectedBatchId}
        selectedClipId={selectedClip?.id}
        batchStatus={batches?.find((b) => b.id === selectedBatchId)?.status}
        onSelect={(clip: Clip) => setSelectedClip(clip)}
      />

      <ClipDetailModal clipId={selectedClip?.id} open={Boolean(selectedClip)} onClose={() => setSelectedClip(undefined)} />
    </div>
  );
};

export default AiViralClipPage;
