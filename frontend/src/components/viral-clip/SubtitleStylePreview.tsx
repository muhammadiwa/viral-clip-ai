import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";

type StyleJson = {
    fontFamily?: string;
    fontSize?: number;
    fontColor?: string;
    outlineColor?: string;
    outlineWidth?: number;
    animation?: string;
    highlightColor?: string;
    highlightStyle?: string;
    bold?: boolean;
};

type Props = {
    styleJson: StyleJson;
    isSelected: boolean;
};

const SAMPLE_TEXT = "This is how your subtitles will look";
const SAMPLE_WORDS = SAMPLE_TEXT.split(" ");

const SubtitleStylePreview: React.FC<Props> = ({ styleJson, isSelected }) => {
    const [currentWordIndex, setCurrentWordIndex] = useState(0);
    const [typewriterIndex, setTypewriterIndex] = useState(0);

    const animationType = styleJson.animation || "none";
    const hasWordHighlight = animationType === "word_highlight";
    const hasTypewriter = animationType === "typewriter";
    const hasAnimation = hasWordHighlight;

    const fontFamily = styleJson.fontFamily || "Arial";
    const fontColor = styleJson.fontColor || "#FFFFFF";
    const highlightColor = styleJson.highlightColor || "#FFD700";
    const outlineColor = styleJson.outlineColor || "#000000";
    const outlineWidth = styleJson.outlineWidth || 2;
    const highlightStyle = styleJson.highlightStyle || "color";
    const isBold = styleJson.bold !== false;

    // Animate through words for word_highlight
    useEffect(() => {
        if (!hasWordHighlight) return;

        const interval = setInterval(() => {
            setCurrentWordIndex((prev) => (prev + 1) % SAMPLE_WORDS.length);
        }, 400);

        return () => clearInterval(interval);
    }, [hasWordHighlight]);

    // Typewriter animation
    useEffect(() => {
        if (!hasTypewriter) return;

        const interval = setInterval(() => {
            setTypewriterIndex((prev) => {
                if (prev >= SAMPLE_TEXT.length) return 0;
                return prev + 1;
            });
        }, 80);

        return () => clearInterval(interval);
    }, [hasTypewriter]);

    const getWordStyle = (index: number): React.CSSProperties => {
        const isHighlighted = hasAnimation && index === currentWordIndex;

        const baseStyle: React.CSSProperties = {
            fontFamily,
            fontWeight: isBold ? "bold" : "normal",
            color: fontColor,
            textShadow: `
        -${outlineWidth}px -${outlineWidth}px 0 ${outlineColor},
        ${outlineWidth}px -${outlineWidth}px 0 ${outlineColor},
        -${outlineWidth}px ${outlineWidth}px 0 ${outlineColor},
        ${outlineWidth}px ${outlineWidth}px 0 ${outlineColor}
      `,
            transition: "all 0.15s ease",
        };

        if (!isHighlighted) return baseStyle;

        // Apply highlight style
        switch (highlightStyle) {
            case "color":
                return { ...baseStyle, color: highlightColor };
            case "background":
                return {
                    ...baseStyle,
                    backgroundColor: highlightColor,
                    padding: "2px 4px",
                    borderRadius: "4px",
                    color: "#FFFFFF",
                };
            case "scale":
                return {
                    ...baseStyle,
                    color: highlightColor,
                    transform: "scale(1.2)",
                    display: "inline-block",
                };
            case "glow":
            case "neon_glow":
                return {
                    ...baseStyle,
                    color: highlightColor,
                    textShadow: `
                        -${outlineWidth}px -${outlineWidth}px 0 ${outlineColor},
                        ${outlineWidth}px -${outlineWidth}px 0 ${outlineColor},
                        -${outlineWidth}px ${outlineWidth}px 0 ${outlineColor},
                        ${outlineWidth}px ${outlineWidth}px 0 ${outlineColor},
                        0 0 10px ${highlightColor},
                        0 0 20px ${highlightColor},
                        0 0 30px ${highlightColor}
                    `,
                };
            case "underline":
                return {
                    ...baseStyle,
                    color: highlightColor,
                    textDecoration: "underline",
                    textDecorationColor: highlightColor,
                    textDecorationThickness: "3px",
                    textUnderlineOffset: "4px",
                };
            case "gradient":
                // CSS doesn't support text gradient easily, use highlight color
                return { ...baseStyle, color: highlightColor };
            case "comic_burst":
                return {
                    ...baseStyle,
                    color: highlightColor,
                    transform: "scale(1.3) rotate(-3deg)",
                    display: "inline-block",
                };
            default:
                return { ...baseStyle, color: highlightColor };
        }
    };

    return (
        <div
            className={`
        relative h-20 rounded-lg overflow-hidden flex items-end justify-center pb-3
        ${isSelected ? "ring-2 ring-primary" : ""}
      `}
            style={{
                background: "linear-gradient(to bottom, #1a1a2e 0%, #16213e 100%)",
            }}
        >
            {/* Fake video background pattern */}
            <div className="absolute inset-0 opacity-20">
                <div className="absolute top-2 left-2 w-8 h-8 rounded-full bg-white/30" />
                <div className="absolute top-4 right-4 w-12 h-6 rounded bg-white/20" />
            </div>

            {/* Subtitle text */}
            <div className="relative z-10 text-center px-2">
                {hasTypewriter ? (
                    // Typewriter animation - characters appear one by one
                    <div
                        className="text-xs leading-tight"
                        style={{
                            fontFamily,
                            fontWeight: isBold ? "bold" : "normal",
                            color: fontColor,
                            textShadow: `
                                -${outlineWidth}px -${outlineWidth}px 0 ${outlineColor},
                                ${outlineWidth}px -${outlineWidth}px 0 ${outlineColor},
                                -${outlineWidth}px ${outlineWidth}px 0 ${outlineColor},
                                ${outlineWidth}px ${outlineWidth}px 0 ${outlineColor}
                            `,
                        }}
                    >
                        {SAMPLE_TEXT.slice(0, typewriterIndex)}
                        <span className="animate-pulse">|</span>
                    </div>
                ) : (
                    // Word highlight or standard animation
                    <div className="flex flex-wrap justify-center gap-1 text-xs leading-tight">
                        {SAMPLE_WORDS.map((word, index) => (
                            <motion.span
                                key={index}
                                style={getWordStyle(index)}
                                animate={
                                    hasAnimation && index === currentWordIndex
                                        ? { scale: highlightStyle === "scale" ? 1.15 : 1 }
                                        : { scale: 1 }
                                }
                                transition={{ duration: 0.15 }}
                            >
                                {word}
                            </motion.span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default SubtitleStylePreview;
