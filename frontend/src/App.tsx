import React from "react";
import AppShell from "./components/layout/AppShell";
import AiViralClipPage from "./app/routes/AiViralClipPage";

const App: React.FC = () => {
  return (
    <AppShell>
      <AiViralClipPage />
    </AppShell>
  );
};

export default App;
