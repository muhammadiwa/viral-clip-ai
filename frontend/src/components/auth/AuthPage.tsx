import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Auth3DScene } from './3d';
import { AuthForm } from './forms/AuthForm';

export type AuthMode = 'login' | 'register' | 'forgot-password' | 'reset-password';

interface AuthPageProps {
    defaultMode?: AuthMode;
    resetToken?: string;
}

// Animation configuration from design spec
const ANIMATION_CONFIG = {
    formTransition: 0.3,      // 300ms
    staggerDelay: 0.05,       // 50ms per element
    logoEntrance: 0.6,        // 600ms
};

// Container animation with stagger children
const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: ANIMATION_CONFIG.staggerDelay,
            delayChildren: 0.1,
        },
    },
};

// Logo entrance animation - scale and fade with slight bounce
const logoVariants = {
    hidden: {
        opacity: 0,
        scale: 0.8,
        y: -20,
    },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: {
            duration: ANIMATION_CONFIG.logoEntrance,
            ease: [0.34, 1.56, 0.64, 1], // Custom spring-like easing
        },
    },
};

// Form container animation
const formContainerVariants = {
    hidden: {
        opacity: 0,
        y: 30,
        scale: 0.95,
    },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: {
            duration: 0.5,
            ease: 'easeOut',
            delay: 0.2,
        },
    },
};

// Footer animation
const footerVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: {
        opacity: 1,
        y: 0,
        transition: {
            duration: 0.4,
            delay: 0.5,
        },
    },
};

export const AuthPage: React.FC<AuthPageProps> = ({
    defaultMode = 'login',
    resetToken,
}) => {
    const [mode, setMode] = useState<AuthMode>(defaultMode);

    const handleModeChange = (newMode: AuthMode) => {
        setMode(newMode);
    };

    const handleSuccess = () => {
        // Navigation will be handled by the auth context/router
        window.location.href = '/';
    };

    return (
        <div className="min-h-screen w-full flex flex-col lg:flex-row">
            {/* 3D Animation Side - Hidden on mobile, shown as background on tablet, full side on desktop */}
            <div className="hidden lg:block lg:w-1/2 xl:w-3/5 relative overflow-hidden bg-gradient-to-br from-slate-900 to-slate-800">
                <Auth3DScene isInteractive={true} />
                {/* Gradient overlay for better visual integration */}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent to-slate-900/20 pointer-events-none" />
            </div>

            {/* Mobile/Tablet background - 3D scene as background */}
            <div className="lg:hidden fixed inset-0 z-0">
                <div className="absolute inset-0 bg-gradient-to-br from-slate-900 to-slate-800">
                    <Auth3DScene isInteractive={false} />
                </div>
                {/* Dark overlay for better form readability */}
                <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
            </div>

            {/* Form Side */}
            <div className="flex-1 lg:w-1/2 xl:w-2/5 flex items-center justify-center p-4 sm:p-6 md:p-8 relative z-10 min-h-screen">
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    animate="visible"
                    className="w-full max-w-md"
                >
                    {/* Form Container with gradient background */}
                    <motion.div
                        variants={formContainerVariants}
                        className="auth-form-container bg-white/95 lg:bg-white rounded-2xl shadow-xl p-6 sm:p-8 backdrop-blur-md lg:backdrop-blur-none relative overflow-hidden"
                    >
                        {/* Animated gradient background effect */}
                        <div className="auth-gradient-bg absolute inset-0 opacity-30 pointer-events-none" />

                        <div className="relative z-10">
                            {/* Logo with enhanced entrance animation */}
                            <motion.div
                                variants={logoVariants}
                                className="text-center mb-6"
                            >
                                {/* Logo icon with glow effect */}
                                <motion.div
                                    className="inline-flex items-center justify-center w-12 h-12 mb-3 rounded-xl bg-gradient-to-br from-primary to-primary/80 shadow-lg shadow-primary/25"
                                    whileHover={{ scale: 1.05, rotate: 5 }}
                                    transition={{ type: 'spring', stiffness: 400 }}
                                >
                                    <svg
                                        className="w-6 h-6 text-white"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        stroke="currentColor"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                                        />
                                    </svg>
                                </motion.div>

                                <h1 className="text-2xl font-bold text-slate-900">
                                    <span className="text-primary">Viral</span> Clip AI
                                </h1>
                                <motion.p
                                    className="text-sm text-slate-500 mt-1"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: 0.4 }}
                                >
                                    {mode === 'login' && 'Masuk ke akun Anda'}
                                    {mode === 'register' && 'Buat akun baru'}
                                    {mode === 'forgot-password' && 'Reset password Anda'}
                                    {mode === 'reset-password' && 'Buat password baru'}
                                </motion.p>
                            </motion.div>

                            {/* Auth Form */}
                            <AuthForm
                                mode={mode}
                                onModeChange={handleModeChange}
                                onSuccess={handleSuccess}
                                resetToken={resetToken}
                            />
                        </div>
                    </motion.div>

                    {/* Footer */}
                    <motion.p
                        variants={footerVariants}
                        className="text-center text-xs text-slate-400 lg:text-slate-500 mt-4"
                    >
                        © 2024 Viral Clip AI. All rights reserved.
                    </motion.p>
                </motion.div>
            </div>
        </div>
    );
};

export default AuthPage;
