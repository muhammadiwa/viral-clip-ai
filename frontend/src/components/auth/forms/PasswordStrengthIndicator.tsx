import React from 'react';
import { motion } from 'framer-motion';

export type StrengthLevel = 'weak' | 'medium' | 'strong';

export interface PasswordStrengthProps {
    password: string;
}

// Calculate password strength
export const calculatePasswordStrength = (password: string): StrengthLevel => {
    if (!password) return 'weak';

    let score = 0;

    // Length checks
    if (password.length >= 8) score += 1;
    if (password.length >= 12) score += 1;

    // Character variety checks
    if (/[a-z]/.test(password)) score += 1;
    if (/[A-Z]/.test(password)) score += 1;
    if (/[0-9]/.test(password)) score += 1;
    if (/[^a-zA-Z0-9]/.test(password)) score += 1;

    // Determine strength level
    if (score <= 2) return 'weak';
    if (score <= 4) return 'medium';
    return 'strong';
};

const strengthConfig = {
    weak: {
        color: 'bg-red-500',
        textColor: 'text-red-600',
        label: 'Lemah',
        width: '33%',
    },
    medium: {
        color: 'bg-yellow-500',
        textColor: 'text-yellow-600',
        label: 'Sedang',
        width: '66%',
    },
    strong: {
        color: 'bg-green-500',
        textColor: 'text-green-600',
        label: 'Kuat',
        width: '100%',
    },
};

export const PasswordStrengthIndicator: React.FC<PasswordStrengthProps> = ({
    password,
}) => {
    const strength = calculatePasswordStrength(password);
    const config = strengthConfig[strength];

    return (
        <div className="mt-2 space-y-1" data-testid="password-strength-indicator">
            {/* Progress bar */}
            <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: config.width }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                    className={`h-full ${config.color} rounded-full`}
                    data-testid="strength-bar"
                />
            </div>

            {/* Label */}
            <p className={`text-xs ${config.textColor}`} data-testid="strength-label">
                Kekuatan password: <span className="font-medium">{config.label}</span>
            </p>
        </div>
    );
};

export default PasswordStrengthIndicator;
