import { useMemo } from "react";
import { useLocation, useParams } from "react-router-dom";

/**
 * Represents a single breadcrumb item in the navigation path.
 */
export interface BreadcrumbItem {
    label: string;
    path: string;
}

/**
 * Route configuration for breadcrumb generation.
 * Maps route patterns to their display labels.
 */
export interface RouteConfig {
    pattern: string;
    label: string | ((params: Record<string, string>) => string);
}

/**
 * Default route configuration for the application.
 * Can be extended or overridden by passing custom config to the hook.
 */
export const defaultRouteConfig: RouteConfig[] = [
    { pattern: "/", label: "Home" },
    { pattern: "/video/:videoId", label: (params) => `Video ${params.videoId}` },
    { pattern: "/settings", label: "Settings" },
    { pattern: "/profile", label: "Profile" },
];

/**
 * Matches a pathname against a route pattern and extracts parameters.
 *
 * @param pathname - The current URL pathname
 * @param pattern - The route pattern to match against (e.g., "/video/:videoId")
 * @returns Object with match status and extracted parameters
 */
export function matchRoute(
    pathname: string,
    pattern: string
): { matches: boolean; params: Record<string, string> } {
    const patternParts = pattern.split("/").filter(Boolean);
    const pathParts = pathname.split("/").filter(Boolean);

    // Special case for root path
    if (pattern === "/" && pathname === "/") {
        return { matches: true, params: {} };
    }

    if (pattern === "/" && pathname !== "/") {
        return { matches: false, params: {} };
    }

    if (patternParts.length !== pathParts.length) {
        return { matches: false, params: {} };
    }

    const params: Record<string, string> = {};

    for (let i = 0; i < patternParts.length; i++) {
        const patternPart = patternParts[i];
        const pathPart = pathParts[i];

        if (patternPart.startsWith(":")) {
            // Dynamic segment - extract parameter
            const paramName = patternPart.slice(1);
            params[paramName] = pathPart;
        } else if (patternPart !== pathPart) {
            // Static segment doesn't match
            return { matches: false, params: {} };
        }
    }

    return { matches: true, params };
}

/**
 * Generates breadcrumb items from a pathname and route configuration.
 * This is a pure function that can be tested independently.
 *
 * @param pathname - The current URL pathname
 * @param routeConfig - Array of route configurations
 * @returns Array of breadcrumb items from Home to current page
 *
 * Requirements: 6.1, 6.2, 6.3
 * - WHEN a user navigates to a nested page THEN the Navbar SHALL display breadcrumb navigation
 * - WHEN breadcrumbs are displayed THEN the Navbar SHALL show the navigation path from home to the current page
 * - WHEN a user clicks a breadcrumb link THEN the Navbar SHALL navigate to that page
 */
export function generateBreadcrumbs(
    pathname: string,
    routeConfig: RouteConfig[] = defaultRouteConfig
): BreadcrumbItem[] {
    // Home page returns empty breadcrumbs (Requirement 6.4)
    if (pathname === "/") {
        return [];
    }

    const breadcrumbs: BreadcrumbItem[] = [];

    // Always start with Home
    breadcrumbs.push({ label: "Home", path: "/" });

    // Build up the path segments
    const pathParts = pathname.split("/").filter(Boolean);
    let currentPath = "";

    for (let i = 0; i < pathParts.length; i++) {
        currentPath += "/" + pathParts[i];

        // Find matching route config for this path
        let matchedConfig: RouteConfig | undefined;
        let matchedParams: Record<string, string> = {};

        for (const config of routeConfig) {
            const { matches, params } = matchRoute(currentPath, config.pattern);
            if (matches) {
                matchedConfig = config;
                matchedParams = params;
                break;
            }
        }

        if (matchedConfig) {
            const label =
                typeof matchedConfig.label === "function"
                    ? matchedConfig.label(matchedParams)
                    : matchedConfig.label;

            // Don't add Home again if it's the matched config
            if (matchedConfig.pattern !== "/") {
                breadcrumbs.push({ label, path: currentPath });
            }
        } else {
            // Fallback: use the path segment as label (capitalize first letter)
            const label = pathParts[i].charAt(0).toUpperCase() + pathParts[i].slice(1);
            breadcrumbs.push({ label, path: currentPath });
        }
    }

    return breadcrumbs;
}

/**
 * Custom hook that generates breadcrumb navigation items based on the current route.
 * Handles dynamic route parameters and provides a navigation path from Home to current page.
 *
 * @param customConfig - Optional custom route configuration to override defaults
 * @returns Array of breadcrumb items for the current route
 *
 * Requirements: 6.1, 6.2, 6.3
 */
export function useBreadcrumb(customConfig?: RouteConfig[]): BreadcrumbItem[] {
    const location = useLocation();
    const params = useParams();

    const breadcrumbs = useMemo(() => {
        const config = customConfig || defaultRouteConfig;
        return generateBreadcrumbs(location.pathname, config);
    }, [location.pathname, customConfig]);

    return breadcrumbs;
}

export default useBreadcrumb;
