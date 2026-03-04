import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";

const API = `http://${window.location.hostname}:8000`;

const SEVERITY_COLORS = {
  HIGH:   "bg-red-900/70 text-red-200 border-red-500",
  MEDIUM: "bg-yellow-900/70 text-yellow-200 border-yellow-500",
  LOW:    "bg-blue-900/70 text-blue-200 border-blue-500",
};

function Badge({ count, level }) {
  if (!count) return null;
  const cls = SEVERITY_COLORS[level] ?? "bg-slate-700 text-slate-200 border-slate-500";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-semibold ${cls}`}>
      {level[0]} {count}
    </span>
  );
}

function SignoffDots({ outgoing, incoming }) {
  const dot = (signed) => (
    <span className={`inline-block w-2.5 h-2.5 rounded-full ${signed ? "bg-green-400" : "bg-slate-600"}`} />
  );
  return (
    <span className="flex items-center gap-1" title={`Out: ${outgoing ? "signed" : "pending"} | In: ${incoming ? "signed" : "pending"}`}>
      {dot(outgoing)}{dot(incoming)}
    </span>
  );
}

export default function SessionHistory({ onViewSession }) {
  const { authFetch, isAdmin } = useAuth();
  const canDelete = isAdmin;  // Only admins can delete sessions
  const [sessions, setSessions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessRes, statsRes] = await Promise.all([
        authFetch(`${API}/sessions?limit=100`),
        authFetch(`${API}/stats`),
      ]);
      if (!sessRes.ok) throw new Error(`Sessions fetch failed: ${sessRes.status}`);
      const sessData = await sessRes.json();
      const statsData = statsRes.ok ? await statsRes.json() : {};
      setSessions(sessData.sessions ?? []);
      setStats(statsData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDelete = async (sessionId, e) => {
    e.stopPropagation();
    if (!confirm("Delete this session record? This cannot be undone.")) return;
    setDeleting(sessionId);
    try {
      await authFetch(`${API}/sessions/${sessionId}`, { method: "DELETE" });
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
    } catch {
      alert("Delete failed.");
    } finally {
      setDeleting(null);
    }
  };

  const handleView = async (sessionId) => {
    try {
      const res = await authFetch(`${API}/sessions/${sessionId}`);
      if (!res.ok) throw new Error("Failed to load session");
      const data = await res.json();
      onViewSession(data);
    } catch (e) {
      alert(e.message);
    }
  };

  const fmt = (ts) => {
    if (!ts) return "—";
    try {
      return new Date(ts).toLocaleString("en-US", {
        month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
      });
    } catch { return ts; }
  };

  return (
    <div className="min-h-screen text-slate-100 p-4 sm:p-6 animate-fadeIn">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Handoff History</h1>
            <p className="text-slate-400 text-sm mt-1">Persisted clinical handoff sessions</p>
          </div>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-4 py-2 btn-ghost rounded-lg text-sm"
          >
            ↻ Refresh
          </button>
        </div>

        {/* Stats bar */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
            {[
              { label: "Total Sessions", value: stats.total_sessions ?? 0, color: "text-cyan-400" },
              { label: "High Alerts",    value: stats.total_high_alerts ?? 0, color: "text-red-400" },
              { label: "Fully Signed",   value: stats.fully_signed ?? 0, color: "text-green-400" },
              { label: "Demo Runs",      value: stats.demo_sessions ?? 0, color: "text-purple-400" },
            ].map((s) => (
              <div key={s.label} className="glass rounded-xl px-4 py-3">
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-slate-400 mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="max-w-7xl mx-auto">
        {loading && (
          <div className="flex justify-center items-center py-20">
            <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="bg-red-900/40 border border-red-500 rounded-xl px-5 py-4 text-red-300 text-sm">
            Failed to load sessions: {error}
          </div>
        )}

        {!loading && !error && sessions.length === 0 && (
          <div className="text-center py-20 text-slate-500">
            <p className="text-5xl mb-4">📋</p>
            <p className="text-lg">No sessions yet.</p>
            <p className="text-sm mt-1">Run a handoff or demo to see records here.</p>
          </div>
        )}

        {!loading && sessions.length > 0 && (
          <div className="overflow-x-auto rounded-xl glass">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/70 text-slate-400 text-xs uppercase tracking-wider">
                <tr>
                  {["Patient", "Room / MRN", "Diagnosis", "Nurses", "Alerts", "Signed", "Time", ...(canDelete ? [""] : [])].map((h) => (
                    <th key={h} className="px-4 py-3 text-left whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {sessions.map((s) => (
                  <tr
                    key={s.session_id}
                    onClick={() => handleView(s.session_id)}
                    className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-slate-100 whitespace-nowrap">
                      {s.patient_name || "—"}
                      {s.is_demo && (
                        <span className="ml-2 text-xs bg-purple-900/60 text-purple-300 border border-purple-600 px-1.5 py-0.5 rounded">
                          demo
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-300 whitespace-nowrap">
                      <span>{s.patient_room || "—"}</span>
                      {s.patient_mrn && <span className="ml-2 text-slate-500 text-xs">{s.patient_mrn}</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-300 max-w-[200px]">
                      <span className="truncate block">{s.diagnosis || "—"}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                      <div>{s.outgoing_nurse || "—"}</div>
                      <div className="text-slate-500">→ {s.incoming_nurse || "—"}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex gap-1 flex-wrap">
                        <Badge count={s.high_alert_count}   level="HIGH" />
                        <Badge count={s.medium_alert_count} level="MEDIUM" />
                        <Badge count={s.low_alert_count}    level="LOW" />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <SignoffDots
                        outgoing={s.signed_by_outgoing}
                        incoming={s.signed_by_incoming}
                      />
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap text-xs">
                      {fmt(s.timestamp)}
                    </td>
                    <td className="px-4 py-3">
                      {canDelete && (
                        <button
                          onClick={(e) => handleDelete(s.session_id, e)}
                          disabled={deleting === s.session_id}
                          className="text-slate-600 hover:text-red-400 transition-colors px-2 py-1 rounded disabled:opacity-40"
                          title="Delete session"
                        >
                          {deleting === s.session_id ? "…" : "🗑"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
