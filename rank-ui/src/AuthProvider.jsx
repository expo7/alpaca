/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from "react";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("access") || "");
  const [user, setUser] = useState(() => {
    const u = localStorage.getItem("username");
    return u ? { username: u } : null;
  });

  function login({ access, username }) {
    localStorage.setItem("access", access);
    localStorage.setItem("username", username);
    setToken(access);
    setUser({ username });
  }

  function logout() {
    localStorage.removeItem("access");
    localStorage.removeItem("username");
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
