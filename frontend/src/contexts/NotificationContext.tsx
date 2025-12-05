import React, {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    useMemo,
    useRef,
} from "react";
import { api } from "../lib/apiClient";

export type NotificationType = "success" | "info" | "warning" | "error";

export interface NotificationDTO {
    id: number;
    title: string;
    message: string;
    type: NotificationType;
    read: boolean;
    created_at: string;
    link?: string;
    job_id?: number;
}

export interface NotificationContextValue {
    notifications: NotificationDTO[];
    unreadCount: number;
    isLoading: boolean;
    error: string | null;
    markAsRead: (id: number) => Promise<void>;
    markAllAsRead: () => Promise<void>;
    deleteNotification: (id: number) => Promise<void>;
    refetch: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextValue | undefined>(
    undefined
);

const POLLING_INTERVAL = 30000; // 30 seconds

// Helper to check if user is authenticated
function isAuthenticated(): boolean {
    return !!localStorage.getItem("vc_token");
}

interface NotificationProviderProps {
    children: React.ReactNode;
    pollingInterval?: number;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({
    children,
    pollingInterval = POLLING_INTERVAL,
}) => {
    const [notifications, setNotifications] = useState<NotificationDTO[]>([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchNotifications = useCallback(async () => {
        // Only fetch if user is authenticated
        if (!isAuthenticated()) {
            setNotifications([]);
            setUnreadCount(0);
            setIsLoading(false);
            return;
        }

        try {
            setIsLoading(true);
            const response = await api.get("/notifications", {
                params: { limit: 20 },
            });
            setNotifications(response.data.notifications);
            setUnreadCount(response.data.unread_count);
            setError(null);
        } catch (err) {
            console.warn("Failed to fetch notifications:", err);
            setError("Unable to load notifications");
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Initial fetch and polling setup
    useEffect(() => {
        // Only start fetching/polling if authenticated
        if (!isAuthenticated()) {
            setIsLoading(false);
            return;
        }

        fetchNotifications();

        // Set up polling only if authenticated
        pollingRef.current = setInterval(() => {
            if (isAuthenticated()) {
                fetchNotifications();
            } else {
                // Stop polling if user logged out
                if (pollingRef.current) {
                    clearInterval(pollingRef.current);
                    pollingRef.current = null;
                }
            }
        }, pollingInterval);

        return () => {
            if (pollingRef.current) {
                clearInterval(pollingRef.current);
            }
        };
    }, [fetchNotifications, pollingInterval]);

    const markAsRead = useCallback(async (id: number) => {
        if (!isAuthenticated()) return;

        try {
            await api.put(`/notifications/${id}/read`);
            setNotifications((prev) =>
                prev.map((n) => (n.id === id ? { ...n, read: true } : n))
            );
            setUnreadCount((prev) => Math.max(0, prev - 1));
        } catch (err) {
            console.warn("Failed to mark notification as read:", err);
            throw err;
        }
    }, []);

    const markAllAsRead = useCallback(async () => {
        if (!isAuthenticated()) return;

        try {
            await api.put("/notifications/read-all");
            setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
            setUnreadCount(0);
        } catch (err) {
            console.warn("Failed to mark all notifications as read:", err);
            throw err;
        }
    }, []);

    const deleteNotification = useCallback(async (id: number) => {
        if (!isAuthenticated()) return;

        try {
            const notification = notifications.find((n) => n.id === id);
            await api.delete(`/notifications/${id}`);
            setNotifications((prev) => prev.filter((n) => n.id !== id));
            if (notification && !notification.read) {
                setUnreadCount((prev) => Math.max(0, prev - 1));
            }
        } catch (err) {
            console.warn("Failed to delete notification:", err);
            throw err;
        }
    }, [notifications]);

    const refetch = useCallback(async () => {
        setIsLoading(true);
        await fetchNotifications();
    }, [fetchNotifications]);

    const value = useMemo<NotificationContextValue>(
        () => ({
            notifications,
            unreadCount,
            isLoading,
            error,
            markAsRead,
            markAllAsRead,
            deleteNotification,
            refetch,
        }),
        [
            notifications,
            unreadCount,
            isLoading,
            error,
            markAsRead,
            markAllAsRead,
            deleteNotification,
            refetch,
        ]
    );

    return (
        <NotificationContext.Provider value={value}>
            {children}
        </NotificationContext.Provider>
    );
};

export function useNotifications(): NotificationContextValue {
    const context = useContext(NotificationContext);
    if (context === undefined) {
        throw new Error(
            "useNotifications must be used within a NotificationProvider"
        );
    }
    return context;
}

export default NotificationContext;
