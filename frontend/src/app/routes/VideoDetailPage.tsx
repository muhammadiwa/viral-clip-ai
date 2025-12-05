import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "../../lib/apiClient";
import { VideoSource, Clip, SubtitleStyle } from "../../types/api";
import ClipsSection from "../../components/viral-clip/ClipsSection";
import ClipDetailModal from "../../components/viral-clip/ClipDetailModal";
import SubtitleStylePreview from "../../components/viral-clip/SubtitleStylePreview";
import YouTubePlayer from "../../components/viral-clip/YouTubePlayer";

/**
 * Video Detail Page - displays video information and clips.
 * 
 * Requirements: 2.1, 2.2, 2.3, 5.2, 6.4
 * - Uses slug in URL path instead of video ID
 * - Displays YouTube embed player for YouTube videos
 * - Displays local video player for uploaded videos
 * - Shows download status when generating clips
 */
const VideoDetailPage: React.FC = () => {
    const { slug } = useParams<{ slug: string }>();
    const navigate = useNavigate();
    const qc = useQueryClient();

    // State
    const [selectedClip, setSelectedClip] = useState<Clip | undefined>();
    const [activeTab, setActiveTab] = useState<"clips" | "settings">("clips");

    // Clip generation settings (video_type removed - AI auto-detects)
    const [aspectRatio, setAspectRatio] = useState("9:16");
    const [clipLengthPreset, setClipLengthPreset] = useState("30_60");
    const [subtitleEnabled, setSubtitleEnabled] = useState(true);
    const [includeMoments, setIncludeMoments] = useState("");
    const [timeframe, setTimeframe] = useState<[number, number]>([0, 90]);
    const [selectedStyleId, setSelectedStyleId] = useState<number | null>(null);

    // Fetch video data by slug or ID (fallback for legacy videos without slug)
    const { data: video, isLoading: videoLoading } = useQuery<VideoSource>({
        queryKey: ["video", slug],
        queryFn: async () => {
            // Check if this is an ID-based fallback (format: "id-{number}")
            if (slug?.startsWith("id-")) {
                const videoId = slug.replace("id-", "");
                const res = await api.get(`/viral-clip/videos/${videoId}`);
                return res.data;
            }
            // Normal slug-based lookup
            const res = await api.get(`/viral-clip/videos/by-slug/${slug}`);
            return res.data;
        },
        enabled: Boolean(slug),
        refetchInterval: 5000,
    });

    // Fetch total clips count for stats (using video ID once we have it)
    const { data: allClips } = useQuery<Clip[]>({
        queryKey: ["video-clips", video?.id],
        queryFn: async () => {
            const res = await api.get(`/viral-clip/videos/${video?.id}/clips`);
            return res.data;
        },
        enabled: Boolean(video?.id),
        refetchInterval: 5000,
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
            const res = await api.post(`/viral-clip/videos/${video?.id}/clip-batches`, {
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
        onSuccess: async () => {
            await qc.invalidateQueries({ queryKey: ["video-clips", video?.id] });
            await qc.invalidateQueries({ queryKey: ["video", slug] });
            setActiveTab("clips");
        },
    });

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
    const isDownloading = video?.status === "downloading";
    const isYouTubeVideo = video?.source_type === "youtube";
    const needsDownload = isYouTubeVideo && !video?.is_downloaded;

    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    // Get status display info
    const getStatusInfo = () => {
        if (isDownloading) {
            return {
                label: "Downloading",
                progress: video?.download_progress ?? 0,
                color: "blue",
                showProgress: true,
            };
        }
        if (isProcessing) {
            return {
                label: "Processing",
                color: "blue",
                showProgress: false,
            };
        }
        if (video?.status === "failed") {
            return {
                label: "Failed",
                color: "rose",
                showProgress: false,
            };
        }
        if (needsDownload) {
            return {
                label: "Ready to Generate",
                color: "emerald",
                showProgress: false,
            };
        }
        return null;
    };

    const statusInfo = getStatusInfo();

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
                onClick={() => navigate("/ai-viral-clip")}
                className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white mb-6 transition-colors"
            >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Back to videos
            </button>

            {/* Video Header */}
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 overflow-hidden mb-6">
                <div className="flex">
                    {/* Video Player / Thumbnail */}
                    <div className="w-80 h-48 bg-slate-900 flex-shrink-0 relative">
                        {/* YouTube Video: Show embedded player (Requirements 2.1, 2.2) */}
                        {isYouTubeVideo && video.youtube_video_id ? (
                            <YouTubePlayer
                                videoId={video.youtube_video_id}
                                className="w-full h-full"
                            />
                        ) : video.thumbnail_path ? (
                            /* Local Video: Show thumbnail (Requirement 2.3) */
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
                        {/* Processing/Downloading Overlay */}
                        {(isProcessing || isDownloading) && (
                            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                <div className="text-center text-white">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto mb-2"></div>
                                    <p className="text-sm">
                                        {isDownloading ? `Downloading... ${Math.round(video.download_progress ?? 0)}%` : "Processing video..."}
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Video Info */}
                    <div className="flex-1 p-6">
                        <div className="flex items-start justify-between">
                            <div>
                                <h1 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                                    {video.title || "Untitled video"}
                                </h1>
                                <div className="flex items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
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

                            {/* Status Badge (Requirements 5.1, 5.2) */}
                            {statusInfo && (
                                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold ${statusInfo.color === "blue" ? "bg-blue-100 text-blue-700" :
                                    statusInfo.color === "rose" ? "bg-rose-100 text-rose-700" :
                                        statusInfo.color === "emerald" ? "bg-emerald-100 text-emerald-700" :
                                            "bg-slate-100 text-slate-700"
                                    }`}>
                                    {(isProcessing || isDownloading) && (
                                        <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                    )}
                                    {statusInfo.label}
                                    {statusInfo.showProgress && ` ${Math.round(statusInfo.progress)}%`}
                                </div>
                            )}
                        </div>

                        {/* Quick Stats */}
                        <div className="mt-4 flex items-center gap-6">
                            <div className="text-center">
                                <div className="text-2xl font-bold text-slate-900 dark:text-white">{allClips?.length || 0}</div>
                                <div className="text-xs text-slate-500 dark:text-slate-400">Total Clips</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>


            {/* Tabs */}
            <div className="flex items-center gap-1 mb-6 bg-slate-100 dark:bg-slate-800 rounded-full p-1 w-fit">
                <button
                    onClick={() => setActiveTab("clips")}
                    className={`px-5 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "clips"
                        ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                        }`}
                >
                    Clips
                </button>
                <button
                    onClick={() => setActiveTab("settings")}
                    className={`px-5 py-2 rounded-full text-sm font-medium transition-colors ${activeTab === "settings"
                        ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                        }`}
                >
                    Generate New
                </button>
            </div>

            {/* Tab Content */}
            {activeTab === "clips" && video?.id && (
                <ClipsSection
                    videoId={String(video.id)}
                    selectedClipId={selectedClip?.id}
                    onSelectClip={(clip: Clip) => setSelectedClip(clip)}
                    onGenerateClick={() => setActiveTab("settings")}
                    isVideoReady={isVideoReady}
                />
            )}

            {activeTab === "settings" && (
                <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 p-6">
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

                    {/* Downloading Warning (Requirement 5.2) */}
                    {isDownloading && (
                        <div className="mb-6 p-4 rounded-xl bg-blue-50 border border-blue-200 flex items-center gap-3">
                            <svg className="animate-spin h-5 w-5 text-blue-600 flex-shrink-0" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <div>
                                <div className="text-sm font-medium text-blue-800">Downloading video...</div>
                                <div className="text-xs text-blue-600">Progress: {Math.round(video?.download_progress ?? 0)}%</div>
                            </div>
                        </div>
                    )}

                    {/* Ready to Generate Info (for YouTube videos not yet downloaded) */}
                    {needsDownload && !isDownloading && (
                        <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center gap-3">
                            <svg className="h-5 w-5 text-emerald-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <div>
                                <div className="text-sm font-medium text-emerald-800">Ready to generate clips</div>
                                <div className="text-xs text-emerald-600">Video will be downloaded automatically when you click Generate</div>
                            </div>
                        </div>
                    )}

                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Generate New Clips</h2>

                    {/* Settings Grid - Video Type removed (AI auto-detects) */}
                    <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                            <label className="block mb-2 text-slate-600 dark:text-slate-400 font-medium">Aspect Ratio</label>
                            <select
                                className="w-full rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2.5 focus:border-primary focus:ring-1 focus:ring-primary outline-none text-slate-900 dark:text-white"
                                value={aspectRatio}
                                onChange={(e) => setAspectRatio(e.target.value)}
                            >
                                <option value="9:16">9:16 (TikTok/Reels)</option>
                                <option value="16:9">16:9 (YouTube)</option>
                                <option value="1:1">1:1 (Square)</option>
                            </select>
                        </div>
                        <div>
                            <label className="block mb-2 text-slate-600 dark:text-slate-400 font-medium">Clip Length</label>
                            <select
                                className="w-full rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2.5 focus:border-primary focus:ring-1 focus:ring-primary outline-none text-slate-900 dark:text-white"
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
                            <label className="block mb-2 text-slate-600 dark:text-slate-400 font-medium">Subtitles</label>
                            <select
                                className="w-full rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2.5 focus:border-primary focus:ring-1 focus:ring-primary outline-none text-slate-900 dark:text-white"
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
                        <label className="block mb-2 text-sm text-slate-600 dark:text-slate-400 font-medium">Include Specific Moments</label>
                        <input
                            className="w-full rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-4 py-2.5 text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none text-slate-900 dark:text-white placeholder-slate-400"
                            placeholder="e.g. intro joke at 02:10, product pitch at 10:30"
                            value={includeMoments}
                            onChange={(e) => setIncludeMoments(e.target.value)}
                        />
                    </div>

                    {/* Timeframe */}
                    <div className="mt-6">
                        <div className="flex items-center justify-between text-sm mb-3">
                            <span className="text-slate-600 dark:text-slate-400 font-medium">Processing Timeframe</span>
                            <span className="text-slate-500 dark:text-slate-400">
                                {formatDuration(timeframe[0])} – {formatDuration(timeframe[1])}
                            </span>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Start</label>
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
                                <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">End</label>
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
                            <div className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-3">Subtitle Style</div>
                            <div className="grid grid-cols-3 gap-4 max-h-[500px] overflow-y-auto pr-2">
                                {styles.map((style) => {
                                    const isSelected = selectedStyleId === style.id;

                                    return (
                                        <button
                                            key={style.id}
                                            onClick={() => setSelectedStyleId(style.id)}
                                            className={`rounded-xl border overflow-hidden text-left transition-all ${isSelected
                                                ? "border-primary ring-2 ring-primary/30"
                                                : "border-slate-200 dark:border-slate-600 hover:border-slate-300 dark:hover:border-slate-500"
                                                }`}
                                        >
                                            {/* Live Preview */}
                                            <SubtitleStylePreview
                                                styleJson={style.style_json as Record<string, unknown>}
                                                isSelected={isSelected}
                                            />

                                            {/* Style Info */}
                                            <div className="p-3 bg-white dark:bg-slate-700">
                                                <div className="font-semibold text-sm text-slate-800 dark:text-white truncate">{style.name}</div>
                                                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
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
                        <div className="text-sm text-slate-500 dark:text-slate-400">
                            {styles?.find((s) => s.id === selectedStyleId)?.name || "Default style"} •
                            Subtitle {subtitleEnabled ? "enabled" : "disabled"}
                        </div>
                        <motion.button
                            onClick={() => generateMutation.mutate()}
                            disabled={generateMutation.isPending || isProcessing || isDownloading}
                            className={`inline-flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold shadow-md transition-all ${!isProcessing && !isDownloading && !generateMutation.isPending
                                ? "bg-primary text-white hover:bg-primary/90"
                                : "bg-slate-300 dark:bg-slate-600 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                                }`}
                            whileHover={!isProcessing && !isDownloading && !generateMutation.isPending ? { scale: 1.02 } : {}}
                            whileTap={!isProcessing && !isDownloading && !generateMutation.isPending ? { scale: 0.98 } : {}}
                        >
                            {generateMutation.isPending ? (
                                <>
                                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    {needsDownload ? "Downloading & Generating..." : "Generating..."}
                                </>
                            ) : isDownloading ? (
                                "Downloading..."
                            ) : isProcessing ? (
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
