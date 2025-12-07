import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

// GPU capability detection
export const detectGPUCapability = (): boolean => {
    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');

        if (!gl) return false;

        // Check for basic WebGL support
        const debugInfo = (gl as WebGLRenderingContext).getExtension('WEBGL_debug_renderer_info');
        if (debugInfo) {
            const renderer = (gl as WebGLRenderingContext).getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            // Check for software renderers or known low-performance GPUs
            const lowPerformanceIndicators = ['swiftshader', 'llvmpipe', 'software', 'microsoft basic'];
            return !lowPerformanceIndicators.some(indicator =>
                renderer.toLowerCase().includes(indicator)
            );
        }

        return true;
    } catch {
        return false;
    }
};

// Floating shape component
interface FloatingShapeProps {
    delay?: number;
    duration?: number;
    size?: number;
    color?: string;
    initialX?: number;
    initialY?: number;
}

const FloatingShape: React.FC<FloatingShapeProps> = ({
    delay = 0,
    duration = 8,
    size = 60,
    color = 'rgba(255, 106, 0, 0.15)',
    initialX = 0,
    initialY = 0,
}) => {
    return (
        <motion.div
            className="absolute rounded-lg"
            style={{
                width: size,
                height: size,
                backgroundColor: color,
                left: `${initialX}%`,
                top: `${initialY}%`,
                filter: 'blur(1px)',
            }}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{
                opacity: [0.3, 0.6, 0.3],
                scale: [0.8, 1.1, 0.8],
                x: [0, 30, -20, 0],
                y: [0, -40, 20, 0],
                rotate: [0, 90, 180, 270, 360],
            }}
            transition={{
                duration,
                delay,
                repeat: Infinity,
                ease: 'easeInOut',
            }}
        />
    );
};

// Film reel icon (2D version)
const FilmReelIcon: React.FC<{ className?: string }> = ({ className }) => (
    <motion.svg
        className={className}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        animate={{ rotate: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
    >
        {/* Outer ring */}
        <circle cx="50" cy="50" r="45" stroke="rgba(255, 106, 0, 0.3)" strokeWidth="4" fill="none" />
        {/* Inner ring */}
        <circle cx="50" cy="50" r="15" stroke="rgba(255, 106, 0, 0.5)" strokeWidth="3" fill="rgba(255, 106, 0, 0.1)" />
        {/* Spokes */}
        {[0, 60, 120, 180, 240, 300].map((angle, i) => (
            <line
                key={i}
                x1={50 + Math.cos((angle * Math.PI) / 180) * 15}
                y1={50 + Math.sin((angle * Math.PI) / 180) * 15}
                x2={50 + Math.cos((angle * Math.PI) / 180) * 42}
                y2={50 + Math.sin((angle * Math.PI) / 180) * 42}
                stroke="rgba(255, 106, 0, 0.3)"
                strokeWidth="2"
            />
        ))}
        {/* Film holes */}
        {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((angle, i) => (
            <circle
                key={i}
                cx={50 + Math.cos((angle * Math.PI) / 180) * 38}
                cy={50 + Math.sin((angle * Math.PI) / 180) * 38}
                r="3"
                fill="rgba(255, 106, 0, 0.4)"
            />
        ))}
    </motion.svg>
);

// Video frame icon (2D version)
const VideoFrameIcon: React.FC<{
    className?: string;
    delay?: number;
    x?: number;
    y?: number;
}> = ({ className, delay = 0, x = 0, y = 0 }) => (
    <motion.div
        className={`absolute ${className}`}
        style={{ left: `${x}%`, top: `${y}%` }}
        initial={{ opacity: 0, y: 20 }}
        animate={{
            opacity: [0.4, 0.7, 0.4],
            y: [0, -15, 0],
        }}
        transition={{
            duration: 4,
            delay,
            repeat: Infinity,
            ease: 'easeInOut',
        }}
    >
        <div className="relative w-20 h-12 rounded-lg border-2 border-primary/30 bg-slate-900/20 backdrop-blur-sm">
            {/* Play button */}
            <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-6 h-6 rounded-full bg-primary/40 flex items-center justify-center">
                    <div className="w-0 h-0 border-l-[8px] border-l-white/80 border-y-[5px] border-y-transparent ml-1" />
                </div>
            </div>
        </div>
    </motion.div>
);

// Particle dot
const ParticleDot: React.FC<{ delay: number; x: number; y: number }> = ({ delay, x, y }) => (
    <motion.div
        className="absolute w-1 h-1 rounded-full bg-primary/60"
        style={{ left: `${x}%`, top: `${y}%` }}
        animate={{
            opacity: [0, 0.8, 0],
            scale: [0.5, 1.5, 0.5],
            y: [0, -30, 0],
        }}
        transition={{
            duration: 3,
            delay,
            repeat: Infinity,
            ease: 'easeInOut',
        }}
    />
);

export const Fallback2DAnimation: React.FC = () => {
    const [particles] = useState(() =>
        Array.from({ length: 20 }, (_, i) => ({
            id: i,
            x: Math.random() * 100,
            y: Math.random() * 100,
            delay: Math.random() * 3,
        }))
    );

    return (
        <div
            className="absolute inset-0 overflow-hidden"
            data-testid="fallback-2d-animation"
        >
            {/* Animated gradient background */}
            <motion.div
                className="absolute inset-0"
                animate={{
                    background: [
                        'linear-gradient(135deg, rgba(255, 106, 0, 0.1) 0%, rgba(255, 154, 77, 0.05) 50%, transparent 100%)',
                        'linear-gradient(225deg, rgba(255, 106, 0, 0.15) 0%, rgba(255, 154, 77, 0.08) 50%, transparent 100%)',
                        'linear-gradient(315deg, rgba(255, 106, 0, 0.1) 0%, rgba(255, 154, 77, 0.05) 50%, transparent 100%)',
                        'linear-gradient(135deg, rgba(255, 106, 0, 0.1) 0%, rgba(255, 154, 77, 0.05) 50%, transparent 100%)',
                    ],
                }}
                transition={{
                    duration: 10,
                    repeat: Infinity,
                    ease: 'easeInOut',
                }}
            />

            {/* Floating shapes */}
            <FloatingShape delay={0} size={80} initialX={10} initialY={20} />
            <FloatingShape delay={1} size={60} initialX={70} initialY={60} color="rgba(255, 154, 77, 0.12)" />
            <FloatingShape delay={2} size={100} initialX={80} initialY={10} color="rgba(255, 106, 0, 0.08)" />
            <FloatingShape delay={1.5} size={50} initialX={20} initialY={70} />
            <FloatingShape delay={0.5} size={70} initialX={50} initialY={40} color="rgba(255, 154, 77, 0.1)" />

            {/* Central film reel */}
            <div className="absolute inset-0 flex items-center justify-center">
                <FilmReelIcon className="w-48 h-48 opacity-30" />
            </div>

            {/* Floating video frames */}
            <VideoFrameIcon x={15} y={25} delay={0} />
            <VideoFrameIcon x={75} y={15} delay={1} />
            <VideoFrameIcon x={65} y={70} delay={2} />
            <VideoFrameIcon x={10} y={65} delay={1.5} />

            {/* Particle dots */}
            {particles.map((particle) => (
                <ParticleDot
                    key={particle.id}
                    x={particle.x}
                    y={particle.y}
                    delay={particle.delay}
                />
            ))}

            {/* Subtle vignette overlay */}
            <div
                className="absolute inset-0 pointer-events-none"
                style={{
                    background: 'radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,0.1) 100%)',
                }}
            />
        </div>
    );
};

export default Fallback2DAnimation;
