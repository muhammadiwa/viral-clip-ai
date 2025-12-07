import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../../contexts/AuthContext';
import { PasswordStrengthIndicator } from './PasswordStrengthIndicator';
import { GoogleAuthButton } from '../GoogleAuthButton';
import { CaptchaWidget, isCaptchaEnabled } from './CaptchaWidget';

export type AuthMode = 'login' | 'register' | 'forgot-password' | 'reset-password';

export interface AuthFormProps {
    mode: AuthMode;
    onModeChange: (mode: AuthMode) => void;
    onSuccess: () => void;
    resetToken?: string;
}

export interface FormState {
    email: string;
    password: string;
    confirmPassword: string;
    name: string;
    rememberMe: boolean;
    captchaToken: string;
}

export interface FormErrors {
    email?: string;
    password?: string;
    confirmPassword?: string;
    name?: string;
    captcha?: string;
    general?: string;
}

// Email validation regex
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Validate email format
export const validateEmail = (email: string): string | undefined => {
    if (!email) return 'Email wajib diisi';
    if (!EMAIL_REGEX.test(email)) return 'Format email tidak valid';
    return undefined;
};

// Validate password
export const validatePassword = (password: string): string | undefined => {
    if (!password) return 'Password wajib diisi';
    if (password.length < 6) return 'Password minimal 6 karakter';
    return undefined;
};

// Validate confirm password
export const validateConfirmPassword = (password: string, confirmPassword: string): string | undefined => {
    if (!confirmPassword) return 'Konfirmasi password wajib diisi';
    if (password !== confirmPassword) return 'Password tidak cocok';
    return undefined;
};

// Validate name
export const validateName = (name: string): string | undefined => {
    if (!name) return 'Nama wajib diisi';
    if (name.length < 2) return 'Nama minimal 2 karakter';
    return undefined;
};

const formVariants = {
    initial: { opacity: 0, x: 20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -20 },
};

const shakeAnimation = {
    x: [0, -10, 10, -10, 10, 0],
    transition: { duration: 0.5 },
};

export const AuthForm: React.FC<AuthFormProps> = ({
    mode,
    onModeChange,
    onSuccess,
    resetToken,
}) => {
    const { login, register, googleLogin, forgotPassword, resetPassword, verifyResetToken, isLoading } = useAuth();

    const [tokenValid, setTokenValid] = useState<boolean | null>(null);
    const [tokenChecking, setTokenChecking] = useState(false);

    const [formState, setFormState] = useState<FormState>({
        email: '',
        password: '',
        confirmPassword: '',
        name: '',
        rememberMe: false,
        captchaToken: '',
    });

    // Verify reset token when in reset-password mode
    React.useEffect(() => {
        if (mode === 'reset-password' && resetToken) {
            setTokenChecking(true);
            verifyResetToken(resetToken)
                .then((valid) => {
                    setTokenValid(valid);
                })
                .finally(() => {
                    setTokenChecking(false);
                });
        }
    }, [mode, resetToken, verifyResetToken]);

    const [errors, setErrors] = useState<FormErrors>({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [showSuccess, setShowSuccess] = useState(false);
    const [shouldShake, setShouldShake] = useState(false);

    // Update form field
    const updateField = useCallback((field: keyof FormState, value: string | boolean) => {
        setFormState(prev => ({ ...prev, [field]: value }));
        // Clear error when user starts typing
        if (errors[field as keyof FormErrors]) {
            setErrors(prev => ({ ...prev, [field]: undefined }));
        }
    }, [errors]);

    // Validate form based on mode
    const validateForm = useCallback((): boolean => {
        const newErrors: FormErrors = {};

        // Email validation for all modes except reset-password
        if (mode !== 'reset-password') {
            const emailError = validateEmail(formState.email);
            if (emailError) newErrors.email = emailError;
        }

        // Password validation for login, register, reset-password
        if (mode === 'login' || mode === 'register' || mode === 'reset-password') {
            const passwordError = validatePassword(formState.password);
            if (passwordError) newErrors.password = passwordError;
        }

        // Additional validations for register mode
        if (mode === 'register') {
            const nameError = validateName(formState.name);
            if (nameError) newErrors.name = nameError;

            const confirmError = validateConfirmPassword(formState.password, formState.confirmPassword);
            if (confirmError) newErrors.confirmPassword = confirmError;

            // CAPTCHA validation - only if CAPTCHA is enabled
            if (isCaptchaEnabled() && !formState.captchaToken) {
                newErrors.captcha = 'Silakan selesaikan verifikasi CAPTCHA';
            }
        }

        // Confirm password for reset-password mode
        if (mode === 'reset-password') {
            const confirmError = validateConfirmPassword(formState.password, formState.confirmPassword);
            if (confirmError) newErrors.confirmPassword = confirmError;
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    }, [mode, formState]);

    // Handle form submission
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!validateForm()) {
            setShouldShake(true);
            setTimeout(() => setShouldShake(false), 500);
            return;
        }

        setIsSubmitting(true);
        setErrors({});

        try {
            if (mode === 'login') {
                await login(formState.email, formState.password, formState.rememberMe);
                setShowSuccess(true);
                setTimeout(() => onSuccess(), 800);
            } else if (mode === 'register') {
                await register(formState.email, formState.password, formState.captchaToken);
                setShowSuccess(true);
                setTimeout(() => onSuccess(), 800);
            } else if (mode === 'forgot-password') {
                await forgotPassword(formState.email);
                setShowSuccess(true);
            } else if (mode === 'reset-password') {
                if (!resetToken) {
                    throw new Error('Token reset tidak valid');
                }
                await resetPassword(resetToken, formState.password);
                setShowSuccess(true);
                setTimeout(() => onModeChange('login'), 800);
            }
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : 'Terjadi kesalahan';
            setErrors({ general: errorMessage });
            setShouldShake(true);
            setTimeout(() => setShouldShake(false), 500);
        } finally {
            setIsSubmitting(false);
        }
    };

    // Handle mode change while preserving email
    const handleModeChange = (newMode: AuthMode) => {
        // Preserve email when switching modes
        setFormState(prev => ({
            ...prev,
            password: '',
            confirmPassword: '',
            name: '',
            captchaToken: '',
        }));
        setErrors({});
        onModeChange(newMode);
    };

    // Handle Google login success
    const handleGoogleSuccess = useCallback(async (accessToken: string) => {
        setIsSubmitting(true);
        setErrors({});

        try {
            await googleLogin(accessToken, formState.rememberMe);
            setShowSuccess(true);
            setTimeout(() => onSuccess(), 800);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : 'Login Google gagal';
            setErrors({ general: errorMessage });
            setShouldShake(true);
            setTimeout(() => setShouldShake(false), 500);
        } finally {
            setIsSubmitting(false);
        }
    }, [googleLogin, formState.rememberMe, onSuccess]);

    // Handle Google login error
    const handleGoogleError = useCallback((error: string) => {
        setErrors({ general: error });
        setShouldShake(true);
        setTimeout(() => setShouldShake(false), 500);
    }, []);

    const isFormLoading = isLoading || isSubmitting || tokenChecking;
    const isTokenInvalid = mode === 'reset-password' && tokenValid === false && !tokenChecking;

    return (
        <motion.div
            animate={shouldShake ? shakeAnimation : {}}
            data-testid="auth-form"
        >
            <AnimatePresence mode="wait">
                <motion.form
                    key={mode}
                    variants={formVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    transition={{ duration: 0.3 }}
                    onSubmit={handleSubmit}
                    className="space-y-4"
                    data-testid={`auth-form-${mode}`}
                >
                    {/* Token Checking State */}
                    {mode === 'reset-password' && tokenChecking && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-600 text-center"
                        >
                            Memverifikasi token...
                        </motion.div>
                    )}

                    {/* Invalid Token Error */}
                    {mode === 'reset-password' && tokenValid === false && !tokenChecking && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600"
                            data-testid="invalid-token-error"
                        >
                            <p className="font-medium mb-2">Link reset password tidak valid atau sudah kadaluarsa.</p>
                            <button
                                type="button"
                                onClick={() => onModeChange('forgot-password')}
                                className="text-primary font-medium hover:text-primary/80 transition-colors underline"
                            >
                                Minta link reset baru
                            </button>
                        </motion.div>
                    )}

                    {/* General Error */}
                    {errors.general && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600"
                            data-testid="auth-error"
                        >
                            {errors.general}
                        </motion.div>
                    )}

                    {/* Success Message */}
                    {showSuccess && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-600 text-center"
                        >
                            {mode === 'forgot-password'
                                ? 'Link reset password telah dikirim ke email Anda'
                                : 'Berhasil! Mengalihkan...'}
                        </motion.div>
                    )}

                    {/* Name Field - Register only */}
                    {mode === 'register' && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="space-y-1"
                        >
                            <label className="block text-sm font-medium text-slate-700">
                                Nama
                            </label>
                            <input
                                type="text"
                                value={formState.name}
                                onChange={(e) => updateField('name', e.target.value)}
                                className={`w-full px-4 py-2.5 rounded-lg border transition-all duration-200
                  focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                  ${errors.name ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'}`}
                                placeholder="Nama lengkap"
                                disabled={isFormLoading}
                                data-testid="name-input"
                            />
                            {errors.name && (
                                <p className="text-xs text-red-500 mt-1">{errors.name}</p>
                            )}
                        </motion.div>
                    )}

                    {/* Email Field - All modes except reset-password */}
                    {mode !== 'reset-password' && (
                        <div className="space-y-1">
                            <label className="block text-sm font-medium text-slate-700">
                                Email
                            </label>
                            <input
                                type="email"
                                value={formState.email}
                                onChange={(e) => updateField('email', e.target.value)}
                                className={`w-full px-4 py-2.5 rounded-lg border transition-all duration-200
                  focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                  ${errors.email ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'}`}
                                placeholder="email@example.com"
                                disabled={isFormLoading}
                                data-testid="email-input"
                            />
                            {errors.email && (
                                <p className="text-xs text-red-500 mt-1">{errors.email}</p>
                            )}
                        </div>
                    )}

                    {/* Password Field - Login, Register, Reset-password */}
                    {(mode === 'login' || mode === 'register' || mode === 'reset-password') && (
                        <div className="space-y-1">
                            <label className="block text-sm font-medium text-slate-700">
                                {mode === 'reset-password' ? 'Password Baru' : 'Password'}
                            </label>
                            <input
                                type="password"
                                value={formState.password}
                                onChange={(e) => updateField('password', e.target.value)}
                                className={`w-full px-4 py-2.5 rounded-lg border transition-all duration-200
                  focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                  ${errors.password ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'}`}
                                placeholder="••••••••"
                                disabled={isFormLoading}
                                data-testid="password-input"
                            />
                            {errors.password && (
                                <p className="text-xs text-red-500 mt-1">{errors.password}</p>
                            )}
                            {/* Password Strength Indicator - Register and Reset-password only */}
                            {(mode === 'register' || mode === 'reset-password') && formState.password && (
                                <PasswordStrengthIndicator password={formState.password} />
                            )}
                        </div>
                    )}

                    {/* Confirm Password Field - Register and Reset-password */}
                    {(mode === 'register' || mode === 'reset-password') && (
                        <div className="space-y-1">
                            <label className="block text-sm font-medium text-slate-700">
                                Konfirmasi Password
                            </label>
                            <input
                                type="password"
                                value={formState.confirmPassword}
                                onChange={(e) => updateField('confirmPassword', e.target.value)}
                                className={`w-full px-4 py-2.5 rounded-lg border transition-all duration-200
                  focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                  ${errors.confirmPassword ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'}`}
                                placeholder="••••••••"
                                disabled={isFormLoading}
                                data-testid="confirm-password-input"
                            />
                            {errors.confirmPassword && (
                                <p className="text-xs text-red-500 mt-1">{errors.confirmPassword}</p>
                            )}
                        </div>
                    )}

                    {/* CAPTCHA Widget - Register only */}
                    {mode === 'register' && (
                        <div className="space-y-1">
                            <CaptchaWidget
                                onVerify={(token) => updateField('captchaToken', token)}
                                onExpire={() => updateField('captchaToken', '')}
                                onError={() => updateField('captchaToken', '')}
                            />
                            {errors.captcha && (
                                <p className="text-xs text-red-500 mt-1 text-center">{errors.captcha}</p>
                            )}
                        </div>
                    )}

                    {/* Remember Me & Forgot Password - Login only */}
                    {mode === 'login' && (
                        <div className="flex items-center justify-between">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={formState.rememberMe}
                                    onChange={(e) => updateField('rememberMe', e.target.checked)}
                                    className="w-4 h-4 rounded border-slate-300 text-primary focus:ring-primary/20"
                                    data-testid="remember-me-checkbox"
                                />
                                <span className="text-sm text-slate-600">Ingat saya</span>
                            </label>
                            <button
                                type="button"
                                onClick={() => handleModeChange('forgot-password')}
                                className="text-sm text-primary hover:text-primary/80 transition-colors"
                            >
                                Lupa password?
                            </button>
                        </div>
                    )}

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={isFormLoading || showSuccess || isTokenInvalid}
                        className="w-full py-2.5 px-4 bg-primary text-white font-semibold rounded-lg
              hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/20
              disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200
              flex items-center justify-center gap-2"
                        data-testid="submit-button"
                    >
                        {isFormLoading ? (
                            <>
                                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                    <circle
                                        className="opacity-25"
                                        cx="12"
                                        cy="12"
                                        r="10"
                                        stroke="currentColor"
                                        strokeWidth="4"
                                        fill="none"
                                    />
                                    <path
                                        className="opacity-75"
                                        fill="currentColor"
                                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                    />
                                </svg>
                                <span>Memproses...</span>
                            </>
                        ) : showSuccess ? (
                            <span>✓ Berhasil</span>
                        ) : (
                            <span>
                                {mode === 'login' && 'Masuk'}
                                {mode === 'register' && 'Daftar'}
                                {mode === 'forgot-password' && 'Kirim Link Reset'}
                                {mode === 'reset-password' && 'Reset Password'}
                            </span>
                        )}
                    </button>

                    {/* Google OAuth - Login and Register only */}
                    {(mode === 'login' || mode === 'register') && (
                        <>
                            {/* Divider */}
                            <div className="relative my-4">
                                <div className="absolute inset-0 flex items-center">
                                    <div className="w-full border-t border-slate-200"></div>
                                </div>
                                <div className="relative flex justify-center text-sm">
                                    <span className="px-2 bg-white text-slate-500">atau</span>
                                </div>
                            </div>

                            {/* Google Auth Button */}
                            <GoogleAuthButton
                                onSuccess={handleGoogleSuccess}
                                onError={handleGoogleError}
                                disabled={isFormLoading || showSuccess}
                                mode={mode}
                            />
                        </>
                    )}

                    {/* Mode Switch Links */}
                    <div className="text-center text-sm text-slate-600 pt-2">
                        {mode === 'login' && (
                            <p>
                                Belum punya akun?{' '}
                                <button
                                    type="button"
                                    onClick={() => handleModeChange('register')}
                                    className="text-primary font-medium hover:text-primary/80 transition-colors"
                                >
                                    Daftar
                                </button>
                            </p>
                        )}
                        {mode === 'register' && (
                            <p>
                                Sudah punya akun?{' '}
                                <button
                                    type="button"
                                    onClick={() => handleModeChange('login')}
                                    className="text-primary font-medium hover:text-primary/80 transition-colors"
                                >
                                    Masuk
                                </button>
                            </p>
                        )}
                        {(mode === 'forgot-password' || mode === 'reset-password') && (
                            <p>
                                <button
                                    type="button"
                                    onClick={() => handleModeChange('login')}
                                    className="text-primary font-medium hover:text-primary/80 transition-colors"
                                >
                                    ← Kembali ke Login
                                </button>
                            </p>
                        )}
                    </div>
                </motion.form>
            </AnimatePresence>
        </motion.div>
    );
};

export default AuthForm;
