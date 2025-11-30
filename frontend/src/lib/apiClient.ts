import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: false
});

export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    localStorage.setItem("vc_token", token);
  } else {
    delete api.defaults.headers.common["Authorization"];
    localStorage.removeItem("vc_token");
  }
};

const savedToken = localStorage.getItem("vc_token");
if (savedToken) {
  setAuthToken(savedToken);
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setAuthToken(null);
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
