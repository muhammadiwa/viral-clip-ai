import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useBreadcrumb, BreadcrumbItem } from "../../hooks/useBreadcrumb";

interface BreadcrumbProps {
    items?: BreadcrumbItem[];
    className?: string;
}

/**
 * Breadcrumb navigation component that displays the current navigation path.
 * Shows navigation from Home to the current page with clickable segments.
 *
 * Requirements: 6.1, 6.2, 6.3, 6.4
 * - WHEN a user navigates to a nested page THEN the Navbar SHALL display breadcrumb navigation below the main navbar
 * - WHEN breadcrumbs are displayed THEN the Navbar SHALL show the navigation path from home to the current page
 * - WHEN a user clicks a breadcrumb link THEN the Navbar SHALL navigate to that page
 * - WHEN a user is on the home page THEN the Navbar SHALL hide the breadcrumb navigation
 */
const Breadcrumb: React.FC<BreadcrumbProps> = ({ items, className = "" }) => {
    const location = useLocation();
    const generatedBreadcrumbs = useBreadcrumb();

    // Use provided items or generated breadcrumbs
    const breadcrumbs = items || generatedBreadcrumbs;

    // Hide breadcrumbs on home page (Requirement 6.4)
    if (location.pathname === "/" || breadcrumbs.length === 0) {
        return null;
    }

    return (
        <nav
            aria-label="Breadcrumb"
            className={`bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700 transition-colors duration-250 ${className}`}
        >
            <div className="px-4 md:px-6 py-2">
                <ol className="flex items-center gap-1 text-sm">
                    {breadcrumbs.map((item, index) => {
                        const isLast = index === breadcrumbs.length - 1;

                        return (
                            <li key={item.path} className="flex items-center">
                                {index > 0 && (
                                    <svg
                                        className="w-4 h-4 text-slate-400 dark:text-slate-500 mx-1"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M9 5l7 7-7 7"
                                        />
                                    </svg>
                                )}
                                {isLast ? (
                                    <span className="text-slate-600 dark:text-slate-300 font-medium">
                                        {item.label}
                                    </span>
                                ) : (
                                    <Link
                                        to={item.path}
                                        className="text-slate-500 dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors"
                                    >
                                        {item.label}
                                    </Link>
                                )}
                            </li>
                        );
                    })}
                </ol>
            </div>
        </nav>
    );
};

export default Breadcrumb;
