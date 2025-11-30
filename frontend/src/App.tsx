import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import AiViralClipPage from "./app/routes/AiViralClipPage";
import AuthGate from "./components/auth/AuthGate";

const App: React.FC = () => {
  return (
    <Routes>
      <Route
        path="/login"
        element={<AuthGate onAuthenticated={() => window.location.replace("/")} />}
      />
      <Route
        path="/*"
        element={
          <AppShell>
            <AiViralClipPage />
          </AppShell>
        }
      />
    </Routes>
  );
};

export default App;
