import React, {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    useMemo,
} from "react";
import { api, setAuthToken } from "../lib/apiClient";

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
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string) => Promise<void>;
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
        const token = localStorage.getItem("vc_token");
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
            setAuthToken(null);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Fetch user on mount
    useEffect(() => {
        fetchUser();
    }, [fetchUser]);

    const login = useCallback(async (email: string, password: string) => {
        setIsLoading(true);
        setError(null);

        try {
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
                    ?.detail || "Login failed";
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const register = useCallback(async (email: string, password: string) => {
        setIsLoading(true);
        setError(null);

        try {
            await api.post("/auth/register", { email, password });

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

    const logout = useCallback(() => {
        setAuthToken(null);
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
            logout,
            refetchUser,
        }),
        [user, isAuthenticated, isLoading, error, login, register, logout, refetchUser]
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
