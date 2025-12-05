import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTheme } from "../../contexts/ThemeContext";

interface ThemeToggleProps {
    className?: string;
}

/**
 * Theme toggle button with sun/moon icon animation.
 * Switches between light and dark color schemes.
 *
 * Requirements: 5.1, 5.2
 * - WHEN the Navbar renders THEN the Navbar SHALL display a theme toggle button
 * - WHEN a user clicks the theme toggle THEN the Navbar SHALL switch between light and dark color schemes
 */
const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = "" }) => {
    const { resolvedTheme, toggleTheme, isLoading } = useTheme();

    const isDark = resolvedTheme === "dark";

    // Animation variants for icon transitions
    const iconVariants = {
        initial: {
            scale: 0,
            rotate: -180,
            opacity: 0
        },
        animate: {
            scale: 1,
            rotate: 0,
            opacity: 1,
            transition: {
                type: "spring",
                stiffness: 200,
                damping: 15,
                duration: 0.4
            }
        },
        exit: {
            scale: 0,
            rotate: 180,
            opacity: 0,
            transition: {
                duration: 0.2
            }
        }
    };

    return (
        <motion.button
            onClick={toggleTheme}
            disabled={isLoading}
            className={`relative p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors overflow-hidden ${className}`}
            whileTap={{ scale: 0.9 }}
            whileHover={{ scale: 1.05 }}
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
            <div className="w-5 h-5 relative">
                <AnimatePresence mode="wait" initial={false}>
                    {isDark ? (
                        <motion.svg
                            key="sun"
                            className="w-5 h-5 text-yellow-400 absolute inset-0"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                            variants={iconVariants}
                            initial="initial"
                            animate="animate"
                            exit="exit"
                        >
                            <path
                                fillRule="evenodd"
                                d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
                                clipRule="evenodd"
                            />
                        </motion.svg>
                    ) : (
                        <motion.svg
                            key="moon"
                            className="w-5 h-5 text-slate-600 dark:text-slate-300 absolute inset-0"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                            variants={iconVariants}
                            initial="initial"
                            animate="animate"
                            exit="exit"
                        >
                            <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                        </motion.svg>
                    )}
                </AnimatePresence>
            </div>
        </motion.button>
    );
};

export default ThemeToggle;
