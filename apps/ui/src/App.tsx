import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import LoginPage from './pages/Login'
import DashboardPage from './pages/Dashboard'
import ProjectPage from './pages/Project'
import { AppLayout } from './components/AppLayout'
import { useAuth } from './contexts/AuthContext'
import { NotificationProvider } from './contexts/NotificationContext'

function ProtectedRoute() {
  const { token, loading } = useAuth()
  if (loading) {
    return <div className="p-6 text-sm text-slate-400">Restoring session…</div>
  }
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <NotificationProvider>
      <AppRoutes />
    </NotificationProvider>
  )
}
