import React, { useCallback } from 'react';
import { useGoogleLogin, TokenResponse } from '@react-oauth/google';
import { motion } from 'framer-motion';

export interface GoogleAuthButtonProps {
    onSuccess: (credential: string) => void;
    onError: (error: string) => void;
    disabled?: boolean;
    mode?: 'login' | 'register';
}

// Check if Google OAuth is enabled via environment variable
const isGoogleOAuthEnabled = import.meta.env.VITE_GOOGLE_OAUTH_ENABLED === 'true';
const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

/**
 * Google Sign-In button component using @react-oauth/google
 * Handles OAuth flow and returns the access token on success
 * 
 * Requirements: 3.1
 * - WHEN a user clicks the Google login button THEN the Auth_System SHALL initiate the Google OAuth flow
 */
export const GoogleAuthButton: React.FC<GoogleAuthButtonProps> = ({
    onSuccess,
    onError,
    disabled = false,
    mode = 'login',
}) => {
    // Don't render if Google OAuth is disabled or client_id is not configured
    if (!isGoogleOAuthEnabled || !googleClientId || googleClientId === 'your-google-client-id.apps.googleusercontent.com') {
        return null;
    }

    return <GoogleAuthButtonInner onSuccess={onSuccess} onError={onError} disabled={disabled} mode={mode} />;
};

/**
 * Inner component that uses the Google OAuth hook
 * Separated to avoid hook call when OAuth is disabled
 */
const GoogleAuthButtonInner: React.FC<GoogleAuthButtonProps> = ({
    onSuccess,
    onError,
    disabled = false,
    mode = 'login',
}) => {
    const handleGoogleSuccess = useCallback((tokenResponse: TokenResponse) => {
        // Pass the access token to the parent component
        onSuccess(tokenResponse.access_token);
    }, [onSuccess]);

    const handleGoogleError = useCallback(() => {
        onError('Login Google gagal. Silakan coba lagi.');
    }, [onError]);

    const googleLogin = useGoogleLogin({
        onSuccess: handleGoogleSuccess,
        onError: handleGoogleError,
        flow: 'implicit',
    });

    const handleClick = useCallback(() => {
        if (!disabled) {
            googleLogin();
        }
    }, [disabled, googleLogin]);

    return (
        <motion.button
            type="button"
            onClick={handleClick}
            disabled={disabled}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            whileHover={{
                scale: disabled ? 1 : 1.02,
                boxShadow: disabled ? undefined : '0 4px 12px rgba(0, 0, 0, 0.1)',
            }}
            whileTap={{ scale: disabled ? 1 : 0.98 }}
            className={`
                auth-google-btn w-full py-3 px-4 rounded-lg border border-slate-200
                bg-white hover:bg-slate-50 
                flex items-center justify-center gap-3
                transition-all duration-200
                ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}
            `}
            data-testid="google-auth-button"
        >
            {/* Google Icon with subtle animation */}
            <motion.div
                whileHover={{ rotate: disabled ? 0 : 5 }}
                transition={{ type: 'spring', stiffness: 400 }}
            >
                <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                    className="flex-shrink-0"
                >
                    <path
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                        fill="#4285F4"
                    />
                    <path
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                        fill="#34A853"
                    />
                    <path
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                        fill="#FBBC05"
                    />
                    <path
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                        fill="#EA4335"
                    />
                </svg>
            </motion.div>
            <span className="text-sm font-medium text-slate-700">
                {mode === 'login' ? 'Masuk dengan Google' : 'Daftar dengan Google'}
            </span>
        </motion.button>
    );
};

export default GoogleAuthButton;

/**
 * Helper function to check if Google OAuth is available
 * Can be used by parent components to conditionally render dividers, etc.
 */
export const isGoogleAuthAvailable = (): boolean => {
    return isGoogleOAuthEnabled &&
        !!googleClientId &&
        googleClientId !== 'your-google-client-id.apps.googleusercontent.com';
};
