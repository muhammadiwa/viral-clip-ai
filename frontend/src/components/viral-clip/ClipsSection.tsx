import React, { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/apiClient";
import { Clip } from "../../types/api";
import ClipCard from "./ClipCard";

type Props = {
    videoId: string;
    onSelectClip: (clip: Clip) => void;
    selectedClipId?: number;
    onGenerateClick?: () => void;
    isVideoReady?: boolean;
};

type AspectRatioCategory = {
    key: string;
    label: string;
    icon: React.ReactNode;
    description: string;
};

const ASPECT_RATIO_CATEGORIES: AspectRatioCategory[] = [
    {
        key: "9:16",
        label: "TikTok / Reels",
        icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z" />
            </svg>
        ),
        description: "Vertical format for short-form content",
    },
    {
        key: "16:9",
        label: "YouTube",
        icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
            </svg>
        ),
        description: "Horizontal format for long-form content",
    },
    {
        key: "1:1",
        label: "Square",
        icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>
        ),
        description: "Square format for feed posts",
    },
];

const ITEMS_PER_PAGE = 8;

const ClipsSection: React.FC<Props> = ({ videoId, onSelectClip, selectedClipId, onGenerateClick, isVideoReady = true }) => {
    const [activeCategory, setActiveCategory] = useState<string>("all");
    const [currentPage, setCurrentPage] = useState(1);

    // Fetch all clips for this video (from all batches)
    const { data: allClips, isLoading } = useQuery<Clip[]>({
        queryKey: ["video-clips", videoId],
        queryFn: async () => {
            const res = await api.get(`/viral-clip/videos/${videoId}/clips`);
            return res.data;
        },
        enabled: Boolean(videoId),
        refetchInterval: 5000,
    });


    // Sort clips by created_at (newest first) and group by aspect ratio
    const { sortedClips, clipsByCategory, categoryCounts } = useMemo(() => {
        if (!allClips) return { sortedClips: [], clipsByCategory: {}, categoryCounts: {} };

        // Sort by created_at descending (newest first)
        const sorted = [...allClips].sort((a, b) => {
            const dateA = new Date(a.created_at || 0).getTime();
            const dateB = new Date(b.created_at || 0).getTime();
            return dateB - dateA;
        });

        // Group by aspect ratio
        const byCategory: Record<string, Clip[]> = {};
        const counts: Record<string, number> = { all: sorted.length };

        sorted.forEach((clip) => {
            const ratio = clip.aspect_ratio || "16:9";
            if (!byCategory[ratio]) {
                byCategory[ratio] = [];
                counts[ratio] = 0;
            }
            byCategory[ratio].push(clip);
            counts[ratio]++;
        });

        return { sortedClips: sorted, clipsByCategory: byCategory, categoryCounts: counts };
    }, [allClips]);

    // Get clips for current view
    const displayClips = useMemo(() => {
        if (activeCategory === "all") {
            return sortedClips;
        }
        return clipsByCategory[activeCategory] || [];
    }, [activeCategory, sortedClips, clipsByCategory]);

    // Pagination
    const totalPages = Math.ceil(displayClips.length / ITEMS_PER_PAGE);
    const paginatedClips = displayClips.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    // Reset page when category changes
    const handleCategoryChange = (category: string) => {
        setActiveCategory(category);
        setCurrentPage(1);
    };

    const processingCount = allClips?.filter((c) => c.status !== "ready").length || 0;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-3"></div>
                    <p className="text-sm text-slate-500">Loading clips...</p>
                </div>
            </div>
        );
    }

    if (!allClips || allClips.length === 0) {
        return (
            <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700 p-12 text-center">
                <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                    </svg>
                </div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">No clips yet</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
                    Generate your first batch of viral clips from this video
                </p>
                {onGenerateClick && (
                    <button
                        onClick={onGenerateClick}
                        disabled={!isVideoReady}
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-primary text-white text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Generate Clips
                    </button>
                )}
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Category Tabs */}
            <div className="flex items-center gap-3 flex-wrap">
                {/* All Tab */}
                <button
                    onClick={() => handleCategoryChange("all")}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${activeCategory === "all"
                        ? "bg-primary text-white shadow-md shadow-primary/25"
                        : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700"
                        }`}
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                    </svg>
                    All Clips
                    <span className={`px-2 py-0.5 rounded-full text-xs ${activeCategory === "all" ? "bg-white/20" : "bg-slate-100 dark:bg-slate-700"
                        }`}>
                        {categoryCounts.all || 0}
                    </span>
                </button>

                {/* Category Tabs */}
                {ASPECT_RATIO_CATEGORIES.map((cat) => {
                    const count = categoryCounts[cat.key] || 0;
                    if (count === 0) return null;

                    return (
                        <button
                            key={cat.key}
                            onClick={() => handleCategoryChange(cat.key)}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${activeCategory === cat.key
                                ? "bg-primary text-white shadow-md shadow-primary/25"
                                : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700"
                                }`}
                        >
                            <span className={activeCategory === cat.key ? "text-white" : "text-slate-400 dark:text-slate-500"}>
                                {cat.icon}
                            </span>
                            {cat.label}
                            <span className={`px-2 py-0.5 rounded-full text-xs ${activeCategory === cat.key ? "bg-white/20" : "bg-slate-100 dark:bg-slate-700"
                                }`}>
                                {count}
                            </span>
                        </button>
                    );
                })}

                {/* Processing indicator */}
                {processingCount > 0 && (
                    <div className="flex items-center gap-2 px-3 py-2 text-xs text-blue-600 bg-blue-50 rounded-lg">
                        <svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                        </svg>
                        {processingCount} processing
                    </div>
                )}
            </div>


            {/* Clips Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {paginatedClips.map((clip) => (
                    <ClipCard
                        key={clip.id}
                        clip={clip}
                        active={selectedClipId === clip.id}
                        onSelect={() => onSelectClip(clip)}
                    />
                ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-6">
                    {/* Previous Button */}
                    <button
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                        className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                        Prev
                    </button>

                    {/* Page Numbers */}
                    <div className="flex items-center gap-1">
                        {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
                            // Show first, last, current, and adjacent pages
                            const showPage =
                                page === 1 ||
                                page === totalPages ||
                                Math.abs(page - currentPage) <= 1;

                            // Show ellipsis
                            const showEllipsisBefore = page === currentPage - 2 && currentPage > 3;
                            const showEllipsisAfter = page === currentPage + 2 && currentPage < totalPages - 2;

                            if (showEllipsisBefore || showEllipsisAfter) {
                                return (
                                    <span key={page} className="px-2 text-slate-400 dark:text-slate-500">
                                        ...
                                    </span>
                                );
                            }

                            if (!showPage) return null;

                            return (
                                <button
                                    key={page}
                                    onClick={() => setCurrentPage(page)}
                                    className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${currentPage === page
                                        ? "bg-primary text-white shadow-md shadow-primary/25"
                                        : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                                        }`}
                                >
                                    {page}
                                </button>
                            );
                        })}
                    </div>

                    {/* Next Button */}
                    <button
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                        className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                    >
                        Next
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                    </button>
                </div>
            )}

            {/* Results info */}
            <div className="text-center text-sm text-slate-500 dark:text-slate-400">
                Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1}–{Math.min(currentPage * ITEMS_PER_PAGE, displayClips.length)} of {displayClips.length} clips
            </div>
        </div>
    );
};

export default ClipsSection;
