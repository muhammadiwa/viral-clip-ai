import React, { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../../contexts/AuthContext";
import { useNotifications } from "../../contexts/NotificationContext";
import { useClickOutside } from "../../hooks/useClickOutside";

interface MobileMenuProps {
    isOpen: boolean;
    onToggle: () => void;
    onClose: () => void;
}

/**
 * Mobile navigation menu with hamburger button and slide-in drawer.
 *
 * Requirements: 4.1, 4.2, 4.3, 4.4
 * - WHEN the viewport width is less than 768px THEN the Navbar SHALL display a hamburger menu icon instead of full navigation links
 * - WHEN a user clicks the hamburger menu THEN the Navbar SHALL display a mobile navigation drawer
 * - WHEN the mobile drawer is open THEN the Navbar SHALL display all navigation links in a vertical list
 * - WHEN a user clicks outside the mobile drawer or clicks a navigation link THEN the Navbar SHALL close the mobile drawer
 */
const MobileMenu: React.FC<MobileMenuProps> = ({ isOpen, onToggle, onClose }) => {
    const drawerRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();
    const { user, logout } = useAuth();
    const { unreadCount } = useNotifications();

    useClickOutside(drawerRef, () => {
        if (isOpen) onClose();
    });

    // Body scroll lock when drawer is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [isOpen]);

    const handleNavigation = (path: string) => {
        navigate(path);
        onClose();
    };

    const handleLogout = () => {
        logout();
        onClose();
        navigate("/login");
    };

    const navLinks = [
        { label: "Home", path: "/" },
        { label: "AI Script", path: "/ai-script" },
        { label: "AI Viral Clip", path: "/" },
        { label: "Caption Generator", path: "/caption-generator" },
        { label: "My Projects", path: "/projects" },
        { label: "Pricing", path: "/pricing" },
    ];

    const displayName = user?.name || user?.email?.split("@")[0] || "User";

    return (
        <>
            {/* Hamburger Button */}
            <button
                onClick={onToggle}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors md:hidden"
                aria-label={isOpen ? "Close menu" : "Open menu"}
                aria-expanded={isOpen}
            >
                <div className="w-5 h-5 relative flex flex-col justify-center items-center">
                    <motion.span
                        className="absolute w-5 h-0.5 bg-slate-600 dark:bg-slate-300 rounded-full"
                        animate={{
                            rotate: isOpen ? 45 : 0,
                            y: isOpen ? 0 : -4,
                        }}
                        transition={{ duration: 0.2 }}
                    />
                    <motion.span
                        className="absolute w-5 h-0.5 bg-slate-600 dark:bg-slate-300 rounded-full"
                        animate={{
                            opacity: isOpen ? 0 : 1,
                        }}
                        transition={{ duration: 0.2 }}
                    />
                    <motion.span
                        className="absolute w-5 h-0.5 bg-slate-600 dark:bg-slate-300 rounded-full"
                        animate={{
                            rotate: isOpen ? -45 : 0,
                            y: isOpen ? 0 : 4,
                        }}
                        transition={{ duration: 0.2 }}
                    />
                </div>
            </button>

            {/* Overlay */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.25, ease: "easeOut" }}
                        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden"
                        onClick={onClose}
                    />
                )}
            </AnimatePresence>

            {/* Drawer */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        ref={drawerRef}
                        initial={{ x: "100%", opacity: 0.8 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: "100%", opacity: 0.8 }}
                        transition={{
                            type: "spring",
                            damping: 28,
                            stiffness: 350,
                            opacity: { duration: 0.2 }
                        }}
                        className="fixed top-0 right-0 h-full w-72 bg-white dark:bg-slate-900 shadow-xl z-50 md:hidden transition-colors duration-250"
                    >
                        {/* Drawer Header */}
                        <div className="px-4 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
                                    {user?.name?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase() || "U"}
                                </div>
                                <div>
                                    <p className="font-medium text-slate-900 dark:text-white text-sm">
                                        {displayName}
                                    </p>
                                    <p className="text-xs text-slate-500 dark:text-slate-400">
                                        {user?.credits ?? 0} credits
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                                aria-label="Close menu"
                            >
                                <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* Notifications Link */}
                        <button
                            onClick={() => handleNavigation("/notifications")}
                            className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                        >
                            <div className="flex items-center gap-3">
                                <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                                </svg>
                                <span className="text-sm text-slate-700 dark:text-slate-200">Notifications</span>
                            </div>
                            {unreadCount > 0 && (
                                <span className="px-2 py-0.5 text-xs font-medium text-white bg-primary rounded-full">
                                    {unreadCount}
                                </span>
                            )}
                        </button>

                        {/* Navigation Links */}
                        <nav className="px-2 py-4 border-t border-slate-200 dark:border-slate-700">
                            <div className="mb-2 px-2 text-xs font-semibold text-slate-400 uppercase">
                                Navigation
                            </div>
                            {navLinks.map((link) => (
                                <button
                                    key={link.path + link.label}
                                    onClick={() => handleNavigation(link.path)}
                                    className="w-full px-3 py-2 text-left text-sm text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                                >
                                    {link.label}
                                </button>
                            ))}
                        </nav>

                        {/* Account Section */}
                        <div className="px-2 py-4 border-t border-slate-200 dark:border-slate-700">
                            <div className="mb-2 px-2 text-xs font-semibold text-slate-400 uppercase">
                                Account
                            </div>
                            <button
                                onClick={() => handleNavigation("/profile")}
                                className="w-full px-3 py-2 text-left text-sm text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            >
                                Profile Settings
                            </button>
                            <button
                                onClick={() => handleNavigation("/channels")}
                                className="w-full px-3 py-2 text-left text-sm text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            >
                                My Channels
                            </button>
                            <button
                                onClick={handleLogout}
                                className="w-full px-3 py-2 text-left text-sm text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                            >
                                Logout
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};

export default MobileMenu;
