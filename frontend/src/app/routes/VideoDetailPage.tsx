import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "../../lib/apiClient";
import { VideoSource, ClipBatch, Clip, SubtitleStyle } from "../../types/api";
import ClipsGrid from "../../components/viral-clip/ClipsGrid";
import ClipDetailModal from "../../components/viral-clip/ClipDetailModal";
import SubtitleStylePreview from "../../components/viral-clip/SubtitleStylePreview";

const VideoDetailPage: React.FC = () => {
    const { videoId } = useParams<{ videoId: string }>();
    const navigate = useNavigate();
    const qc = useQueryClient();

    // State
    const [selectedBatchId, setSelectedBatchId] = useState<number | undefined>();
    const [selectedClip, setSelectedClip] = useState<Clip | undefined>();
    const [activeTab, setActiveTab] = useState<"clips" | "settings">("clips");

    // Clip generation settings (video_type removed - AI auto-detects)
    const [aspectRatio, setAspectRatio] = useState("9:16");
    const [clipLengthPreset, setClipLengthPreset] = useState("30_60");
    const [subtitleEnabled, setSubtitleEnabled] = useState(true);
    const [includeMoments, setIncludeMoments] = useState("");
    const [timeframe, setTimeframe] = useState<[number, number]>([0, 90]);
    const [selectedStyleId, setSelectedStyleId] = useState<number | null>(null);

    // Fetch video data
    const { data: video, isLoading: videoLoading } = useQuery<VideoSource>({
        queryKey: ["video", videoId],
        queryFn: async () => {
            const res = await api.get(`/viral-clip/videos/${videoId}`);
            return res.data;
        },
        enabled: Boolean(videoId),
        refetchInterval: 5000,
    });

    // Fetch clip batches
    const { data: batches } = useQuery<ClipBatch[]>({
        queryKey: ["clip-batches", videoId],
        queryFn: async () => {
            const res = await api.get(`/viral-clip/videos/${videoId}/clip-batches`);
            return res.data;
        },
        enabled: Boolean(videoId),
        refetchInterval: 4000,
    });

    // Fetch subtitle styles
    const { data: styles } = useQuery<SubtitleStyle[]>({
        queryKey: ["subtitle-styles"],
        queryFn: async () => {
            const res = await api.get("/subtitle-styles");
            return res.data;
        },
    });

    // Generate clips mutation
    const generateMutation = useMutation({
        mutationFn: async () => {
            const res = await api.post(`/viral-clip/videos/${videoId}/clip-batches`, {
                aspect_ratio: aspectRatio,
                clip_length_preset: clipLengthPreset,
                subtitle_enabled: subtitleEnabled,
                subtitle_style_id: selectedStyleId,
                include_specific_moments: includeMoments,
                processing_timeframe_start: timeframe[0],
                processing_timeframe_end: timeframe[1],
            });
            return res.data;
        },
        onSuccess: async (data) => {
            if (data?.batch?.id) {
                setSelectedBatchId(data.batch.id);
            }
            await qc.invalidateQueries({ queryKey: ["clip-batches", videoId] });
            setActiveTab("clips");
        },
    });

    // Set default batch when loaded
    useEffect(() => {
        if (batches && batches.length > 0 && !selectedBatchId) {
            setSelectedBatchId(batches[0].id);
        }
    }, [batches, selectedBatchId]);

    // Update timeframe when video loads
    useEffect(() => {
        if (video?.duration_seconds) {
            const maxTime = Math.ceil(video.duration_seconds);
            setTimeframe([0, Math.min(90, maxTime)]);
        }
    }, [video?.id, video?.duration_seconds]);

    const maxTime = Math.max(60, Math.ceil(video?.duration_seconds ?? 180));
    const isVideoReady = video?.status === "ready" || video?.status === "analyzed";
    const isProcessing = video?.status === "processing" || video?.status === "pending";

    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    if (videoLoading) {
        return (
            <div className="max-w-6xl mx-auto flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mx-auto mb-4"></div>
                    <p className="text-sm text-slate-500">Loading video...</p>
                </div>
            </div>
        );
    }

    if (!video) {
        return (
            <div className="max-w-6xl mx-auto">
                <div className="text-center py-12">
                    <p className="text-slate-500 mb-4">Video not found</p>
                    <button
                        onClick={() => navigate("/")}
                        className="text-primary hover:underline text-sm"
                    >
                        ← Back to videos
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto">
            {/* Back Button */}
            <button
                onClick={() => navigate("/")}
                className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 mb-6 transition-colors"
            >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Back to videos
            </button>

            {/* Video Header */}
            <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden mb-6">
                <div className="flex">
                    {/* Video Thumbnail / Preview */}
                    <div className="w-80 h-48 bg-slate-900 flex-shrink-0 relative">
                        {video.thumbnail_path ? (
                            <img
                                src={video.thumbnail_path}
                                alt={video.title || "Video thumbnail"}
                                className="w-full h-full object-cover"
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-slate-500">
                                <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                            </div>
                        )}
                        {/* Processing Overlay */}
                        {isProcessing && (
                            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                <div className="text-center text-white">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto mb-2"></div>
                                    <p className="text-sm">Processing video...</p>
                                </div>
                            </div>
                        )}
                        {/* Play Button Overlay */}
                        {!isProcessing && (
                            <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 hover:opacity-100 transition-opacity cursor-pointer">
                                <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center">
                                    <svg className="w-6 h-6 text-slate-800 ml-1" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M8 5v14l11-7z" />
                                    </svg>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Video Info */}
                    <div className="flex-1 p-6">
                        <div className="flex items-start justify-between">
                            <div>
                                <h1 className="text-xl font-semibold text-slate-900 mb-2">
                                    {video.title || "Untitled video"}
                                </h1>
                                <div className="flex items-center gap-4 text-sm text-slate-500">
                                    <span className="flex items-center gap-1">
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        {video.duration_seconds ? formatDuration(video.duration_seconds) : "Unknown"}
                                    </span>
                                    <span className="capitalize flex items-center gap-1">
                                        {video.source_type === "youtube" ? (
                                            <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                                                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                                            </svg>
                                        ) : (
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                            </svg>
                                        )}
                                        {video.source_type}
                                    </span>
                                </div>
                            </div>

                            {/* Status - only show if processing or failed */}
                            {(video.status === "processing" || video.status === "pending") && (
                                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold">
                                    <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Processing
                                </div>
                            )}
                            {video.status === "failed" && (
                                <div className="px-3 py-1.5 rounded-full bg-rose-100 text-rose-700 text-xs font-semibold">
                                    Failed
                                </div>
                            )}
                        </div>

                        {/* Quick Stats */}
                        <div className="mt-4 flex items-center gap-6">
                            <div className="text-center">
                                <div className="text-2xl font-bold text-slate-900">{batches?.length || 0}</div>
                                <div className="text-xs text-slate-500">Batches</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-1 mb-6 bg-slate-100 rounded-full p-1 w-fit">
                <button
                    onClick={() => setActiveTab("clips")}
                    className={`px-5 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "clips"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                        }`}
                >
                    Clips
                </button>
                <button
                    onClick={() => setActiveTab("settings")}
                    className={`px-5 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "settings"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                        }`}
                >
                    Generate New
                </button>
            </div>

            {/* Tab Content */}
            {activeTab === "clips" && (
                <div>
                    {/* Batch Selector */}
                    {batches && batches.length > 0 && (
                        <div className="mb-6">
                            <div className="text-sm font-semibold mb-3 text-slate-700">Select Batch</div>
                            <div className="flex gap-2 flex-wrap">
                                {batches.map((batch) => (
                                    <button
                                        key={batch.id}
                                        onClick={() => {
                                            setSelectedBatchId(batch.id);
                                            setSelectedClip(undefined);
                                        }}
                                        className={`px-4 py-2 rounded-xl text-sm border transition-all ${selectedBatchId === batch.id
                                            ? "border-primary bg-primary/5 text-primary font-medium"
                                            : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                                            }`}
                                    >
                                        {batch.name}
                                        {batch.status === "processing" && (
                                            <span className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-blue-100 text-blue-700">
                                                <svg className="animate-spin h-2.5 w-2.5" fill="none" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                                </svg>
                                                Processing
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Clips Grid */}
                    {selectedBatchId ? (
                        <ClipsGrid
                            batchId={selectedBatchId}
                            selectedClipId={selectedClip?.id}
                            batchStatus={batches?.find((b) => b.id === selectedBatchId)?.status}
                            onSelect={(clip: Clip) => setSelectedClip(clip)}
                        />
                    ) : (
                        <div className="bg-white rounded-3xl border border-slate-100 p-12 text-center">
                            <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
                                <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-slate-900 mb-2">No clips yet</h3>
                            <p className="text-sm text-slate-500 mb-4">
                                Generate your first batch of viral clips from this video
                            </p>
                            <button
                                onClick={() => setActiveTab("settings")}
                                disabled={!isVideoReady}
                                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-primary text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                                Generate Clips
                            </button>
                        </div>
                    )}
                </div>
            )}

            {activeTab === "settings" && (
                <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-6">
                    {/* Processing Warning */}
                    {isProcessing && (
                        <div className="mb-6 p-4 rounded-xl bg-blue-50 border border-blue-200 flex items-center gap-3">
                            <svg className="animate-spin h-5 w-5 text-blue-600 flex-shrink-0" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <div>
                                <div className="text-sm font-medium text-blue-800">Video sedang diproses</div>
                                <div className="text-xs text-blue-600">Tunggu sampai proses selesai sebelum generate clips</div>
                            </div>
                        </div>
                    )}

                    <h2 className="text-lg font-semibold text-slate-900 mb-6">Generate New Clips</h2>

                    {/* Settings Grid - Video Type removed (AI auto-detects) */}
                    <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                            <label className="block mb-2 text-slate-600 font-medium">Aspect Ratio</label>
                            <select
                                className="w-full rounded-xl border border-slate-200 px-3 py-2.5 focus:border-primary focus:ring-1 focus:ring-primary outline-none"
                                value={aspectRatio}
                                onChange={(e) => setAspectRatio(e.target.value)}
                            >
                                <option value="9:16">9:16 (TikTok/Reels)</option>
                                <option value="16:9">16:9 (YouTube)</option>
                                <option value="1:1">1:1 (Square)</option>
                            </select>
                        </div>
                        <div>
                            <label className="block mb-2 text-slate-600 font-medium">Clip Length</label>
                            <select
                                className="w-full rounded-xl border border-slate-200 px-3 py-2.5 focus:border-primary focus:ring-1 focus:ring-primary outline-none"
                                value={clipLengthPreset}
                                onChange={(e) => setClipLengthPreset(e.target.value)}
                            >
                                <option value="0_30">Short (0–30s)</option>
                                <option value="30_60">Medium (30–60s)</option>
                                <option value="60_90">Long (60–90s)</option>
                                <option value="60_180">Extra Long (1–3 min)</option>
                            </select>
                        </div>
                        <div>
                            <label className="block mb-2 text-slate-600 font-medium">Subtitles</label>
                            <select
                                className="w-full rounded-xl border border-slate-200 px-3 py-2.5 focus:border-primary focus:ring-1 focus:ring-primary outline-none"
                                value={subtitleEnabled ? "yes" : "no"}
                                onChange={(e) => setSubtitleEnabled(e.target.value === "yes")}
                            >
                                <option value="yes">Enabled</option>
                                <option value="no">Disabled</option>
                            </select>
                        </div>
                    </div>

                    {/* Include Moments */}
                    <div className="mt-6">
                        <label className="block mb-2 text-sm text-slate-600 font-medium">Include Specific Moments</label>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none"
                            placeholder="e.g. intro joke at 02:10, product pitch at 10:30"
                            value={includeMoments}
                            onChange={(e) => setIncludeMoments(e.target.value)}
                        />
                    </div>

                    {/* Timeframe */}
                    <div className="mt-6">
                        <div className="flex items-center justify-between text-sm mb-3">
                            <span className="text-slate-600 font-medium">Processing Timeframe</span>
                            <span className="text-slate-500">
                                {formatDuration(timeframe[0])} – {formatDuration(timeframe[1])}
                            </span>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">Start</label>
                                <input
                                    type="range"
                                    min={0}
                                    max={timeframe[1]}
                                    value={timeframe[0]}
                                    onChange={(e) => setTimeframe([Number(e.target.value), timeframe[1]])}
                                    className="w-full accent-primary"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">End</label>
                                <input
                                    type="range"
                                    min={timeframe[0]}
                                    max={maxTime}
                                    value={timeframe[1]}
                                    onChange={(e) => setTimeframe([timeframe[0], Number(e.target.value)])}
                                    className="w-full accent-primary"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Subtitle Styles */}
                    {subtitleEnabled && styles && styles.length > 0 && (
                        <div className="mt-6">
                            <div className="text-sm font-medium text-slate-600 mb-3">Subtitle Style</div>
                            <div className="grid grid-cols-3 gap-4 max-h-[500px] overflow-y-auto pr-2">
                                {styles.map((style) => {
                                    const hasAnimation = style.style_json.animation === "word_highlight";
                                    const isSelected = selectedStyleId === style.id;

                                    return (
                                        <button
                                            key={style.id}
                                            onClick={() => setSelectedStyleId(style.id)}
                                            className={`rounded-xl border overflow-hidden text-left transition-all ${isSelected
                                                ? "border-primary ring-2 ring-primary/30"
                                                : "border-slate-200 hover:border-slate-300"
                                                }`}
                                        >
                                            {/* Live Preview */}
                                            <SubtitleStylePreview
                                                styleJson={style.style_json as Record<string, unknown>}
                                                isSelected={isSelected}
                                            />

                                            {/* Style Info */}
                                            <div className="p-3 bg-white">
                                                <div className="font-semibold text-sm text-slate-800 truncate">{style.name}</div>
                                                <div className="text-[11px] text-slate-500 mt-0.5">
                                                    {String(style.style_json.fontFamily || "Sans")}
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* Generate Button */}
                    <div className="mt-8 flex items-center justify-between">
                        <div className="text-sm text-slate-500">
                            {styles?.find((s) => s.id === selectedStyleId)?.name || "Default style"} •
                            Subtitle {subtitleEnabled ? "enabled" : "disabled"}
                        </div>
                        <motion.button
                            onClick={() => generateMutation.mutate()}
                            disabled={generateMutation.isPending || !isVideoReady}
                            className={`inline-flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold shadow-md transition-all ${isVideoReady
                                ? "bg-primary text-white hover:bg-primary/90"
                                : "bg-slate-300 text-slate-500 cursor-not-allowed"
                                }`}
                            whileHover={isVideoReady && !generateMutation.isPending ? { scale: 1.02 } : {}}
                            whileTap={isVideoReady && !generateMutation.isPending ? { scale: 0.98 } : {}}
                        >
                            {generateMutation.isPending ? (
                                <>
                                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Generating...
                                </>
                            ) : !isVideoReady ? (
                                "Waiting for video..."
                            ) : (
                                <>
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Generate Clips
                                </>
                            )}
                        </motion.button>
                    </div>
                </div>
            )}

            {/* Clip Detail Modal */}
            <ClipDetailModal
                clipId={selectedClip?.id}
                open={Boolean(selectedClip)}
                onClose={() => setSelectedClip(undefined)}
            />
        </div>
    );
};

export default VideoDetailPage;
