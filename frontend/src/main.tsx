import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GoogleOAuthProvider } from "@react-oauth/google";
import "./index.css";
import App from "./App";
import { BrowserRouter } from "react-router-dom";

const client = new QueryClient();

// Google OAuth settings from environment variables
const isGoogleOAuthEnabled = import.meta.env.VITE_GOOGLE_OAUTH_ENABLED === 'true';
const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

// Only use a valid client ID, use placeholder if disabled to prevent errors
const effectiveClientId = isGoogleOAuthEnabled && googleClientId && googleClientId !== 'your-google-client-id.apps.googleusercontent.com'
  ? googleClientId
  : 'disabled'; // Use 'disabled' as placeholder - GoogleOAuthProvider requires non-empty string

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <GoogleOAuthProvider clientId={effectiveClientId}>
      <BrowserRouter>
        <QueryClientProvider client={client}>
          <App />
        </QueryClientProvider>
      </BrowserRouter>
    </GoogleOAuthProvider>
  </React.StrictMode>
);
