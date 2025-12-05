import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../../contexts/AuthContext";
import { useClickOutside } from "../../hooks/useClickOutside";

interface UserProfileMenuProps {
    className?: string;
}

interface MenuItem {
    label: string;
    icon: React.ReactNode;
    onClick: () => void;
    divider?: boolean;
}

/**
 * User profile menu with avatar, name, and dropdown options.
 *
 * Requirements: 2.1, 2.2, 2.3, 2.4
 * - WHEN the Navbar renders THEN the Navbar SHALL display a user avatar and name on the right side
 * - WHEN a user clicks the user profile area THEN the Navbar SHALL display a dropdown menu with account options
 * - WHEN the profile dropdown is open THEN the Navbar SHALL display options for Profile Settings, My Channels, Credits Balance, and Logout
 * - WHEN a user clicks outside the profile dropdown THEN the Navbar SHALL close the dropdown menu
 */
const UserProfileMenu: React.FC<UserProfileMenuProps> = ({ className = "" }) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();
    const { user, logout } = useAuth();

    useClickOutside(dropdownRef, () => setIsOpen(false));

    const handleLogout = () => {
        logout();
        setIsOpen(false);
        navigate("/login");
    };

    const menuItems: MenuItem[] = [
        {
            label: "Profile Settings",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
            ),
            onClick: () => {
                navigate("/profile");
                setIsOpen(false);
            },
        },
        {
            label: "My Channels",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
            ),
            onClick: () => {
                navigate("/channels");
                setIsOpen(false);
            },
        },
        {
            label: `Credits: ${user?.credits ?? 0}`,
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            ),
            onClick: () => {
                navigate("/credits");
                setIsOpen(false);
            },
            divider: true,
        },
        {
            label: "Logout",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
            ),
            onClick: handleLogout,
        },
    ];

    const getInitials = (name: string | null | undefined, email: string) => {
        if (name) {
            return name
                .split(" ")
                .map((n) => n[0])
                .join("")
                .toUpperCase()
                .slice(0, 2);
        }
        return email.charAt(0).toUpperCase();
    };

    const displayName = user?.name || user?.email?.split("@")[0] || "User";

    return (
        <div ref={dropdownRef} className={`relative ${className}`}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                aria-label="User menu"
            >
                {user?.avatar_url ? (
                    <img
                        src={user.avatar_url}
                        alt={displayName}
                        className="w-8 h-8 rounded-full object-cover"
                    />
                ) : (
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium text-sm">
                        {getInitials(user?.name, user?.email || "")}
                    </div>
                )}
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200 hidden lg:block max-w-[120px] truncate">
                    {displayName}
                </span>
                <motion.svg
                    className="w-4 h-4 text-slate-400 dark:text-slate-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    animate={{ rotate: isOpen ? 180 : 0 }}
                    transition={{ duration: 0.2, ease: "easeInOut" }}
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </motion.svg>
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -10, scale: 0.95 }}
                        transition={{
                            type: "spring",
                            stiffness: 300,
                            damping: 25,
                            duration: 0.2
                        }}
                        className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden transition-colors duration-250"
                    >
                        {/* User Info Header */}
                        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                            <p className="font-medium text-slate-900 dark:text-white truncate">
                                {displayName}
                            </p>
                            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                                {user?.email}
                            </p>
                        </div>

                        {/* Menu Items */}
                        <div className="py-1">
                            {menuItems.map((item, index) => (
                                <React.Fragment key={item.label}>
                                    {item.divider && index > 0 && (
                                        <div className="my-1 border-t border-slate-200 dark:border-slate-700" />
                                    )}
                                    <button
                                        onClick={item.onClick}
                                        className="w-full px-4 py-2 flex items-center gap-3 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                                    >
                                        <span className="text-slate-400 dark:text-slate-500">
                                            {item.icon}
                                        </span>
                                        {item.label}
                                    </button>
                                </React.Fragment>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default UserProfileMenu;
