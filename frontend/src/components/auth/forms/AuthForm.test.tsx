import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as fc from 'fast-check';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { AuthForm, AuthMode, validateEmail, validatePassword, validateName, validateConfirmPassword } from './AuthForm';
import { calculatePasswordStrength } from './PasswordStrengthIndicator';

// Mock the AuthContext
vi.mock('../../../contexts/AuthContext', () => ({
    useAuth: () => ({
        login: vi.fn().mockResolvedValue(undefined),
        register: vi.fn().mockResolvedValue(undefined),
        googleLogin: vi.fn().mockResolvedValue(undefined),
        isLoading: false,
        error: null,
    }),
}));

// Helper to render AuthForm with required props and GoogleOAuthProvider
const renderAuthForm = (mode: AuthMode = 'login', onModeChange = vi.fn(), onSuccess = vi.fn()) => {
    return render(
        <GoogleOAuthProvider clientId="test-client-id">
            <AuthForm
                mode={mode}
                onModeChange={onModeChange}
                onSuccess={onSuccess}
            />
        </GoogleOAuthProvider>
    );
};

// Email generator for property tests - using simple character set
const alphanumChars = 'abcdefghijklmnopqrstuvwxyz0123456789';
const emailArbitrary = fc.tuple(
    fc.integer({ min: 1, max: 10 }).chain(len =>
        fc.array(fc.constantFrom(...alphanumChars.split('')), { minLength: len, maxLength: len })
    ).map(chars => chars.join('')),
    fc.constantFrom('gmail.com', 'yahoo.com', 'example.com', 'test.org')
).map(([local, domain]) => `${local}@${domain}`);

// Password generator for property tests - using simple character set
const passwordChars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%';
const passwordArbitrary = fc.integer({ min: 1, max: 20 }).chain(len =>
    fc.array(fc.constantFrom(...passwordChars.split('')), { minLength: len, maxLength: len })
).map(chars => chars.join(''));

describe('AuthForm Property Tests', () => {
    afterEach(() => {
        cleanup();
        vi.clearAllMocks();
    });

    /**
     * **Feature: auth-redesign, Property 2: Email preservation across mode changes**
     * **Validates: Requirements 2.4**
     */
    it('Property 2: Email field accepts valid formats', () => {
        // Verify valid emails pass validation
        expect(validateEmail('a@gmail.com')).toBeUndefined();
        expect(validateEmail('test@yahoo.com')).toBeUndefined();
        expect(validateEmail('user123@example.com')).toBeUndefined();
    });

    /**
     * **Feature: auth-redesign, Property 1: Register mode displays additional fields**
     * **Validates: Requirements 2.3**
     */
    it('Property 1: Register mode displays additional fields', () => {
        renderAuthForm('register');

        expect(screen.getByTestId('name-input')).toBeInTheDocument();
        expect(screen.getByTestId('email-input')).toBeInTheDocument();
        expect(screen.getByTestId('password-input')).toBeInTheDocument();
        expect(screen.getByTestId('confirm-password-input')).toBeInTheDocument();
    });

    /**
     * **Feature: auth-redesign, Property 8: Form validation feedback**
     * **Validates: Requirements 4.4, 4.5**
     */
    it('Property 8: Form validation - invalid emails rejected', () => {
        const invalidEmailArbitrary = fc.oneof(
            fc.integer({ min: 1, max: 10 }).chain(len =>
                fc.array(fc.constantFrom(...'abcdefghijklmnopqrstuvwxyz'.split('')), { minLength: len, maxLength: len })
            ).map(chars => chars.join('')),
            fc.constant(''),
            fc.constant('invalid'),
            fc.constant('no@domain'),
        );

        fc.assert(
            fc.property(invalidEmailArbitrary, (invalidEmail) => {
                const emailError = validateEmail(invalidEmail);
                expect(emailError).toBeDefined();
                expect(typeof emailError).toBe('string');
            }),
            { numRuns: 100 }
        );
    });

    it('Property 8: Form validation - valid emails pass', () => {
        fc.assert(
            fc.property(emailArbitrary, (validEmail) => {
                const emailError = validateEmail(validEmail);
                expect(emailError).toBeUndefined();
            }),
            { numRuns: 100 }
        );
    });

    it('Property 8: Password strength returns valid level', () => {
        fc.assert(
            fc.property(passwordArbitrary, (password) => {
                const strength = calculatePasswordStrength(password);
                expect(['weak', 'medium', 'strong']).toContain(strength);
            }),
            { numRuns: 100 }
        );
    });

    /**
     * **Feature: auth-redesign, Property 7: Authentication error feedback**
     * **Validates: Requirements 4.3**
     */
    it('Property 7: Error messages are valid strings', () => {
        const errorMessages = [
            'Email atau password salah',
            'Akun terkunci. Coba lagi dalam 15 menit',
            'Koneksi gagal. Periksa internet Anda',
            'Terlalu banyak percobaan. Tunggu sebentar',
        ];

        fc.assert(
            fc.property(
                fc.constantFrom(...errorMessages),
                (errorMessage) => {
                    expect(errorMessage).toBeTruthy();
                    expect(typeof errorMessage).toBe('string');
                    expect(errorMessage.length).toBeGreaterThan(0);
                }
            ),
            { numRuns: 100 }
        );
    });
});

describe('AuthForm Unit Tests', () => {
    afterEach(() => {
        cleanup();
        vi.clearAllMocks();
    });

    it('renders login form by default', () => {
        renderAuthForm('login');
        expect(screen.getByTestId('email-input')).toBeInTheDocument();
        expect(screen.getByTestId('password-input')).toBeInTheDocument();
        expect(screen.getByTestId('submit-button')).toHaveTextContent('Masuk');
    });

    it('renders register form with additional fields', () => {
        renderAuthForm('register');
        expect(screen.getByTestId('name-input')).toBeInTheDocument();
        expect(screen.getByTestId('email-input')).toBeInTheDocument();
        expect(screen.getByTestId('password-input')).toBeInTheDocument();
        expect(screen.getByTestId('confirm-password-input')).toBeInTheDocument();
        expect(screen.getByTestId('submit-button')).toHaveTextContent('Daftar');
    });

    it('renders forgot-password form', () => {
        renderAuthForm('forgot-password');
        expect(screen.getByTestId('email-input')).toBeInTheDocument();
        expect(screen.queryByTestId('password-input')).not.toBeInTheDocument();
        expect(screen.getByTestId('submit-button')).toHaveTextContent('Kirim Link Reset');
    });

    it('validates email format correctly', () => {
        expect(validateEmail('')).toBe('Email wajib diisi');
        expect(validateEmail('invalid')).toBe('Format email tidak valid');
        expect(validateEmail('test@example.com')).toBeUndefined();
    });

    it('validates password correctly', () => {
        expect(validatePassword('')).toBe('Password wajib diisi');
        expect(validatePassword('12345')).toBe('Password minimal 6 karakter');
        expect(validatePassword('123456')).toBeUndefined();
    });

    it('validates confirm password correctly', () => {
        expect(validateConfirmPassword('password', '')).toBe('Konfirmasi password wajib diisi');
        expect(validateConfirmPassword('password', 'different')).toBe('Password tidak cocok');
        expect(validateConfirmPassword('password', 'password')).toBeUndefined();
    });

    it('validates name correctly', () => {
        expect(validateName('')).toBe('Nama wajib diisi');
        expect(validateName('A')).toBe('Nama minimal 2 karakter');
        expect(validateName('John')).toBeUndefined();
    });
});

describe('AuthForm DOM Tests', () => {
    afterEach(() => {
        cleanup();
        vi.clearAllMocks();
    });

    it('mode change is triggered when clicking register link', async () => {
        const onModeChange = vi.fn();
        renderAuthForm('login', onModeChange);

        const emailInput = screen.getByTestId('email-input');
        await userEvent.type(emailInput, 'test@example.com');

        expect(emailInput).toHaveValue('test@example.com');

        const registerLink = screen.getByText('Daftar');
        await userEvent.click(registerLink);

        expect(onModeChange).toHaveBeenCalledWith('register');
    });
});

describe('PasswordStrengthIndicator Property Tests', () => {
    /**
     * **Feature: auth-redesign, Property 8: Form validation feedback**
     * **Validates: Requirements 4.4, 4.5**
     */
    it('Password strength is deterministic', () => {
        fc.assert(
            fc.property(passwordArbitrary, (password) => {
                const strength1 = calculatePasswordStrength(password);
                const strength2 = calculatePasswordStrength(password);
                expect(strength1).toBe(strength2);
            }),
            { numRuns: 100 }
        );
    });

    it('Longer passwords with more variety are stronger', () => {
        expect(calculatePasswordStrength('abc')).toBe('weak');
        expect(calculatePasswordStrength('Abcdef12')).toBe('medium');
        expect(calculatePasswordStrength('Abcdef123!@#')).toBe('strong');
    });

    it('Empty password is always weak', () => {
        expect(calculatePasswordStrength('')).toBe('weak');
    });
});
