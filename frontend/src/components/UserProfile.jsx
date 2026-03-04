/**
 * UserProfile — Accessible by ALL roles (nurse, charge_nurse, supervisor, admin).
 * Provides:
 *  - View own profile info (username, role, display name)
 *  - Change own password
 *
 * This is a USER feature — NOT an admin feature.
 */
import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";

const API = `http://${window.location.hostname}:8000`;

const ROLE_COLORS = {
  admin:       "text-red-300 border-red-500/40 bg-red-500/10",
  supervisor:  "text-amber-300 border-amber-500/40 bg-amber-500/10",
  charge_nurse:"text-purple-300 border-purple-500/40 bg-purple-500/10",
  nurse:       "text-cyan-300 border-cyan-500/40 bg-cyan-500/10",
};

export default function UserProfile() {
  const { user, roleDisplay, authFetch, logout } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: "", text: "" });

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setMessage({ type: "", text: "" });

    if (newPassword.length < 6) {
      setMessage({ type: "error", text: "New password must be at least 6 characters." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setMessage({ type: "error", text: "New passwords do not match." });
      return;
    }

    setSaving(true);
    try {
      const res = await authFetch(`${API}/auth/change-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to change password");
      }
      setMessage({ type: "success", text: "Password changed successfully. You will be logged out." });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      // Auto-logout after 2 seconds since all tokens are revoked
      setTimeout(() => logout(), 2000);
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoutAll = async () => {
    if (!confirm("Sign out from all devices? You will need to log in again.")) return;
    try {
      await authFetch(`${API}/auth/logout-all`, { method: "POST" });
      logout();
    } catch {
      // Force local logout even if API fails
      logout();
    }
  };

  return (
    <div className="max-w-3xl mx-auto mt-8 px-4 pb-12 animate-fadeIn">
      <h1 className="text-3xl font-semibold mb-1">My Profile</h1>
      <p className="text-sm text-slate-400 mb-6">Manage your account settings</p>

      {/* ── Profile Info Card ── */}
      <div className="glass rounded-2xl p-6 border border-indigo-500/20 mb-6">
        <h2 className="text-lg font-semibold text-slate-200 mb-4">Account Information</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-500 uppercase tracking-wide mb-1">Username</label>
            <p className="text-slate-200 font-medium">@{user?.username}</p>
          </div>
          <div>
            <label className="block text-xs text-slate-500 uppercase tracking-wide mb-1">Display Name</label>
            <p className="text-slate-200 font-medium">{user?.display_name || user?.username}</p>
          </div>
          <div>
            <label className="block text-xs text-slate-500 uppercase tracking-wide mb-1">Role</label>
            <span className={`inline-flex text-xs px-2.5 py-1 rounded-full border font-medium ${ROLE_COLORS[user?.role] || ROLE_COLORS.nurse}`}>
              {roleDisplay}
            </span>
          </div>
          <div>
            <label className="block text-xs text-slate-500 uppercase tracking-wide mb-1">User ID</label>
            <p className="text-slate-400 text-xs font-mono">{user?.user_id}</p>
          </div>
        </div>
      </div>

      {/* ── Change Password Card ── */}
      <div className="glass rounded-2xl p-6 border border-indigo-500/20 mb-6">
        <h2 className="text-lg font-semibold text-slate-200 mb-4">Change Password</h2>
        <form onSubmit={handleChangePassword} className="space-y-4 max-w-sm">
          <div>
            <label className="block text-xs text-slate-400 mb-1 uppercase tracking-wide">Current Password</label>
            <input
              type="password"
              className="input-premium w-full"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1 uppercase tracking-wide">New Password</label>
            <input
              type="password"
              className="input-premium w-full"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={6}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1 uppercase tracking-wide">Confirm New Password</label>
            <input
              type="password"
              className="input-premium w-full"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={6}
              autoComplete="new-password"
            />
          </div>

          {message.text && (
            <div className={`rounded-lg px-3 py-2 text-sm ${
              message.type === "error"
                ? "bg-red-900/40 border border-red-500/60 text-red-200"
                : "bg-emerald-900/40 border border-emerald-500/60 text-emerald-200"
            }`}>
              {message.text}
            </div>
          )}

          <button
            type="submit"
            disabled={saving}
            className="w-full py-2.5 rounded-lg btn-primary text-sm font-semibold disabled:opacity-60"
          >
            {saving ? "Changing…" : "Update Password"}
          </button>
        </form>
      </div>

      {/* ── Security Actions Card ── */}
      <div className="glass rounded-2xl p-6 border border-indigo-500/20">
        <h2 className="text-lg font-semibold text-slate-200 mb-4">Security</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleLogoutAll}
            className="px-4 py-2.5 rounded-lg text-sm font-semibold border border-red-500/40 text-red-300 hover:bg-red-500/10 transition-colors"
          >
            Sign Out All Devices
          </button>
          <button
            onClick={logout}
            className="px-4 py-2.5 rounded-lg text-sm font-semibold btn-ghost"
          >
            Sign Out
          </button>
        </div>
        <p className="text-xs text-slate-500 mt-3">
          "Sign Out All Devices" revokes all active sessions across every browser and device.
        </p>
      </div>
    </div>
  );
}
