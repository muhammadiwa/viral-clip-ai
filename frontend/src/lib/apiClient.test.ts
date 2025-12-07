import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';
import {
    setAuthToken,
    getStoredToken,
    clearAllTokens,
    isTokenExpired,
    TOKEN_KEY,
    TOKEN_EXPIRY_KEY,
    REMEMBER_ME_KEY,
    REMEMBER_ME_DURATION,
} from './apiClient';

// Mock localStorage and sessionStorage
const createStorageMock = () => {
    let store: Record<string, string> = {};
    return {
        getItem: vi.fn((key: string) => store[key] || null),
        setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
        removeItem: vi.fn((key: string) => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; }),
        get length() { return Object.keys(store).length; },
        key: vi.fn((index: number) => Object.keys(store)[index] || null),
    };
};

describe('Token Persistence Property Tests', () => {
    let localStorageMock: ReturnType<typeof createStorageMock>;
    let sessionStorageMock: ReturnType<typeof createStorageMock>;
    let originalLocalStorage: Storage;
    let originalSessionStorage: Storage;

    beforeEach(() => {
        localStorageMock = createStorageMock();
        sessionStorageMock = createStorageMock();
        originalLocalStorage = global.localStorage;
        originalSessionStorage = global.sessionStorage;
        Object.defineProperty(global, 'localStorage', { value: localStorageMock, writable: true });
        Object.defineProperty(global, 'sessionStorage', { value: sessionStorageMock, writable: true });
    });

    afterEach(() => {
        Object.defineProperty(global, 'localStorage', { value: originalLocalStorage, writable: true });
        Object.defineProperty(global, 'sessionStorage', { value: originalSessionStorage, writable: true });
        vi.clearAllMocks();
    });

    // Token generator - simple alphanumeric tokens
    const tokenArbitrary = fc.stringOf(
        fc.constantFrom(...'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.split('')),
        { minLength: 10, maxLength: 100 }
    );

    /**
     * **Feature: auth-redesign, Property 9: Remember me token expiration**
     * **Validates: Requirements 7.1, 7.2**
     * 
     * For any login with "Remember me" checked, the issued token SHALL have an expiration of 30 days.
     * For any login without "Remember me", the token SHALL be a session token.
     */
    describe('Property 9: Remember me token expiration', () => {
        it('Remember me stores token in localStorage with 30-day expiry', () => {
            fc.assert(
                fc.property(tokenArbitrary, (token) => {
                    // Clear any previous state
                    localStorageMock.clear();
                    sessionStorageMock.clear();

                    const beforeTime = Date.now();
                    setAuthToken(token, true); // rememberMe = true
                    const afterTime = Date.now();

                    // Token should be in localStorage
                    expect(localStorageMock.setItem).toHaveBeenCalledWith(TOKEN_KEY, token);
                    expect(localStorageMock.setItem).toHaveBeenCalledWith(REMEMBER_ME_KEY, "true");

                    // Expiry should be set to ~30 days from now
                    const expiryCall = localStorageMock.setItem.mock.calls.find(
                        (call: [string, string]) => call[0] === TOKEN_EXPIRY_KEY
                    );
                    expect(expiryCall).toBeDefined();

                    const expiry = parseInt(expiryCall![1], 10);
                    // Allow 1 second tolerance for timing differences
                    const tolerance = 1000;
                    const expectedMinExpiry = beforeTime + REMEMBER_ME_DURATION - tolerance;
                    const expectedMaxExpiry = afterTime + REMEMBER_ME_DURATION + tolerance;

                    expect(expiry).toBeGreaterThanOrEqual(expectedMinExpiry);
                    expect(expiry).toBeLessThanOrEqual(expectedMaxExpiry);

                    // Session storage should be cleared
                    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
                }),
                { numRuns: 100 }
            );
        });

        it('Without remember me, token is stored in sessionStorage only', () => {
            fc.assert(
                fc.property(tokenArbitrary, (token) => {
                    // Clear any previous state
                    localStorageMock.clear();
                    sessionStorageMock.clear();

                    setAuthToken(token, false); // rememberMe = false

                    // Token should be in sessionStorage
                    expect(sessionStorageMock.setItem).toHaveBeenCalledWith(TOKEN_KEY, token);

                    // localStorage should be cleared
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_EXPIRY_KEY);
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(REMEMBER_ME_KEY);
                }),
                { numRuns: 100 }
            );
        });

        it('Token expiry is exactly 30 days for remember me', () => {
            const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
            expect(REMEMBER_ME_DURATION).toBe(thirtyDaysMs);
        });
    });

    /**
     * **Feature: auth-redesign, Property 10: Logout clears all tokens**
     * **Validates: Requirements 7.4**
     * 
     * For any logout action, all stored authentication tokens (localStorage and sessionStorage)
     * SHALL be cleared regardless of how the user originally logged in.
     */
    describe('Property 10: Logout clears all tokens', () => {
        it('clearAllTokens removes tokens from localStorage when remember me was used', () => {
            fc.assert(
                fc.property(tokenArbitrary, (token) => {
                    // Setup: store token with remember me
                    localStorageMock.clear();
                    sessionStorageMock.clear();
                    setAuthToken(token, true);

                    // Clear mocks to track only clearAllTokens calls
                    localStorageMock.removeItem.mockClear();
                    sessionStorageMock.removeItem.mockClear();

                    // Act: clear all tokens (simulates logout)
                    clearAllTokens();

                    // Assert: localStorage should be cleared
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_EXPIRY_KEY);
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(REMEMBER_ME_KEY);

                    // Assert: sessionStorage should also be cleared
                    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
                    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_EXPIRY_KEY);
                }),
                { numRuns: 100 }
            );
        });

        it('clearAllTokens removes tokens from sessionStorage when remember me was not used', () => {
            fc.assert(
                fc.property(tokenArbitrary, (token) => {
                    // Setup: store token without remember me
                    localStorageMock.clear();
                    sessionStorageMock.clear();
                    setAuthToken(token, false);

                    // Clear mocks to track only clearAllTokens calls
                    localStorageMock.removeItem.mockClear();
                    sessionStorageMock.removeItem.mockClear();

                    // Act: clear all tokens (simulates logout)
                    clearAllTokens();

                    // Assert: both storages should be cleared
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_EXPIRY_KEY);
                    expect(localStorageMock.removeItem).toHaveBeenCalledWith(REMEMBER_ME_KEY);
                    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
                    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(TOKEN_EXPIRY_KEY);
                }),
                { numRuns: 100 }
            );
        });

        it('After clearAllTokens, getStoredToken returns null', () => {
            fc.assert(
                fc.property(
                    tokenArbitrary,
                    fc.boolean(),
                    (token, rememberMe) => {
                        // Setup: store token
                        localStorageMock.clear();
                        sessionStorageMock.clear();
                        setAuthToken(token, rememberMe);

                        // Act: clear all tokens
                        clearAllTokens();

                        // Assert: getStoredToken should return null
                        const storedToken = getStoredToken();
                        expect(storedToken).toBeNull();
                    }
                ),
                { numRuns: 100 }
            );
        });
    });
});
