/**
 * **Feature: navbar-navigation, Property 4: Breadcrumb Path Generation**
 * **Validates: Requirements 6.1, 6.2**
 *
 * Property: For any nested route path P (where P is not the home route),
 * the breadcrumb component SHALL generate a navigation path starting from "Home"
 * and ending at the current page label, with each intermediate segment being
 * a valid navigable link.
 */

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import {
    generateBreadcrumbs,
    matchRoute,
    defaultRouteConfig,
    type RouteConfig,
    type BreadcrumbItem,
} from "./useBreadcrumb";

// Arbitrary for valid path segments (alphanumeric, no special chars)
const pathSegmentArbitrary = fc.stringMatching(/^[a-z][a-z0-9-]{0,19}$/);

// Arbitrary for numeric IDs (common in dynamic routes)
const numericIdArbitrary = fc.integer({ min: 1, max: 99999 }).map(String);

// Arbitrary for nested paths (1-4 segments deep)
const nestedPathArbitrary = fc
    .array(pathSegmentArbitrary, { minLength: 1, maxLength: 4 })
    .map((segments) => "/" + segments.join("/"));

// Arbitrary for video detail paths
const videoPathArbitrary = numericIdArbitrary.map((id) => `/video/${id}`);

describe("useBreadcrumb Property Tests", () => {
    /**
     * **Feature: navbar-navigation, Property 4: Breadcrumb Path Generation**
     * **Validates: Requirements 6.1, 6.2**
     */
    describe("Property 4: Breadcrumb Path Generation", () => {
        it("home route returns empty breadcrumbs (Requirement 6.4)", () => {
            const breadcrumbs = generateBreadcrumbs("/");
            expect(breadcrumbs).toEqual([]);
        });

        it("for any nested path, breadcrumbs start with Home", () => {
            fc.assert(
                fc.property(nestedPathArbitrary, (pathname) => {
                    const breadcrumbs = generateBreadcrumbs(pathname);

                    // Non-home paths should have breadcrumbs starting with Home
                    expect(breadcrumbs.length).toBeGreaterThan(0);
                    expect(breadcrumbs[0].label).toBe("Home");
                    expect(breadcrumbs[0].path).toBe("/");
                }),
                { numRuns: 100 }
            );
        });

        it("for any nested path, breadcrumbs end with current page", () => {
            fc.assert(
                fc.property(nestedPathArbitrary, (pathname) => {
                    const breadcrumbs = generateBreadcrumbs(pathname);

                    // Last breadcrumb should have the full path
                    const lastBreadcrumb = breadcrumbs[breadcrumbs.length - 1];
                    expect(lastBreadcrumb.path).toBe(pathname);
                }),
                { numRuns: 100 }
            );
        });

        it("for any nested path, all intermediate segments are valid navigable links", () => {
            fc.assert(
                fc.property(nestedPathArbitrary, (pathname) => {
                    const breadcrumbs = generateBreadcrumbs(pathname);

                    // Each breadcrumb path should be a valid prefix of the full path
                    for (let i = 0; i < breadcrumbs.length; i++) {
                        const crumb = breadcrumbs[i];

                        // Path should start with /
                        expect(crumb.path.startsWith("/")).toBe(true);

                        // Path should be a prefix of the full pathname (or be /)
                        if (crumb.path !== "/") {
                            expect(pathname.startsWith(crumb.path)).toBe(true);
                        }

                        // Label should be non-empty
                        expect(crumb.label.length).toBeGreaterThan(0);
                    }
                }),
                { numRuns: 100 }
            );
        });

        it("for any video path, breadcrumbs include video label with ID", () => {
            fc.assert(
                fc.property(videoPathArbitrary, (pathname) => {
                    const breadcrumbs = generateBreadcrumbs(pathname);

                    // Should have Home, Video (intermediate), and Video {id} breadcrumbs
                    // Path /video/1 creates: Home -> Video -> Video 1
                    expect(breadcrumbs.length).toBe(3);
                    expect(breadcrumbs[0].label).toBe("Home");

                    // Last breadcrumb should contain the video ID
                    const videoId = pathname.split("/")[2];
                    const lastBreadcrumb = breadcrumbs[breadcrumbs.length - 1];
                    expect(lastBreadcrumb.label).toContain(videoId);
                    expect(lastBreadcrumb.path).toBe(pathname);
                }),
                { numRuns: 100 }
            );
        });

        it("breadcrumb paths are progressively longer", () => {
            fc.assert(
                fc.property(nestedPathArbitrary, (pathname) => {
                    const breadcrumbs = generateBreadcrumbs(pathname);

                    // Each subsequent breadcrumb path should be longer than the previous
                    for (let i = 1; i < breadcrumbs.length; i++) {
                        expect(breadcrumbs[i].path.length).toBeGreaterThan(
                            breadcrumbs[i - 1].path.length
                        );
                    }
                }),
                { numRuns: 100 }
            );
        });

        it("number of breadcrumbs equals path depth plus one (for Home)", () => {
            fc.assert(
                fc.property(nestedPathArbitrary, (pathname) => {
                    const breadcrumbs = generateBreadcrumbs(pathname);
                    const pathDepth = pathname.split("/").filter(Boolean).length;

                    // Breadcrumbs = Home + each path segment
                    expect(breadcrumbs.length).toBe(pathDepth + 1);
                }),
                { numRuns: 100 }
            );
        });
    });

    describe("matchRoute function", () => {
        it("matches exact static routes", () => {
            fc.assert(
                fc.property(pathSegmentArbitrary, (segment) => {
                    const pattern = `/${segment}`;
                    const pathname = `/${segment}`;

                    const result = matchRoute(pathname, pattern);
                    expect(result.matches).toBe(true);
                    expect(result.params).toEqual({});
                }),
                { numRuns: 100 }
            );
        });

        it("extracts dynamic parameters correctly", () => {
            fc.assert(
                fc.property(numericIdArbitrary, (id) => {
                    const pattern = "/video/:videoId";
                    const pathname = `/video/${id}`;

                    const result = matchRoute(pathname, pattern);
                    expect(result.matches).toBe(true);
                    expect(result.params).toEqual({ videoId: id });
                }),
                { numRuns: 100 }
            );
        });

        it("does not match paths with different segment counts", () => {
            fc.assert(
                fc.property(
                    pathSegmentArbitrary,
                    pathSegmentArbitrary,
                    (seg1, seg2) => {
                        const pattern = `/${seg1}`;
                        const pathname = `/${seg1}/${seg2}`;

                        const result = matchRoute(pathname, pattern);
                        expect(result.matches).toBe(false);
                    }
                ),
                { numRuns: 100 }
            );
        });

        it("root path matches only root pattern", () => {
            const result = matchRoute("/", "/");
            expect(result.matches).toBe(true);

            const result2 = matchRoute("/", "/something");
            expect(result2.matches).toBe(false);

            const result3 = matchRoute("/something", "/");
            expect(result3.matches).toBe(false);
        });
    });
});
