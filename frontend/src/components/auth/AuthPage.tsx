import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Auth3DScene } from './3d';
import { AuthForm } from './forms/AuthForm';

export type AuthMode = 'login' | 'register' | 'forgot-password' | 'reset-password';

interface AuthPageProps {
    defaultMode?: AuthMode;
    resetToken?: string;
}

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
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, ease: 'easeOut' }}
                    className="w-full max-w-md"
                >
                    {/* Form Container */}
                    <div className="bg-white/95 lg:bg-white rounded-2xl shadow-xl p-6 sm:p-8 backdrop-blur-md lg:backdrop-blur-none">
                        {/* Logo */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.6, delay: 0.1 }}
                            className="text-center mb-6"
                        >
                            <h1 className="text-2xl font-bold text-slate-900">
                                <span className="text-primary">Viral</span> Clip AI
                            </h1>
                            <p className="text-sm text-slate-500 mt-1">
                                {mode === 'login' && 'Masuk ke akun Anda'}
                                {mode === 'register' && 'Buat akun baru'}
                                {mode === 'forgot-password' && 'Reset password Anda'}
                                {mode === 'reset-password' && 'Buat password baru'}
                            </p>
                        </motion.div>

                        {/* Auth Form */}
                        <AuthForm
                            mode={mode}
                            onModeChange={handleModeChange}
                            onSuccess={handleSuccess}
                            resetToken={resetToken}
                        />
                    </div>

                    {/* Footer */}
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5, delay: 0.3 }}
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
