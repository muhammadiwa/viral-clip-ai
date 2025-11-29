import React, { useState } from "react";
import UploadCard from "../../components/viral-clip/UploadCard";
import VideoHistoryGrid from "../../components/viral-clip/VideoHistoryGrid";
import AiClippingPanel from "../../components/viral-clip/AiClippingPanel";
import { VideoSource } from "../../types/api";

const AiViralClipPage: React.FC = () => {
  const [selectedVideo, setSelectedVideo] = useState<VideoSource | undefined>();

  return (
    <div className="max-w-6xl mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">AI Viral Clip</h1>
        <p className="text-sm text-slate-500">
          Turn one long video into many viral shorts – automatically.
        </p>
      </header>

      <UploadCard onVideoCreated={() => {}} />
      <VideoHistoryGrid
        selectedId={selectedVideo?.id}
        onSelect={(v) => setSelectedVideo(v)}
      />
      <AiClippingPanel video={selectedVideo} />
    </div>
  );
};

export default AiViralClipPage;
