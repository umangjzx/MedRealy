import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../contexts/AuthContext";

const API = `http://${window.location.hostname}:8000`;

function HeaderPill({ children }) {
  return <span className="text-xs px-2.5 py-1 rounded-full border border-indigo-400/30 bg-indigo-500/10 text-indigo-200">{children}</span>;
}

function UsersTab() {
  const { authFetch } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ username: "", display_name: "", role: "nurse", password: "changeme" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API}/admin/users`);
      const data = await res.json();
      setUsers(data.users || []);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    let active = true;
    (async () => {
      if (active) await load();
    })();
    return () => { active = false; };
  }, [load]);

  const createUser = async (event) => {
    event.preventDefault();
    await authFetch(`${API}/admin/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    setForm({ username: "", display_name: "", role: "nurse", password: "changeme" });
    load();
  };

  const toggleActive = async (user) => {
    await authFetch(`${API}/admin/users/${user.user_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !user.is_active }),
    });
    load();
  };

  const removeUser = async (userId) => {
    if (!confirm("Delete this user?")) return;
    await authFetch(`${API}/admin/users/${userId}`, { method: "DELETE" });
    load();
  };

  return (
    <div className="grid lg:grid-cols-3 gap-5">
      <div className="glass rounded-xl p-4 lg:col-span-1">
        <h3 className="font-semibold mb-3">Create User</h3>
        <form onSubmit={createUser} className="space-y-3">
          <input className="input-premium w-full" placeholder="Username" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} required />
          <input className="input-premium w-full" placeholder="Display Name" value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} />
          <select className="input-premium w-full" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
            <option value="nurse">Nurse</option>
            <option value="charge_nurse">Charge Nurse</option>
            <option value="supervisor">Supervisor</option>
            <option value="admin">Admin</option>
          </select>
          <input className="input-premium w-full" placeholder="Password" type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} required />
          <button className="w-full py-2.5 rounded-lg btn-primary text-sm font-semibold">Create</button>
        </form>
      </div>

      <div className="glass rounded-xl p-4 lg:col-span-2 overflow-auto">
        <h3 className="font-semibold mb-3">Users</h3>
        {loading ? <p className="text-slate-400 text-sm">Loading users…</p> : (
          <table className="w-full text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="text-left pb-2">Name</th>
                <th className="text-left pb-2">Role</th>
                <th className="text-left pb-2">Status</th>
                <th className="text-right pb-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-t border-slate-800">
                  <td className="py-2">
                    <div>{u.display_name || u.username}</div>
                    <div className="text-xs text-slate-500">@{u.username}</div>
                  </td>
                  <td className="py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full border capitalize ${
                      u.role === "admin" ? "text-red-300 border-red-500/40 bg-red-500/10" :
                      u.role === "supervisor" ? "text-amber-300 border-amber-500/40 bg-amber-500/10" :
                      u.role === "charge_nurse" ? "text-purple-300 border-purple-500/40 bg-purple-500/10" :
                      "text-cyan-300 border-cyan-500/40 bg-cyan-500/10"
                    }`}>
                      {u.role === "charge_nurse" ? "Charge Nurse" : u.role}
                    </span>
                  </td>
                  <td className="py-2">
                    <span className={`text-xs px-2 py-1 rounded-full border ${u.is_active ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10" : "text-red-300 border-red-500/40 bg-red-500/10"}`}>
                      {u.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="py-2 text-right space-x-2">
                    <button onClick={() => toggleActive(u)} className="text-xs btn-ghost px-2 py-1 rounded">
                      {u.is_active ? "Disable" : "Enable"}
                    </button>
                    <button onClick={() => removeUser(u.user_id)} className="text-xs btn-ghost px-2 py-1 rounded text-red-300">Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SettingsTab() {
  const { authFetch } = useAuth();
  const [settings, setSettings] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const res = await authFetch(`${API}/admin/settings`);
    setSettings(await res.json());
  }, [authFetch]);

  useEffect(() => {
    let active = true;
    (async () => {
      if (active) await load();
    })();
    return () => { active = false; };
  }, [load]);

  const fields = useMemo(() => [
    { key: "hospital_name", label: "Hospital Name" },
    { key: "department", label: "Department" },
    { key: "session_retention_days", label: "Session Retention (days)" },
    { key: "auto_demo_enabled", label: "Auto Demo Enabled" },
    { key: "require_dual_signoff", label: "Require Dual Sign-off" },
  ], []);

  const save = async () => {
    setSaving(true);
    await authFetch(`${API}/admin/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    });
    setSaving(false);
  };

  return (
    <div className="glass rounded-xl p-4">
      <h3 className="font-semibold mb-4">System Settings</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        {fields.map((f) => (
          <div key={f.key}>
            <label className="block text-xs text-slate-400 mb-1">{f.label}</label>
            <input
              className="input-premium w-full"
              value={settings[f.key] ?? ""}
              onChange={(e) => setSettings((s) => ({ ...s, [f.key]: e.target.value }))}
            />
          </div>
        ))}
      </div>
      <button onClick={save} disabled={saving} className="mt-4 px-4 py-2 rounded-lg btn-primary text-sm font-semibold disabled:opacity-60">
        {saving ? "Saving…" : "Save Settings"}
      </button>
    </div>
  );
}

function AuditTab() {
  const { authFetch } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await authFetch(`${API}/admin/audit?limit=150`);
    const data = await res.json();
    setLogs(data.logs || []);
    setLoading(false);
  }, [authFetch]);

  useEffect(() => {
    let active = true;
    (async () => {
      if (active) await load();
    })();
    return () => { active = false; };
  }, [load]);

  return (
    <div className="glass rounded-xl p-4 overflow-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Audit Log</h3>
        <button onClick={load} className="text-xs btn-ghost rounded px-2 py-1">Refresh</button>
      </div>
      {loading ? <p className="text-slate-400 text-sm">Loading logs…</p> : (
        <table className="w-full text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="text-left pb-2">Time</th>
              <th className="text-left pb-2">User</th>
              <th className="text-left pb-2">Action</th>
              <th className="text-left pb-2">Target</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.log_id} className="border-t border-slate-800">
                <td className="py-2 text-xs text-slate-400">{new Date(log.timestamp).toLocaleString()}</td>
                <td className="py-2">{log.username}</td>
                <td className="py-2">{log.action}</td>
                <td className="py-2 text-slate-400">{log.target_type || "—"} {log.target_id ? `(${log.target_id.slice(0, 8)}…)` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SessionsTab() {
  const { authFetch } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await authFetch(`${API}/sessions?limit=200`);
    const data = await res.json();
    setSessions(data.sessions || []);
    setLoading(false);
  }, [authFetch]);

  useEffect(() => {
    let active = true;
    (async () => {
      if (active) await load();
    })();
    return () => { active = false; };
  }, [load]);

  const toggle = (id) => setSelected((s) => ({ ...s, [id]: !s[id] }));

  const bulkDelete = async () => {
    const ids = Object.keys(selected).filter((id) => selected[id]);
    if (!ids.length || !confirm(`Delete ${ids.length} session(s)?`)) return;
    await authFetch(`${API}/admin/sessions/bulk-delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_ids: ids }),
    });
    setSelected({});
    load();
  };

  const purgeDemos = async () => {
    if (!confirm("Purge all demo sessions?")) return;
    await authFetch(`${API}/admin/sessions/purge-demos`, { method: "POST" });
    load();
  };

  return (
    <div className="glass rounded-xl p-4 overflow-auto">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 className="font-semibold">Session Maintenance</h3>
        <div className="flex items-center gap-2">
          <button onClick={bulkDelete} className="text-xs px-3 py-1.5 rounded btn-ghost">Delete Selected</button>
          <button onClick={purgeDemos} className="text-xs px-3 py-1.5 rounded btn-danger">Purge Demo Sessions</button>
        </div>
      </div>

      {loading ? <p className="text-slate-400 text-sm">Loading sessions…</p> : (
        <table className="w-full text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="text-left pb-2">Sel</th>
              <th className="text-left pb-2">Patient</th>
              <th className="text-left pb-2">Room</th>
              <th className="text-left pb-2">Time</th>
              <th className="text-left pb-2">Demo</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.session_id} className="border-t border-slate-800">
                <td className="py-2"><input type="checkbox" checked={!!selected[s.session_id]} onChange={() => toggle(s.session_id)} /></td>
                <td className="py-2">{s.patient_name || "—"}</td>
                <td className="py-2 text-slate-400">{s.patient_room || "—"}</td>
                <td className="py-2 text-slate-400 text-xs">{s.timestamp ? new Date(s.timestamp).toLocaleString() : "—"}</td>
                <td className="py-2">{s.is_demo ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ChangePasswordTab() {
  const { authFetch } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: "", text: "" });

  const handleSubmit = async (e) => {
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
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to change password");
      }
      setMessage({ type: "success", text: "Password changed successfully. You may need to re-login." });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="glass rounded-xl p-4 max-w-md">
      <h3 className="font-semibold mb-4">Change Password</h3>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Current Password</label>
          <input type="password" className="input-premium w-full" value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)} required />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">New Password</label>
          <input type="password" className="input-premium w-full" value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)} required minLength={6} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Confirm New Password</label>
          <input type="password" className="input-premium w-full" value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} />
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

        <button type="submit" disabled={saving} className="w-full py-2.5 rounded-lg btn-primary text-sm font-semibold disabled:opacity-60">
          {saving ? "Changing…" : "Change Password"}
        </button>
      </form>
    </div>
  );
}

export default function AdminPanel() {
  const { user, hasPermission } = useAuth();

  // Tabs filtered by the current user's permissions
  const allTabs = [
    { key: "users",    label: "Users",    perm: "manage_users" },
    { key: "settings", label: "Settings", perm: "manage_settings" },
    { key: "audit",    label: "Audit",    perm: "view_audit" },
    { key: "sessions", label: "Sessions", perm: "manage_sessions" },
    { key: "password", label: "Password", perm: null },  // always visible
  ];
  const tabs = allTabs.filter((t) => !t.perm || hasPermission(t.perm));

  const [tab, setTab] = useState(tabs[0]?.key || "password");

  return (
    <div className="max-w-7xl mx-auto mt-8 px-4 pb-12 animate-fadeIn">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-3xl font-semibold">Admin Console</h1>
          <p className="text-sm text-slate-400 mt-1">Operational controls for MedRelay</p>
        </div>
        <div className="flex items-center gap-2">
          <HeaderPill>{user?.display_name || user?.username}</HeaderPill>
          <HeaderPill>{user?.role}</HeaderPill>
        </div>
      </div>

      <div className="glass rounded-xl p-2 mb-4 inline-flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-sm px-3 py-1.5 rounded-lg border transition-colors ${tab === t.key ? "bg-indigo-500/20 border-indigo-400/40 text-indigo-200" : "border-transparent text-slate-300 hover:bg-slate-800"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "users" && <UsersTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "sessions" && <SessionsTab />}
      {tab === "password" && <ChangePasswordTab />}
    </div>
  );
}
