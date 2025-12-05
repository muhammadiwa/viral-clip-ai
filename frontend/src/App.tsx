import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import AiViralClipPage from "./app/routes/AiViralClipPage";
import VideoDetailPage from "./app/routes/VideoDetailPage";
import AuthGate from "./components/auth/AuthGate";
import { ThemeProvider, NotificationProvider, AuthProvider } from "./contexts";

/**
 * Main application component with context providers.
 *
 * Requirements: 5.1, 5.4, 3.1
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
            <Route
              path="/login"
              element={<AuthGate onAuthenticated={() => window.location.replace("/ai-viral-clip")} />}
            />
            {/* Redirect root to AI Viral Clip */}
            <Route path="/" element={<Navigate to="/ai-viral-clip" replace />} />
            {/* AI Viral Clip routes */}
            <Route
              path="/ai-viral-clip"
              element={
                <AppShell>
                  <AiViralClipPage />
                </AppShell>
              }
            />
            <Route
              path="/ai-viral-clip/video/:videoId"
              element={
                <AppShell>
                  <VideoDetailPage />
                </AppShell>
              }
            />
          </Routes>
        </NotificationProvider>
      </ThemeProvider>
    </AuthProvider>
  );
};

export default App;
