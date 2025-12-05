import React, {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    useMemo,
} from "react";
import { api } from "../lib/apiClient";

export type Theme = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

export interface ThemeContextValue {
    theme: Theme;
    resolvedTheme: ResolvedTheme;
    toggleTheme: () => void;
    setTheme: (theme: Theme) => void;
    isLoading: boolean;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const THEME_STORAGE_KEY = "vc_theme";

function getSystemTheme(): ResolvedTheme {
    if (typeof window !== "undefined" && window.matchMedia) {
        return window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light";
    }
    return "light";
}

function resolveTheme(theme: Theme): ResolvedTheme {
    if (theme === "system") {
        return getSystemTheme();
    }
    return theme;
}

function applyThemeToDocument(resolvedTheme: ResolvedTheme): void {
    if (typeof document !== "undefined") {
        const root = document.documentElement;
        root.classList.remove("light", "dark");
        root.classList.add(resolvedTheme);
    }
}

interface ThemeProviderProps {
    children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
    const [theme, setThemeState] = useState<Theme>(() => {
        // Initialize from localStorage for immediate render
        if (typeof localStorage !== "undefined") {
            const stored = localStorage.getItem(THEME_STORAGE_KEY);
            if (stored === "light" || stored === "dark" || stored === "system") {
                return stored;
            }
        }
        return "light";
    });
    const [isLoading, setIsLoading] = useState(true);

    const resolvedTheme = useMemo(() => resolveTheme(theme), [theme]);

    // Apply theme to document whenever it changes
    useEffect(() => {
        applyThemeToDocument(resolvedTheme);
    }, [resolvedTheme]);

    // Listen for system theme changes when theme is "system"
    useEffect(() => {
        if (theme !== "system") return;

        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handleChange = () => {
            applyThemeToDocument(getSystemTheme());
        };

        mediaQuery.addEventListener("change", handleChange);
        return () => mediaQuery.removeEventListener("change", handleChange);
    }, [theme]);

    // Fetch theme from API on mount (only if authenticated)
    useEffect(() => {
        const fetchTheme = async () => {
            // Only fetch from API if user is authenticated
            const token = localStorage.getItem("vc_token");
            if (!token) {
                setIsLoading(false);
                return;
            }

            try {
                const response = await api.get("/users/preferences");
                const apiTheme = response.data.theme as Theme;
                if (apiTheme === "light" || apiTheme === "dark" || apiTheme === "system") {
                    setThemeState(apiTheme);
                    localStorage.setItem(THEME_STORAGE_KEY, apiTheme);
                }
            } catch (error) {
                // API failed, keep localStorage value (offline fallback)
                console.warn("Failed to fetch theme preference from API:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchTheme();
    }, []);

    const setTheme = useCallback(async (newTheme: Theme) => {
        setThemeState(newTheme);
        localStorage.setItem(THEME_STORAGE_KEY, newTheme);

        // Only sync to API if authenticated
        const token = localStorage.getItem("vc_token");
        if (!token) {
            return;
        }

        // Sync to API
        try {
            await api.put("/users/preferences", { theme: newTheme });
        } catch (error) {
            console.warn("Failed to sync theme preference to API:", error);
            // Theme is still saved locally, will sync on next successful request
        }
    }, []);

    const toggleTheme = useCallback(() => {
        const nextTheme: Theme = resolvedTheme === "light" ? "dark" : "light";
        setTheme(nextTheme);
    }, [resolvedTheme, setTheme]);

    const value = useMemo<ThemeContextValue>(
        () => ({
            theme,
            resolvedTheme,
            toggleTheme,
            setTheme,
            isLoading,
        }),
        [theme, resolvedTheme, toggleTheme, setTheme, isLoading]
    );

    return (
        <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
    );
};

export function useTheme(): ThemeContextValue {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error("useTheme must be used within a ThemeProvider");
    }
    return context;
}

export default ThemeContext;
