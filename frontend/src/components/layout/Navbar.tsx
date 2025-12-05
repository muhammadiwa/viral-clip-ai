import React from "react";
import ThemeToggle from "./ThemeToggle";
import NotificationBell from "./NotificationBell";
import UserProfileMenu from "./UserProfileMenu";
import MobileMenu from "./MobileMenu";

interface NavbarProps {
    className?: string;
}

/**
 * Main navigation bar component with fixed positioning and backdrop blur.
 * Displays theme toggle, notifications, and user profile menu.
 *
 * Requirements: 1.1, 1.2
 * - WHEN a user loads any page THEN the Navbar SHALL display at the top of the viewport with fixed positioning
 * - WHEN a user scrolls down the page THEN the Navbar SHALL remain visible at the top of the viewport
 */
const Navbar: React.FC<NavbarProps> = ({ className = "" }) => {
    const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

    return (
        <nav
            className={`fixed top-0 left-64 right-0 z-50 h-[72px] bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border-b border-slate-100 dark:border-slate-800 transition-colors duration-300 ${className}`}
        >
            <div className="h-full px-6 flex items-center justify-end">
                {/* Desktop Actions - Right Side */}
                <div className="hidden md:flex items-center gap-2">
                    <ThemeToggle />
                    <NotificationBell />
                    <UserProfileMenu />
                </div>

                {/* Mobile Menu Button */}
                <div className="flex md:hidden items-center gap-2">
                    <ThemeToggle />
                    <MobileMenu
                        isOpen={mobileMenuOpen}
                        onToggle={() => setMobileMenuOpen(!mobileMenuOpen)}
                        onClose={() => setMobileMenuOpen(false)}
                    />
                </div>
            </div>
        </nav>
    );
};

export default Navbar;
