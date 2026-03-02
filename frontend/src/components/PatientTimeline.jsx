/**
 * PatientTimeline — Vertical timeline showing all handoffs for a specific patient.
 * Each node shows date, nurses, diagnosis, and alert counts.
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";

const API = `http://${window.location.hostname}:8000`;

function TimelineNode({ session, index, total, onView }) {
  const isLast = index === total - 1;
  const alertTotal =
    (session.high_alert_count || 0) +
    (session.medium_alert_count || 0) +
    (session.low_alert_count || 0);
  const hasHighRisk = session.high_alert_count > 0;

  return (
    <div className="flex gap-4">
      {/* Timeline spine + dot */}
      <div className="flex flex-col items-center">
        <div
          className={`w-4 h-4 rounded-full border-2 shrink-0 ${
            hasHighRisk
              ? "bg-red-500 border-red-400"
              : "bg-cyan-500 border-cyan-400"
          }`}
        />
        {!isLast && <div className="w-0.5 flex-1 bg-slate-700 min-h-[3rem]" />}
      </div>

      {/* Content card */}
      <div className="flex-1 pb-6">
        <div
          className="glass rounded-xl p-4 hover:border-indigo-400/30 transition-colors cursor-pointer"
          onClick={() => onView(session.session_id)}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-400">{session.timestamp || "—"}</span>
            <div className="flex items-center gap-1">
              {session.is_demo && (
                <span className="text-[10px] bg-purple-900/60 text-purple-300 border border-purple-600 px-1.5 py-0.5 rounded">
                  demo
                </span>
              )}
              {session.signed_by_outgoing && session.signed_by_incoming && (
                <span className="text-[10px] bg-emerald-900/60 text-emerald-300 border border-emerald-600 px-1.5 py-0.5 rounded">
                  ✓ signed
                </span>
              )}
            </div>
          </div>

          {/* Diagnosis */}
          <p className="text-sm font-medium text-slate-100 mb-2">
            {session.diagnosis || "No diagnosis recorded"}
          </p>

          {/* Nurses */}
          <p className="text-xs text-slate-400 mb-2">
            {session.outgoing_nurse || "—"} → {session.incoming_nurse || "—"}
          </p>

          {/* Alerts summary */}
          {alertTotal > 0 && (
            <div className="flex gap-2 flex-wrap">
              {session.high_alert_count > 0 && (
                <span className="text-xs bg-red-900/50 text-red-300 px-2 py-0.5 rounded">
                  {session.high_alert_count} HIGH
                </span>
              )}
              {session.medium_alert_count > 0 && (
                <span className="text-xs bg-yellow-900/50 text-yellow-300 px-2 py-0.5 rounded">
                  {session.medium_alert_count} MED
                </span>
              )}
              {session.low_alert_count > 0 && (
                <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded">
                  {session.low_alert_count} LOW
                </span>
              )}
            </div>
          )}

          {/* Room */}
          {session.patient_room && (
            <p className="text-xs text-slate-500 mt-2">📍 {session.patient_room}</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PatientTimeline({ patientName, onViewSession, onBack }) {
  const { authFetch } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(
        `${API}/patients/${encodeURIComponent(patientName)}/timeline`
      );
      if (!res.ok) throw new Error(`Failed to load timeline: ${res.status}`);
      const data = await res.json();
      setSessions(data.sessions ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [patientName, authFetch]);

  useEffect(() => { load(); }, [load]);

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

  return (
    <div className="max-w-3xl mx-auto mt-8 px-4 pb-12 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={onBack}
          className="text-sm text-slate-300 hover:text-white transition-colors btn-ghost rounded-lg px-3 py-1.5"
        >
          ← Back
        </button>
        <div>
          <h1 className="text-3xl font-semibold text-white">{patientName}</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {sessions.length} handoff{sessions.length !== 1 ? "s" : ""} recorded
          </p>
        </div>
      </div>

      {loading && (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-500 rounded-xl px-5 py-4 text-red-300 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && sessions.length === 0 && (
        <div className="text-center py-20 text-slate-500">
          <p className="text-5xl mb-4">📋</p>
          <p>No sessions found for this patient.</p>
        </div>
      )}

      {!loading && sessions.length > 0 && (
        <div>
          {sessions.map((s, i) => (
            <TimelineNode
              key={s.session_id}
              session={s}
              index={i}
              total={sessions.length}
              onView={handleView}
            />
          ))}
        </div>
      )}
    </div>
  );
}
