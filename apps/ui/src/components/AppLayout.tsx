import { Outlet, Navigate, Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { OrganizationSwitcher } from './OrganizationSwitcher'

export function AppLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-white/5 bg-slate-900/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/dashboard" className="flex items-center gap-2 text-lg font-semibold">
            <span className="h-8 w-8 rounded-xl bg-indigo-500/30" />
            Viral Clip AI
          </Link>
          <div className="flex items-center gap-4">
            <OrganizationSwitcher />
            <div className="text-right">
              <div className="text-sm font-medium">{user.full_name ?? user.email}</div>
              <button
                className="text-xs text-slate-300 hover:text-white"
                onClick={logout}
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
