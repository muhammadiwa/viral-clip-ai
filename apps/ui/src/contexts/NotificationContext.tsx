import { createContext, useCallback, useContext, useMemo, useState } from 'react'

type NotificationTone = 'info' | 'success' | 'error' | 'warning'

export interface NotificationInput {
  title: string
  message?: string
  tone?: NotificationTone
  durationMs?: number
}

interface Notification extends NotificationInput {
  id: string
  createdAt: number
  tone: NotificationTone
}

interface NotificationContextValue {
  addNotification: (input: NotificationInput) => string
  removeNotification: (id: string) => void
}

const NotificationContext = createContext<NotificationContextValue | undefined>(undefined)

function generateId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return Math.random().toString(36).slice(2)
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([])

  const removeNotification = useCallback((id: string) => {
    setNotifications((current) => current.filter((notification) => notification.id !== id))
  }, [])

  const addNotification = useCallback(
    ({ title, message, tone = 'info', durationMs = 6000 }: NotificationInput) => {
      const id = generateId()
      const createdAt = Date.now()
      const entry: Notification = { id, createdAt, title, message, tone }
      setNotifications((current) => [...current, entry])
      if (durationMs > 0) {
        window.setTimeout(() => removeNotification(id), durationMs)
      }
      return id
    },
    [removeNotification],
  )

  const contextValue = useMemo<NotificationContextValue>(
    () => ({ addNotification, removeNotification }),
    [addNotification, removeNotification],
  )

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-80 max-w-full flex-col gap-3">
        {notifications.map((notification) => (
          <div
            key={notification.id}
            className={[
              'pointer-events-auto rounded-xl border px-4 py-3 shadow-lg backdrop-blur',
              notification.tone === 'success'
                ? 'border-emerald-400/40 bg-emerald-500/20 text-emerald-50'
                : notification.tone === 'error'
                  ? 'border-rose-400/40 bg-rose-500/20 text-rose-50'
                  : notification.tone === 'warning'
                    ? 'border-amber-400/40 bg-amber-500/20 text-amber-50'
                    : 'border-slate-400/30 bg-slate-700/60 text-slate-50',
            ].join(' ')}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-semibold leading-tight">{notification.title}</p>
                {notification.message && (
                  <p className="text-xs leading-snug text-slate-100/80">{notification.message}</p>
                )}
              </div>
              <button
                type="button"
                className="text-xs text-white/70 transition hover:text-white"
                onClick={() => removeNotification(notification.id)}
              >
                Close
              </button>
            </div>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  )
}

export function useNotifications(): NotificationContextValue {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return context
}
