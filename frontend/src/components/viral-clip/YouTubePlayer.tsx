import React, { useRef, useEffect, useCallback, useState } from "react";

interface YouTubePlayerProps {
    videoId: string;
    startTime?: number;
    endTime?: number;
    autoplay?: boolean;
    className?: string;
    onReady?: () => void;
    onPlay?: () => void;
    onPause?: () => void;
    onEnd?: () => void;
    onError?: (error: number) => void;
}

// YouTube Player API types
interface YTPlayer {
    playVideo: () => void;
    pauseVideo: () => void;
    seekTo: (seconds: number, allowSeekAhead: boolean) => void;
    getCurrentTime: () => number;
    getDuration: () => number;
    destroy: () => void;
}

interface YTPlayerEvent {
    target: YTPlayer;
    data?: number;
}

// Extend window for YouTube API
declare global {
    interface Window {
        YT?: {
            Player: new (
                elementId: string,
                config: {
                    videoId: string;
                    playerVars?: Record<string, string | number>;
                    events?: {
                        onReady?: (event: YTPlayerEvent) => void;
                        onStateChange?: (event: YTPlayerEvent) => void;
                        onError?: (event: YTPlayerEvent) => void;
                    };
                }
            ) => YTPlayer;
            PlayerState: {
                UNSTARTED: number;
                ENDED: number;
                PLAYING: number;
                PAUSED: number;
                BUFFERING: number;
                CUED: number;
            };
        };
        onYouTubeIframeAPIReady?: () => void;
    }
}

// Track if API is loaded globally
let apiLoaded = false;
let apiLoading = false;
const apiReadyCallbacks: (() => void)[] = [];

const loadYouTubeAPI = (): Promise<void> => {
    return new Promise((resolve) => {
        if (apiLoaded && window.YT) {
            resolve();
            return;
        }

        apiReadyCallbacks.push(resolve);

        if (apiLoading) {
            return;
        }

        apiLoading = true;

        const existingScript = document.querySelector(
            'script[src="https://www.youtube.com/iframe_api"]'
        );
        if (existingScript) {
            return;
        }

        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        script.async = true;

        window.onYouTubeIframeAPIReady = () => {
            apiLoaded = true;
            apiReadyCallbacks.forEach((cb) => cb());
            apiReadyCallbacks.length = 0;
        };

        document.body.appendChild(script);
    });
};

const YouTubePlayer: React.FC<YouTubePlayerProps> = ({
    videoId,
    startTime = 0,
    endTime,
    autoplay = false,
    className = "",
    onReady,
    onPlay,
    onPause,
    onEnd,
    onError,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const playerRef = useRef<YTPlayer | null>(null);
    const playerIdRef = useRef<string>(`yt-player-${Math.random().toString(36).substr(2, 9)}`);
    const [isLoading, setIsLoading] = useState(true);
    const [hasError, setHasError] = useState(false);

    const handleStateChange = useCallback(
        (event: YTPlayerEvent) => {
            if (!window.YT) return;

            switch (event.data) {
                case window.YT.PlayerState.PLAYING:
                    onPlay?.();
                    break;
                case window.YT.PlayerState.PAUSED:
                    onPause?.();
                    break;
                case window.YT.PlayerState.ENDED:
                    onEnd?.();
                    break;
            }
        },
        [onPlay, onPause, onEnd]
    );

    const handleError = useCallback(
        (event: YTPlayerEvent) => {
            setHasError(true);
            setIsLoading(false);
            onError?.(event.data ?? 0);
        },
        [onError]
    );

    const handleReady = useCallback(() => {
        setIsLoading(false);
        onReady?.();
    }, [onReady]);

    useEffect(() => {
        let mounted = true;

        const initPlayer = async () => {
            await loadYouTubeAPI();

            if (!mounted || !window.YT || !containerRef.current) return;

            // Create player container element
            const playerElement = document.createElement("div");
            playerElement.id = playerIdRef.current;
            containerRef.current.innerHTML = "";
            containerRef.current.appendChild(playerElement);

            // Build player vars
            const playerVars: Record<string, string | number> = {
                autoplay: autoplay ? 1 : 0,
                start: Math.floor(startTime),
                modestbranding: 1,
                rel: 0,
                playsinline: 1,
                enablejsapi: 1,
                origin: window.location.origin,
            };

            if (endTime !== undefined) {
                playerVars.end = Math.floor(endTime);
            }

            playerRef.current = new window.YT.Player(playerIdRef.current, {
                videoId,
                playerVars,
                events: {
                    onReady: handleReady,
                    onStateChange: handleStateChange,
                    onError: handleError,
                },
            });
        };

        initPlayer();

        return () => {
            mounted = false;
            if (playerRef.current) {
                try {
                    playerRef.current.destroy();
                } catch {
                    // Player may already be destroyed
                }
                playerRef.current = null;
            }
        };
    }, [videoId, startTime, endTime, autoplay, handleReady, handleStateChange, handleError]);

    return (
        <div className={`relative bg-black ${className}`}>
            {isLoading && !hasError && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
                    <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto mb-2"></div>
                        <p className="text-sm text-slate-400">Loading player...</p>
                    </div>
                </div>
            )}
            {hasError && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
                    <div className="text-center text-white">
                        <svg
                            className="w-12 h-12 mx-auto mb-2 text-slate-500"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.5}
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                            />
                        </svg>
                        <p className="text-sm text-slate-400">Video unavailable</p>
                    </div>
                </div>
            )}
            <div
                ref={containerRef}
                className="w-full h-full"
                style={{ minHeight: "200px" }}
            />
        </div>
    );
};

export default YouTubePlayer;
