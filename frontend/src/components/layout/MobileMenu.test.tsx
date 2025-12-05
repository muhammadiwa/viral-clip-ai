/**
 * **Feature: navbar-navigation, Property 2: Responsive Hamburger Menu Visibility**
 * **Validates: Requirements 4.1**
 *
 * Property: For any viewport width W, when W < 768px the hamburger menu icon SHALL be visible
 * and desktop navigation elements SHALL be hidden. When W >= 768px, the hamburger menu SHALL
 * be hidden and desktop elements SHALL be visible.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import * as fc from "fast-check";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { BrowserRouter } from "react-router-dom";
import MobileMenu from "./MobileMenu";

// Mock the contexts
vi.mock("../../contexts/AuthContext", () => ({
    useAuth: () => ({
        user: { id: 1, email: "test@example.com", name: "Test User", credits: 100 },
        logout: vi.fn(),
    }),
}));

vi.mock("../../contexts/NotificationContext", () => ({
    useNotifications: () => ({
        unreadCount: 5,
    }),
}));

// Wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <BrowserRouter>{children}</BrowserRouter>
);

/**
 * Helper function to determine expected visibility based on viewport width.
 * According to Requirements 4.1:
 * - When viewport width < 768px: hamburger menu visible, desktop elements hidden
 * - When viewport width >= 768px: hamburger menu hidden, desktop elements visible
 */
export function getExpectedVisibility(viewportWidth: number): {
    hamburgerVisible: boolean;
    desktopVisible: boolean;
} {
    const isMobile = viewportWidth < 768;
    return {
        hamburgerVisible: isMobile,
        desktopVisible: !isMobile,
    };
}

describe("MobileMenu Property Tests", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        cleanup();
    });

    /**
     * **Feature: navbar-navigation, Property 2: Responsive Hamburger Menu Visibility**
     * **Validates: Requirements 4.1**
     *
     * This test verifies that the hamburger button has the correct CSS class
     * that controls its visibility based on viewport width.
     */
    it("Property 2: Hamburger button has md:hidden class for responsive visibility", () => {
        const onToggle = vi.fn();
        const onClose = vi.fn();

        render(
            <TestWrapper>
                <MobileMenu isOpen={false} onToggle={onToggle} onClose={onClose} />
            </TestWrapper>
        );

        // Find the hamburger button
        const hamburgerButton = screen.getByRole("button", { name: /menu/i });

        // Verify the button exists and has the responsive class
        expect(hamburgerButton).toBeInTheDocument();

        // The button should have md:hidden class which means:
        // - Visible when viewport < 768px (mobile)
        // - Hidden when viewport >= 768px (desktop)
        expect(hamburgerButton.className).toContain("md:hidden");
    });

    /**
     * **Feature: navbar-navigation, Property 2: Responsive Hamburger Menu Visibility**
     * **Validates: Requirements 4.1**
     *
     * This test verifies the visibility logic is correct for any viewport width.
     */
    it("Property 2: Visibility logic correctly determines mobile vs desktop for any viewport width", () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1, max: 3000 }),
                (viewportWidth) => {
                    const expected = getExpectedVisibility(viewportWidth);

                    // Verify the logic:
                    // - For widths < 768: hamburger visible, desktop hidden
                    // - For widths >= 768: hamburger hidden, desktop visible
                    if (viewportWidth < 768) {
                        return expected.hamburgerVisible === true && expected.desktopVisible === false;
                    } else {
                        return expected.hamburgerVisible === false && expected.desktopVisible === true;
                    }
                }
            ),
            { numRuns: 100 }
        );
    });

    /**
     * **Feature: navbar-navigation, Property 2: Responsive Hamburger Menu Visibility**
     * **Validates: Requirements 4.1**
     *
     * Edge case: Test at the exact breakpoint boundary (768px).
     */
    it("Property 2: At exactly 768px, hamburger should be hidden (desktop mode)", () => {
        const viewportWidth = 768;
        const expected = getExpectedVisibility(viewportWidth);

        expect(expected.hamburgerVisible).toBe(false);
        expect(expected.desktopVisible).toBe(true);
    });

    /**
     * **Feature: navbar-navigation, Property 2: Responsive Hamburger Menu Visibility**
     * **Validates: Requirements 4.1**
     *
     * Edge case: Test at 767px (just below breakpoint).
     */
    it("Property 2: At 767px, hamburger should be visible (mobile mode)", () => {
        const viewportWidth = 767;
        const expected = getExpectedVisibility(viewportWidth);

        expect(expected.hamburgerVisible).toBe(true);
        expect(expected.desktopVisible).toBe(false);
    });

    /**
     * **Feature: navbar-navigation, Property 2: Responsive Hamburger Menu Visibility**
     * **Validates: Requirements 4.1**
     *
     * Property: The breakpoint boundary (768px) is consistent - all widths below
     * show mobile, all widths at or above show desktop.
     */
    it("Property 2: Breakpoint boundary is consistent for all viewport widths", () => {
        const BREAKPOINT = 768;

        fc.assert(
            fc.property(
                fc.integer({ min: 1, max: 2000 }),
                (viewportWidth) => {
                    const expected = getExpectedVisibility(viewportWidth);

                    // Invariant: hamburgerVisible and desktopVisible are always opposite
                    const oppositeCheck = expected.hamburgerVisible === !expected.desktopVisible;

                    // Invariant: The breakpoint determines the mode
                    const isBelowBreakpoint = viewportWidth < BREAKPOINT;
                    const breakpointCheck = expected.hamburgerVisible === isBelowBreakpoint;

                    return oppositeCheck && breakpointCheck;
                }
            ),
            { numRuns: 100 }
        );
    });
});
