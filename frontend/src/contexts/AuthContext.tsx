import React, {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    useMemo,
} from "react";
import { api, setAuthToken, getStoredToken, clearAllTokens } from "../lib/apiClient";

export interface UserDTO {
    id: number;
    email: string;
    name: string | null;
    avatar_url: string | null;
    credits: number;
    created_at: string;
}

export interface AuthContextValue {
    user: UserDTO | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    register: (email: string, password: string, captchaToken?: string) => Promise<void>;
    googleLogin: (accessToken: string, rememberMe?: boolean) => Promise<void>;
    forgotPassword: (email: string) => Promise<void>;
    resetPassword: (token: string, newPassword: string) => Promise<void>;
    verifyResetToken: (token: string) => Promise<boolean>;
    logout: () => void;
    refetchUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
    children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<UserDTO | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchUser = useCallback(async () => {
        const token = getStoredToken();
        if (!token) {
            setIsLoading(false);
            return;
        }

        try {
            const response = await api.get("/auth/me");
            setUser(response.data);
            setError(null);
        } catch (err) {
            console.warn("Failed to fetch user:", err);
            setUser(null);
            // Token might be invalid, clear it
            clearAllTokens();
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Fetch user on mount
    useEffect(() => {
        fetchUser();
    }, [fetchUser]);

    const login = useCallback(async (email: string, password: string, rememberMe: boolean = false) => {
        setIsLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams();
            params.append("username", email);
            params.append("password", password);

            const response = await api.post("/auth/login", params, {
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
            });

            // Store token with remember me preference
            setAuthToken(response.data.access_token, rememberMe);

            // Fetch user data after login
            const userResponse = await api.get("/auth/me");
            setUser(userResponse.data);
        } catch (err: unknown) {
            const errorMessage =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Login failed";
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const register = useCallback(async (email: string, password: string, captchaToken?: string) => {
        setIsLoading(true);
        setError(null);

        try {
            const payload: { email: string; password: string; captcha_token?: string } = { email, password };
            if (captchaToken) {
                payload.captcha_token = captchaToken;
            }
            await api.post("/auth/register", payload);

            // Auto-login after registration
            const params = new URLSearchParams();
            params.append("username", email);
            params.append("password", password);

            const response = await api.post("/auth/login", params, {
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
            });

            setAuthToken(response.data.access_token);

            // Fetch user data after login
            const userResponse = await api.get("/auth/me");
            setUser(userResponse.data);
        } catch (err: unknown) {
            const errorMessage =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Registration failed";
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const googleLogin = useCallback(async (accessToken: string, rememberMe: boolean = false) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await api.post("/auth/google", { access_token: accessToken });

            // Store token with remember me preference
            setAuthToken(response.data.access_token, rememberMe);

            // Fetch user data after login
            const userResponse = await api.get("/auth/me");
            setUser(userResponse.data);
        } catch (err: unknown) {
            const errorMessage =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Google login failed";
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const forgotPassword = useCallback(async (email: string) => {
        setIsLoading(true);
        setError(null);

        try {
            await api.post("/auth/forgot-password", { email });
            // Always succeeds to prevent email enumeration
        } catch (err: unknown) {
            const errorMessage =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Failed to send reset email";
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const resetPassword = useCallback(async (token: string, newPassword: string) => {
        setIsLoading(true);
        setError(null);

        try {
            await api.post("/auth/reset-password", { token, new_password: newPassword });
        } catch (err: unknown) {
            const errorMessage =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Failed to reset password";
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const verifyResetToken = useCallback(async (token: string): Promise<boolean> => {
        try {
            const response = await api.get(`/auth/verify-reset-token/${token}`);
            return response.data.valid;
        } catch {
            return false;
        }
    }, []);

    const logout = useCallback(() => {
        clearAllTokens();
        setUser(null);
        setError(null);
    }, []);

    const refetchUser = useCallback(async () => {
        setIsLoading(true);
        await fetchUser();
    }, [fetchUser]);

    const isAuthenticated = useMemo(() => user !== null, [user]);

    const value = useMemo<AuthContextValue>(
        () => ({
            user,
            isAuthenticated,
            isLoading,
            error,
            login,
            register,
            googleLogin,
            forgotPassword,
            resetPassword,
            verifyResetToken,
            logout,
            refetchUser,
        }),
        [user, isAuthenticated, isLoading, error, login, register, googleLogin, forgotPassword, resetPassword, verifyResetToken, logout, refetchUser]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}

export default AuthContext;
