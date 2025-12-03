import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import UploadCard from "../../components/viral-clip/UploadCard";
import VideoHistoryGrid from "../../components/viral-clip/VideoHistoryGrid";
import { VideoSource } from "../../types/api";

const AiViralClipPage: React.FC = () => {
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);
  const qc = useQueryClient();

  const handleVideoCreated = (video?: VideoSource, jobId?: number) => {
    if (video) {
      // Refresh video list
      qc.invalidateQueries({ queryKey: ["videos"] });
      if (jobId) {
        setIngestStatus("processing");
        // Poll for job status
        const pollJob = async () => {
          try {
            const res = await fetch(`/api/viral-clip/jobs/${jobId}`, {
              headers: {
                Authorization: `Bearer ${localStorage.getItem("token")}`,
              },
            });
            const job = await res.json();
            if (job.status === "completed" || job.status === "failed") {
              setIngestStatus(job.status);
              qc.invalidateQueries({ queryKey: ["videos"] });
            } else {
              setTimeout(pollJob, 3000);
            }
          } catch {
            setIngestStatus("failed");
          }
        };
        pollJob();
      }
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      <header className="mb-6 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">AI Viral Clip</h1>
        <p className="text-sm text-slate-500">
          Turn one long video into many viral shorts – automatically.
        </p>
        {ingestStatus && ingestStatus !== "completed" && (
          <div className="mt-2 text-xs">
            <span className={ingestStatus === "completed" ? "text-emerald-600" : ingestStatus === "failed" ? "text-rose-600" : "text-blue-600"}>
              {ingestStatus === "processing" ? "Processing video..." : `Latest ingest: ${ingestStatus}`}
            </span>
          </div>
        )}
      </header>

      <UploadCard onVideoCreated={handleVideoCreated} />

      <VideoHistoryGrid />

      {/* Instruction Card */}
      <div className="mt-8 p-6 bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl border border-slate-200">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 mb-1">How it works</h3>
            <ol className="text-sm text-slate-600 space-y-1">
              <li>1. Upload a video or paste a YouTube URL above</li>
              <li>2. Wait for the video to finish processing</li>
              <li>3. Click on a video to generate viral clips</li>
              <li>4. Download and share your clips!</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AiViralClipPage;
