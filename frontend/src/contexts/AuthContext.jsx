/**
 * AuthContext — Centralised authentication state for MedRelay.
 *
 * Features:
 *  - JWT access + refresh token management (localStorage)
 *  - Auto-refresh before expiry
 *  - `authFetch()` wrapper that injects Authorization header & retries on 401
 *  - Login / logout helpers
 *  - User object available via context
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";

const API = `http://${window.location.hostname}:8000`;

// ── Local permission map (mirrors backend constants.py) ──────────────────────
const ROLE_PERMISSIONS = {
  admin: [
    "assign_roles", "bulk_delete", "change_any_password", "create_handoff",
    "export_data", "import_excel", "manage_sessions", "manage_settings",
    "manage_users", "purge_demos", "sign_off", "view_all_patients",
    "view_analytics", "view_audit", "view_sessions",
  ],
  supervisor: [
    "create_handoff", "export_data", "import_excel", "manage_sessions",
    "sign_off", "view_all_patients", "view_analytics", "view_audit",
    "view_sessions",
  ],
  charge_nurse: [
    "create_handoff", "export_data", "import_excel", "sign_off",
    "view_all_patients", "view_analytics", "view_sessions",
  ],
  nurse: ["create_handoff", "sign_off", "view_sessions"],
};

const ROLE_DISPLAY = {
  admin: "Administrator",
  supervisor: "Supervisor",
  charge_nurse: "Charge Nurse",
  nurse: "Nurse",
};

function getPermissions(role) {
  return ROLE_PERMISSIONS[role] || ROLE_PERMISSIONS.nurse;
}

function getRoleDisplay(role) {
  return ROLE_DISPLAY[role] || role;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseJwt(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

function tokenExpiresIn(token) {
  const payload = parseJwt(token);
  if (!payload?.exp) return 0;
  return payload.exp * 1000 - Date.now();
}

// ── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);               // { user_id, username, display_name, role }
  const [accessToken, setAccessToken] = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [loading, setLoading] = useState(true);          // true while rehydrating from localStorage
  const refreshTimerRef = useRef(null);

  // ── Persistence helpers ──────────────────────────────────────────────────

  const persist = useCallback((access, refresh, userData) => {
    localStorage.setItem("medrelay_access", access);
    localStorage.setItem("medrelay_refresh", refresh);
    localStorage.setItem("medrelay_user", JSON.stringify(userData));
    setAccessToken(access);
    setRefreshToken(refresh);
    setUser(userData);
  }, []);

  const clear = useCallback(() => {
    localStorage.removeItem("medrelay_access");
    localStorage.removeItem("medrelay_refresh");
    localStorage.removeItem("medrelay_user");
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
  }, []);

  // ── Token refresh ────────────────────────────────────────────────────────

  const refreshAccessToken = useCallback(async (rt) => {
    try {
      const res = await fetch(`${API}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) throw new Error("refresh failed");
      const data = await res.json();
      persist(data.access_token, data.refresh_token, data.user);
      scheduleRefresh(data.access_token, data.refresh_token);
      return data.access_token;
    } catch {
      clear();
      return null;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persist, clear]);

  const scheduleRefresh = useCallback((access, refresh) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const ms = tokenExpiresIn(access) - 60_000; // refresh 1 min before expiry
    if (ms > 0) {
      refreshTimerRef.current = setTimeout(() => refreshAccessToken(refresh), ms);
    }
  }, [refreshAccessToken]);

  // ── Rehydrate on mount ───────────────────────────────────────────────────

  useEffect(() => {
    const access = localStorage.getItem("medrelay_access");
    const refresh = localStorage.getItem("medrelay_refresh");
    const stored = localStorage.getItem("medrelay_user");

    if (access && refresh && stored) {
      const remaining = tokenExpiresIn(access);
      if (remaining > 10_000) {
        // Access token still valid
        setAccessToken(access);
        setRefreshToken(refresh);
        setUser(JSON.parse(stored));
        scheduleRefresh(access, refresh);
        setLoading(false);
      } else {
        // Access expired — try refresh
        refreshAccessToken(refresh).then(() => setLoading(false));
      }
    } else {
      setLoading(false);
    }

    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Login ────────────────────────────────────────────────────────────────

  const login = useCallback(async (username, password) => {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Login failed");
    }
    const data = await res.json();
    persist(data.access_token, data.refresh_token, data.user);
    scheduleRefresh(data.access_token, data.refresh_token);
    return data.user;
  }, [persist, scheduleRefresh]);

  // ── Logout ───────────────────────────────────────────────────────────────

  const logout = useCallback(async () => {
    try {
      if (accessToken && refreshToken) {
        await fetch(`${API}/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } catch { /* best effort */ }
    clear();
  }, [accessToken, refreshToken, clear]);

  // ── Authenticated fetch wrapper ──────────────────────────────────────────

  const authFetch = useCallback(async (url, options = {}) => {
    const headers = { ...options.headers };
    let token = accessToken;

    // If token expired, try a refresh first
    if (token && tokenExpiresIn(token) < 5_000 && refreshToken) {
      token = await refreshAccessToken(refreshToken);
    }

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let res = await fetch(url, { ...options, headers });

    // On 401 try one refresh cycle
    if (res.status === 401 && refreshToken) {
      const newToken = await refreshAccessToken(refreshToken);
      if (newToken) {
        headers["Authorization"] = `Bearer ${newToken}`;
        res = await fetch(url, { ...options, headers });
      }
    }

    return res;
  }, [accessToken, refreshToken, refreshAccessToken]);

  // ── Context value ────────────────────────────────────────────────────────

  // Always derive permissions locally from role — never rely on server array alone
  const userRole = user?.role || "nurse";
  const userPermissions = getPermissions(userRole);

  const value = {
    user,
    accessToken,
    loading,
    isAuthenticated: !!user,
    // Role checks
    isAdmin: userRole === "admin",
    isSupervisor: userRole === "supervisor",
    isChargeNurse: userRole === "charge_nurse",
    isNurse: userRole === "nurse",
    // Permission check — always works because derived from local map
    hasPermission: (perm) => userPermissions.includes(perm),
    // Convenience
    role: userRole,
    roleDisplay: getRoleDisplay(userRole),
    permissions: userPermissions,
    // Actions
    login,
    logout,
    authFetch,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Hook to consume auth context */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
