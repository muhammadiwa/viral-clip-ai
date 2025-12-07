import React from "react";
import { Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import AiViralClipPage from "./app/routes/AiViralClipPage";
import VideoDetailPage from "./app/routes/VideoDetailPage";
import { AuthPage } from "./components/auth/AuthPage";
import { ThemeProvider, NotificationProvider, AuthProvider } from "./contexts";
import { useAuth } from "./contexts/AuthContext";

/**
 * Protected route wrapper that redirects to login if not authenticated.
 */
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#fdf7f4]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

/**
 * Auth route wrapper that redirects to app if already authenticated.
 */
const AuthRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#fdf7f4]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/ai-viral-clip" replace />;
  }

  return <>{children}</>;
};

/**
 * Password reset page component that extracts token from URL.
 */
const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  return <AuthPage defaultMode="reset-password" resetToken={token} />;
};

/**
 * Main application component with context providers.
 *
 * Requirements: 1.1, 5.1, 5.4, 3.1
 * - WHEN a user visits the auth page THEN the Auth_Page SHALL display a split-screen layout
 * - WHEN the Navbar renders THEN the Navbar SHALL display a theme toggle button
 * - WHEN a user returns to the application THEN the Navbar SHALL apply the previously saved theme preference
 * - WHEN the Navbar renders THEN the Navbar SHALL display a notification bell icon
 */
const App: React.FC = () => {
  return (
    <AuthProvider>
      <ThemeProvider>
        <NotificationProvider>
          <Routes>
            {/* Auth routes */}
            <Route
              path="/login"
              element={
                <AuthRoute>
                  <AuthPage defaultMode="login" />
                </AuthRoute>
              }
            />
            <Route
              path="/register"
              element={
                <AuthRoute>
                  <AuthPage defaultMode="register" />
                </AuthRoute>
              }
            />
            <Route
              path="/forgot-password"
              element={
                <AuthRoute>
                  <AuthPage defaultMode="forgot-password" />
                </AuthRoute>
              }
            />
            <Route
              path="/reset-password"
              element={
                <AuthRoute>
                  <ResetPasswordPage />
                </AuthRoute>
              }
            />
            {/* Redirect root to AI Viral Clip */}
            <Route path="/" element={<Navigate to="/ai-viral-clip" replace />} />
            {/* AI Viral Clip routes - Protected */}
            <Route
              path="/ai-viral-clip"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <AiViralClipPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />
            <Route
              path="/ai-viral-clip/video/:slug"
              element={
                <ProtectedRoute>
                  <AppShell>
                    <VideoDetailPage />
                  </AppShell>
                </ProtectedRoute>
              }
            />
          </Routes>
        </NotificationProvider>
      </ThemeProvider>
    </AuthProvider>
  );
};

export default App;
