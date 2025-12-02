import React from "react";
import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import AiViralClipPage from "./app/routes/AiViralClipPage";
import VideoDetailPage from "./app/routes/VideoDetailPage";
import AuthGate from "./components/auth/AuthGate";

const App: React.FC = () => {
  return (
    <Routes>
      <Route
        path="/login"
        element={<AuthGate onAuthenticated={() => window.location.replace("/")} />}
      />
      <Route
        path="/"
        element={
          <AppShell>
            <AiViralClipPage />
          </AppShell>
        }
      />
      <Route
        path="/video/:videoId"
        element={
          <AppShell>
            <VideoDetailPage />
          </AppShell>
        }
      />
    </Routes>
  );
};

export default App;
