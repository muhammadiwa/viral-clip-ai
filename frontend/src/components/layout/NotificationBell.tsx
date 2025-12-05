import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useNotifications, NotificationDTO } from "../../contexts/NotificationContext";
import { useClickOutside } from "../../hooks/useClickOutside";

interface NotificationBellProps {
    className?: string;
}

/**
 * Notification bell icon with badge count and dropdown list.
 *
 * Requirements: 3.1, 3.2, 3.3, 3.4
 * - WHEN the Navbar renders THEN the Navbar SHALL display a notification bell icon
 * - WHEN there are unread notifications THEN the Navbar SHALL display a badge with the count of unread notifications
 * - WHEN a user clicks the notification bell THEN the Navbar SHALL display a dropdown list of recent notifications
 * - WHEN a user clicks a notification item THEN the Navbar SHALL navigate to the relevant page and mark the notification as read
 */
const NotificationBell: React.FC<NotificationBellProps> = ({ className = "" }) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();
    const { notifications, unreadCount, isLoading, markAsRead, markAllAsRead } = useNotifications();

    useClickOutside(dropdownRef, () => setIsOpen(false));

    const handleNotificationClick = async (notification: NotificationDTO) => {
        if (!notification.read) {
            await markAsRead(notification.id);
        }
        if (notification.link) {
            navigate(notification.link);
        }
        setIsOpen(false);
    };

    const getNotificationIcon = (type: NotificationDTO["type"]) => {
        switch (type) {
            case "success":
                return "✓";
            case "error":
                return "✕";
            case "warning":
                return "⚠";
            default:
                return "ℹ";
        }
    };

    const getNotificationColor = (type: NotificationDTO["type"]) => {
        switch (type) {
            case "success":
                return "text-green-500 bg-green-50 dark:bg-green-900/20";
            case "error":
                return "text-red-500 bg-red-50 dark:bg-red-900/20";
            case "warning":
                return "text-yellow-500 bg-yellow-50 dark:bg-yellow-900/20";
            default:
                return "text-blue-500 bg-blue-50 dark:bg-blue-900/20";
        }
    };

    const formatTime = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return "Just now";
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        return `${days}d ago`;
    };

    return (
        <div ref={dropdownRef} className={`relative ${className}`}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="relative p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                aria-label="Notifications"
            >
                <svg
                    className="w-5 h-5 text-slate-600 dark:text-slate-300"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                    />
                </svg>
                {/* Badge - only show when unreadCount > 0 */}
                {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 h-5 min-w-[20px] px-1 flex items-center justify-center text-xs font-medium text-white bg-primary rounded-full">
                        {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                )}
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
                        className="absolute right-0 mt-2 w-80 bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden transition-colors duration-250"
                    >
                        {/* Header */}
                        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                            <h3 className="font-semibold text-slate-900 dark:text-white">
                                Notifications
                            </h3>
                            {unreadCount > 0 && (
                                <button
                                    onClick={() => markAllAsRead()}
                                    className="text-xs text-primary hover:underline"
                                >
                                    Mark all as read
                                </button>
                            )}
                        </div>

                        {/* Notification List */}
                        <div className="max-h-80 overflow-y-auto">
                            {isLoading ? (
                                <div className="px-4 py-8 text-center text-slate-500 dark:text-slate-400">
                                    Loading...
                                </div>
                            ) : notifications.length === 0 ? (
                                <div className="px-4 py-8 text-center text-slate-500 dark:text-slate-400">
                                    No notifications
                                </div>
                            ) : (
                                notifications.map((notification) => (
                                    <button
                                        key={notification.id}
                                        onClick={() => handleNotificationClick(notification)}
                                        className={`w-full px-4 py-3 flex items-start gap-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors text-left ${!notification.read ? "bg-slate-50/50 dark:bg-slate-700/30" : ""
                                            }`}
                                    >
                                        <span
                                            className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm ${getNotificationColor(
                                                notification.type
                                            )}`}
                                        >
                                            {getNotificationIcon(notification.type)}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <p
                                                className={`text-sm ${!notification.read
                                                    ? "font-medium text-slate-900 dark:text-white"
                                                    : "text-slate-700 dark:text-slate-300"
                                                    }`}
                                            >
                                                {notification.title}
                                            </p>
                                            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                                                {notification.message}
                                            </p>
                                            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                                                {formatTime(notification.created_at)}
                                            </p>
                                        </div>
                                        {!notification.read && (
                                            <span className="flex-shrink-0 w-2 h-2 rounded-full bg-primary mt-2" />
                                        )}
                                    </button>
                                ))
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default NotificationBell;
