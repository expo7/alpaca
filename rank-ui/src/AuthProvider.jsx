/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from "react";

const AuthCtx = createContext(null);
const BASE = "http://127.0.0.1:8000";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("access") || "");
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("auth_user");
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch {
        // fall through to legacy username storage
      }
    }
    const username = localStorage.getItem("username");
    return username ? { username, is_staff: false, is_superuser: false } : null;
  });

  useEffect(() => {
    if (!token) return;

    let alive = true;

    async function hydrateCurrentUser() {
      try {
        const res = await fetch(`${BASE}/api/auth/me/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok || !alive) return;
        const nextUser = {
          username: json?.username || user?.username || "",
          email: json?.email || "",
          is_staff: Boolean(json?.is_staff),
          is_superuser: Boolean(json?.is_superuser),
        };
        setUser(nextUser);
        localStorage.setItem("auth_user", JSON.stringify(nextUser));
        if (nextUser.username) localStorage.setItem("username", nextUser.username);
      } catch {
        // Keep local user fallback when auth/me is unavailable.
      }
    }

    hydrateCurrentUser();
    return () => {
      alive = false;
    };
  }, [token]);

  function login({ access, username }) {
    localStorage.setItem("access", access);
    localStorage.setItem("username", username);
    localStorage.removeItem("auth_user");
    setToken(access);
    setUser({ username, is_staff: false, is_superuser: false });
  }

  function logout() {
    localStorage.removeItem("access");
    localStorage.removeItem("username");
    localStorage.removeItem("auth_user");
    setToken("");
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) {
    // Helpful error so the screen isn't just blank if provider is missing
    throw new Error("AuthProvider missing: wrap your app in <AuthProvider> in main.jsx");
  }
  return ctx;
}
