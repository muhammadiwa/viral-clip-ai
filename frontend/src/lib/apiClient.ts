import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: false
});

// Token storage keys
export const TOKEN_KEY = "vc_token";
export const TOKEN_EXPIRY_KEY = "vc_token_expiry";
export const REMEMBER_ME_KEY = "vc_remember_me";

// Token expiration durations (in milliseconds)
export const REMEMBER_ME_DURATION = 30 * 24 * 60 * 60 * 1000; // 30 days

/**
 * Check if a token is expired based on stored expiry time
 */
export const isTokenExpired = (): boolean => {
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY) || sessionStorage.getItem(TOKEN_EXPIRY_KEY);
  if (!expiry) return true;
  return Date.now() > parseInt(expiry, 10);
};

/**
 * Get the stored token from either localStorage or sessionStorage
 */
export const getStoredToken = (): string | null => {
  // Check localStorage first (remember me)
  const localToken = localStorage.getItem(TOKEN_KEY);
  if (localToken) {
    if (!isTokenExpired()) {
      return localToken;
    }
    // Token expired, clear it
    clearAllTokens();
    return null;
  }

  // Check sessionStorage (session token)
  const sessionToken = sessionStorage.getItem(TOKEN_KEY);
  if (sessionToken) {
    return sessionToken;
  }

  return null;
};

/**
 * Clear all stored tokens from both localStorage and sessionStorage
 */
export const clearAllTokens = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
  localStorage.removeItem(REMEMBER_ME_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_EXPIRY_KEY);
  delete api.defaults.headers.common["Authorization"];
};

/**
 * Set auth token with optional remember me functionality
 * @param token - The JWT token or null to clear
 * @param rememberMe - If true, store in localStorage with 30-day expiry; otherwise use sessionStorage
 */
export const setAuthToken = (token: string | null, rememberMe: boolean = false): void => {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;

    if (rememberMe) {
      // Store in localStorage with expiry for remember me
      const expiry = Date.now() + REMEMBER_ME_DURATION;
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(TOKEN_EXPIRY_KEY, expiry.toString());
      localStorage.setItem(REMEMBER_ME_KEY, "true");
      // Clear sessionStorage to avoid conflicts
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_EXPIRY_KEY);
    } else {
      // Store in sessionStorage for session-only token
      sessionStorage.setItem(TOKEN_KEY, token);
      // Clear localStorage to avoid conflicts
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXPIRY_KEY);
      localStorage.removeItem(REMEMBER_ME_KEY);
    }
  } else {
    clearAllTokens();
  }
};

// Initialize token from storage on load
const savedToken = getStoredToken();
if (savedToken) {
  api.defaults.headers.common["Authorization"] = `Bearer ${savedToken}`;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setAuthToken(null);
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
