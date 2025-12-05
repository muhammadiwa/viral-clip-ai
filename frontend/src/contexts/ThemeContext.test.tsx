/**
 * **Feature: navbar-navigation, Property 3: Theme Toggle Round-Trip Consistency**
 * **Validates: Requirements 5.2, 5.4**
 *
 * Property: For any initial theme state T, clicking the theme toggle SHALL switch
 * to the opposite theme, persist it to the backend API, and upon page reload,
 * the theme SHALL be restored from the server to the last saved value.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import * as fc from "fast-check";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";
import { ThemeProvider, useTheme, Theme } from "./ThemeContext";

// Mock the API module
vi.mock("../lib/apiClient", () => ({
    api: {
        get: vi.fn(),
        put: vi.fn(),
    },
}));

import { api } from "../lib/apiClient";

const mockedApi = api as {
    get: ReturnType<typeof vi.fn>;
    put: ReturnType<typeof vi.fn>;
};

// Arbitrary for valid theme values
const themeArbitrary = fc.constantFrom<Theme>("light", "dark", "system");

// Wrapper component for the hook
const wrapper = ({ children }: { children: React.ReactNode }) => (
    <ThemeProvider>{children}</ThemeProvider>
);

describe("ThemeContext Property Tests", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
        document.documentElement.classList.remove("light", "dark");
        // Set auth token so API calls are made
        localStorage.setItem("vc_token", "test-token");
    });

    afterEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
    });

    /**
     * **Feature: navbar-navigation, Property 3: Theme Toggle Round-Trip Consistency**
     * **Validates: Requirements 5.2, 5.4**
     */
    it("Property 3: setTheme persists to localStorage and API for any valid theme", async () => {
        await fc.assert(
            fc.asyncProperty(themeArbitrary, async (theme) => {
                // Reset state
                localStorage.clear();
                localStorage.setItem("vc_token", "test-token");
                vi.clearAllMocks();

                // Mock API responses
                mockedApi.get.mockResolvedValue({ data: { theme: "light", language: "en" } });
                mockedApi.put.mockResolvedValue({ data: { theme, language: "en" } });

                const { result } = renderHook(() => useTheme(), { wrapper });

                // Wait for initial load
                await waitFor(() => {
                    expect(result.current.isLoading).toBe(false);
                });

                // Set the theme
                await act(async () => {
                    await result.current.setTheme(theme);
                });

                // Verify localStorage was updated
                expect(localStorage.getItem("vc_theme")).toBe(theme);

                // Verify API was called with correct theme
                expect(mockedApi.put).toHaveBeenCalledWith("/users/preferences", { theme });

                // Verify context state was updated
                expect(result.current.theme).toBe(theme);
            }),
            { numRuns: 100 }
        );
    });

    /**
     * **Feature: navbar-navigation, Property 3: Theme Toggle Round-Trip Consistency**
     * **Validates: Requirements 5.2, 5.4**
     */
    it("Property 3: toggleTheme switches between light and dark for any initial resolved theme", async () => {
        // Test toggle behavior: light -> dark, dark -> light
        const resolvedThemes: Array<"light" | "dark"> = ["light", "dark"];

        for (const initialTheme of resolvedThemes) {
            localStorage.clear();
            localStorage.setItem("vc_token", "test-token");
            vi.clearAllMocks();

            // Mock API to return initial theme
            mockedApi.get.mockResolvedValue({ data: { theme: initialTheme, language: "en" } });
            mockedApi.put.mockResolvedValue({ data: { theme: initialTheme === "light" ? "dark" : "light", language: "en" } });

            const { result } = renderHook(() => useTheme(), { wrapper });

            await waitFor(() => {
                expect(result.current.isLoading).toBe(false);
            });

            const expectedNextTheme = initialTheme === "light" ? "dark" : "light";

            await act(async () => {
                result.current.toggleTheme();
            });

            // Verify toggle switched to opposite theme
            expect(result.current.theme).toBe(expectedNextTheme);
            expect(localStorage.getItem("vc_theme")).toBe(expectedNextTheme);
            expect(mockedApi.put).toHaveBeenCalledWith("/users/preferences", { theme: expectedNextTheme });
        }
    });

    /**
     * **Feature: navbar-navigation, Property 3: Theme Toggle Round-Trip Consistency**
     * **Validates: Requirements 5.2, 5.4**
     */
    it("Property 3: theme is restored from API on mount for any valid theme", async () => {
        await fc.assert(
            fc.asyncProperty(themeArbitrary, async (savedTheme) => {
                localStorage.clear();
                localStorage.setItem("vc_token", "test-token");
                vi.clearAllMocks();

                // Mock API to return the saved theme (simulating page reload)
                mockedApi.get.mockResolvedValue({ data: { theme: savedTheme, language: "en" } });

                const { result } = renderHook(() => useTheme(), { wrapper });

                await waitFor(() => {
                    expect(result.current.isLoading).toBe(false);
                });

                // Verify theme was restored from API
                expect(result.current.theme).toBe(savedTheme);
                expect(localStorage.getItem("vc_theme")).toBe(savedTheme);
            }),
            { numRuns: 100 }
        );
    });

    /**
     * **Feature: navbar-navigation, Property 3: Theme Toggle Round-Trip Consistency**
     * **Validates: Requirements 5.2, 5.4**
     */
    it("Property 3: localStorage fallback works when API fails for any valid theme", async () => {
        await fc.assert(
            fc.asyncProperty(themeArbitrary, async (localTheme) => {
                localStorage.clear();
                localStorage.setItem("vc_token", "test-token");
                vi.clearAllMocks();

                // Set localStorage before mounting
                localStorage.setItem("vc_theme", localTheme);

                // Mock API to fail
                mockedApi.get.mockRejectedValue(new Error("Network error"));

                const { result } = renderHook(() => useTheme(), { wrapper });

                await waitFor(() => {
                    expect(result.current.isLoading).toBe(false);
                });

                // Verify theme was restored from localStorage (fallback)
                expect(result.current.theme).toBe(localTheme);
            }),
            { numRuns: 100 }
        );
    });

    /**
     * **Feature: navbar-navigation, Property 3: Theme Toggle Round-Trip Consistency**
     * **Validates: Requirements 5.2, 5.4**
     */
    it("Property 3: resolvedTheme correctly resolves system theme", async () => {
        localStorage.clear();
        localStorage.setItem("vc_token", "test-token");
        vi.clearAllMocks();

        mockedApi.get.mockResolvedValue({ data: { theme: "system", language: "en" } });

        const { result } = renderHook(() => useTheme(), { wrapper });

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        // When theme is "system", resolvedTheme should be either "light" or "dark"
        expect(result.current.theme).toBe("system");
        expect(["light", "dark"]).toContain(result.current.resolvedTheme);
    });
});
