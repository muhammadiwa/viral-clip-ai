import React, { useState, PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";
import { api, setAuthToken } from "../../lib/apiClient";

type Props = PropsWithChildren<{
  onAuthenticated: () => void;
}>;

const AuthGate: React.FC<Props> = ({ onAuthenticated, children }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = localStorage.getItem("vc_token");

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      if (mode === "register") {
        await api.post("/auth/register", { email, password });
      }
      const params = new URLSearchParams();
      params.append("username", email);
      params.append("password", password);
      const res = await api.post("/auth/login", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });
      setAuthToken(res.data.access_token);
      onAuthenticated();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  if (token) {
    return children ? <>{children}</> : <Navigate to="/" replace />;
  }

  return (
    <div className="h-screen flex items-center justify-center bg-[#fdf7f4]">
      <div className="w-full max-w-md bg-white rounded-3xl shadow p-6 space-y-4 border border-slate-100">
        <div>
          <div className="text-xl font-semibold text-slate-900">Viral Clip AI</div>
          <div className="text-sm text-slate-500">Login atau daftar untuk melanjutkan.</div>
        </div>
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Email</label>
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Password</label>
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
            />
          </div>
          {error && <div className="text-xs text-rose-600">{error}</div>}
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full rounded-lg bg-primary text-white py-2 font-semibold text-sm disabled:opacity-60"
          >
            {loading ? "Processing..." : mode === "login" ? "Login" : "Register & Login"}
          </button>
          <button
            className="w-full text-xs text-primary"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "Need an account? Register" : "Have an account? Login"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AuthGate;
