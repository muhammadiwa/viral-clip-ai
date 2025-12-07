import React, { useRef, useCallback } from 'react';
import ReCAPTCHA from 'react-google-recaptcha';

export interface CaptchaWidgetProps {
    onVerify: (token: string) => void;
    onExpire: () => void;
    onError?: () => void;
}

const RECAPTCHA_ENABLED = import.meta.env.VITE_RECAPTCHA_ENABLED === 'true';
const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || '';

// Export function to check if CAPTCHA is enabled (for use in form validation)
export const isCaptchaEnabled = (): boolean => {
    return RECAPTCHA_ENABLED && !!RECAPTCHA_SITE_KEY;
};

export const CaptchaWidget: React.FC<CaptchaWidgetProps> = ({
    onVerify,
    onExpire,
    onError,
}) => {
    const recaptchaRef = useRef<ReCAPTCHA>(null);

    const handleChange = useCallback((token: string | null) => {
        if (token) {
            onVerify(token);
        }
    }, [onVerify]);

    const handleExpired = useCallback(() => {
        onExpire();
    }, [onExpire]);

    const handleError = useCallback(() => {
        if (onError) {
            onError();
        }
        onExpire(); // Also clear the token on error
    }, [onError, onExpire]);

    // Don't render if CAPTCHA is disabled or no site key is configured
    if (!RECAPTCHA_ENABLED) {
        return null;
    }

    if (!RECAPTCHA_SITE_KEY) {
        console.warn('reCAPTCHA enabled but site key not configured. CAPTCHA verification disabled.');
        return null;
    }

    return (
        <div className="flex justify-center" data-testid="captcha-widget">
            <ReCAPTCHA
                ref={recaptchaRef}
                sitekey={RECAPTCHA_SITE_KEY}
                onChange={handleChange}
                onExpired={handleExpired}
                onErrored={handleError}
                theme="light"
                size="normal"
            />
        </div>
    );
};

export default CaptchaWidget;
