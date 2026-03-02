import React, { useState, useCallback } from "react";
import HandoffSession from "./components/HandoffSession";
import LiveTranscript from "./components/LiveTranscript";
import SBARReport from "./components/SBARReport";
import RiskAlerts from "./components/RiskAlerts";
import SignOff from "./components/SignOff";
import SessionHistory from "./components/SessionHistory";
import Dashboard from "./components/Dashboard";
import PatientTimeline from "./components/PatientTimeline";
import AdminPanel from "./components/AdminPanel";
import LoginPage from "./components/LoginPage";
import { useWebSocket } from "./api/websocket";
import { useAuth } from "./contexts/AuthContext";

// ─── Progress stepper ─────────────────────────────────────────────────────────
const STAGES = [
  { key: "listening",    label: "Listening"    },
  { key: "transcribing", label: "Transcribing" },
  { key: "extracting",   label: "Extracting"   },
  { key: "sentinel",     label: "Risk Check"   },
  { key: "bridge",       label: "Report"       },
];

function ProgressStepper({ currentStage }) {
  const activeIdx = STAGES.findIndex((s) => s.key === currentStage);
  return (
    <div className="glass rounded-xl p-4 flex items-center justify-center gap-2 mb-6">
      {STAGES.map((s, i) => (
        <React.Fragment key={s.key}>
          <div className={`flex flex-col items-center ${i <= activeIdx ? "opacity-100" : "opacity-30"}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              i < activeIdx ? "bg-emerald-500 text-white"
              : i === activeIdx ? "bg-indigo-500 text-white ring-2 ring-indigo-300"
              : "bg-slate-700 text-slate-400"
            }`}>
              {i < activeIdx ? "✓" : i + 1}
            </div>
            <span className="text-xs mt-1 text-slate-300">{s.label}</span>
          </div>
          {i < STAGES.length - 1 && (
            <div className={`h-0.5 w-10 mb-4 ${i < activeIdx ? "bg-emerald-500" : "bg-slate-700"}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const { user, isAuthenticated, hasPermission, roleDisplay, loading: authLoading, logout, authFetch, accessToken } = useAuth();

  const [screen, setScreen]             = useState("start");     // start | active | report | history | dashboard | timeline | admin
  const [outgoingNurse, setOutgoingNurse] = useState("");
  const [incomingNurse, setIncomingNurse] = useState("");
  const [patientRoom, setPatientRoom]   = useState("");
  const [sessionData, setSessionData]   = useState(null);
  const [demoLoading, setDemoLoading]   = useState(false);
  const [error, setError]               = useState("");
  const [timelinePatient, setTimelinePatient] = useState("");
  const [previousScreen, setPreviousScreen]   = useState("start");

  const { connect, disconnect, sendMessage, sendAudio, sessionState } = useWebSocket({
    onComplete: (data) => { setSessionData(data); setScreen("report"); },
    onError: (msg) => setError(msg),
  });

  const handleStartHandoff = () => {
    if (!outgoingNurse.trim() || !incomingNurse.trim()) {
      setError("Please enter both nurse names."); return;
    }
    setError(""); setScreen("active");
    connect(outgoingNurse.trim(), incomingNurse.trim(), accessToken);
  };

  const handleEndHandoff = () => sendMessage({ type: "end" });

  const handleDemo = async () => {
    if (demoLoading) return;
    setDemoLoading(true); setError("");
    try {
      const res = await authFetch(`http://${window.location.hostname}:8000/demo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outgoing: outgoingNurse.trim() || "Nurse Sarah Chen",
          incoming: incomingNurse.trim() || "Nurse Marcus Rivera",
        }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setSessionData(data); setScreen("report");
    } catch (e) {
      setError(`Demo failed: ${e.message}. Make sure the backend is running.`);
    } finally { setDemoLoading(false); }
  };

  const handleReset = () => {
    disconnect();
    setScreen("start");
    setSessionData(null);
    setError("");
    setOutgoingNurse("");
    setIncomingNurse("");
    setPatientRoom("");
    setTimelinePatient("");
  };

  const handleViewTimeline = useCallback((patientName) => {
    setPreviousScreen(screen);
    setTimelinePatient(patientName);
    setScreen("timeline");
  }, [screen]);

  // View a session loaded from history
  const handleViewSession = useCallback((data) => {
    // Reconstruct sessionData from raw DB row
    const sd = {
      session_id:     data.session_id,
      outgoing_nurse: data.outgoing_nurse,
      incoming_nurse: data.incoming_nurse,
      sbar:           data.sbar_json    ?? null,
      alerts:         data.alerts_json  ?? [],
      rendered:       data.rendered     ?? "",
      timestamp:      data.timestamp    ?? "",
      is_demo:        !!data.is_demo,
      signed_by_outgoing: !!data.signed_by_outgoing,
      signed_by_incoming: !!data.signed_by_incoming,
    };
    setSessionData(sd); setScreen("report");
  }, []);

  // ── Navigation items — driven by permissions ─────────────────────────────
  const canViewAnalytics = hasPermission("view_analytics");
  const canViewAdmin = hasPermission("manage_users") || hasPermission("manage_settings")
    || hasPermission("view_audit") || hasPermission("manage_sessions");

  const navItems = [
    { key: "start",     label: "New Handoff", always: true },
    { key: "history",   label: "History",     always: true },
    ...(canViewAnalytics ? [{ key: "dashboard", label: "Analytics" }] : []),
    ...(canViewAdmin     ? [{ key: "admin",     label: "Admin" }]     : []),
  ];

  // ── Auth loading spinner ──────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Login gate ────────────────────────────────────────────────────────────
  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <div className="min-h-screen text-white font-sans">
      {/* ── Top bar ── */}
      <header className="sticky top-0 z-30 border-b border-indigo-500/20 bg-slate-950/80 backdrop-blur-xl px-4 sm:px-6 py-3 flex items-center justify-between">
        <button
          onClick={handleReset}
          className="flex items-center gap-3 hover:opacity-90 transition-opacity"
        >
          <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-bold text-sm bg-gradient-to-br from-indigo-500 to-cyan-500 shadow-lg shadow-indigo-500/30">M</div>
          <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-indigo-300 to-cyan-300 bg-clip-text text-transparent">MedRelay</span>
          <span className="text-xs text-slate-400 ml-1 hidden sm:inline">Clinical Intelligence</span>
        </button>

        <nav className="flex items-center gap-2">
          {navItems.map((item) => {
            const active = screen === item.key;
            return (
              <button
                key={item.key}
                onClick={() => {
                  if (item.key === "start") { handleReset(); return; }
                  setScreen(item.key);
                }}
                className={`text-sm px-3 py-1.5 rounded-lg border transition-all ${
                  active
                    ? "bg-indigo-500/20 border-indigo-400/40 text-indigo-200"
                    : "btn-ghost text-slate-300"
                }`}
              >
                {item.label}
              </button>
            );
          })}
          {user && (
            <div className="hidden md:flex items-center gap-1.5">
              <span className="text-xs text-slate-400 border border-slate-700 rounded-lg px-2 py-1">
                {user.display_name || user.username}
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${
                user.role === "admin" ? "text-red-300 border-red-500/40 bg-red-500/10" :
                user.role === "supervisor" ? "text-amber-300 border-amber-500/40 bg-amber-500/10" :
                user.role === "charge_nurse" ? "text-purple-300 border-purple-500/40 bg-purple-500/10" :
                "text-cyan-300 border-cyan-500/40 bg-cyan-500/10"
              }`}>
                {roleDisplay}
              </span>
            </div>
          )}
          <button
            onClick={logout}
            className="text-xs text-slate-400 hover:text-red-300 transition-colors px-2 py-1 rounded-lg border border-transparent hover:border-red-500/30"
            title="Sign out"
          >
            Logout
          </button>
        </nav>
      </header>

      {/* ── Error banner ── */}
      {error && (
        <div className="mx-4 sm:mx-6 mt-4 rounded-xl bg-red-900/40 border border-red-500/60 text-red-200 px-4 py-3 text-sm flex items-center justify-between animate-fadeIn">
          <span>⚠ {error}</span>
          <button onClick={() => setError("")} className="ml-4 text-red-400 hover:text-white">✕</button>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 1 — Start
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "start" && (
        <main className="max-w-6xl mx-auto mt-10 px-4 pb-14 animate-fadeIn">
          <div className="grid lg:grid-cols-2 gap-8 items-start">
            <section className="pt-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-400/30 bg-indigo-500/10 text-indigo-200 text-xs mb-4">
                AI-Powered Clinical Handoffs
              </div>
              <h1 className="text-4xl sm:text-5xl font-semibold leading-tight mb-4">
                A premium handoff workspace for safer shift transitions.
              </h1>
              <p className="text-slate-300 max-w-xl leading-relaxed">
                Record naturally, generate structured SBAR, flag clinical risks, and complete dual sign-off in one streamlined experience.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-7">
                <div className="glass rounded-xl p-3">
                  <p className="text-xs text-slate-400">Pipeline</p>
                  <p className="text-sm font-semibold text-cyan-300">Relay → Extract → Sentinel → Bridge</p>
                </div>
                <div className="glass rounded-xl p-3">
                  <p className="text-xs text-slate-400">Transcription</p>
                  <p className="text-sm font-semibold text-indigo-300">Local faster-whisper</p>
                </div>
                <div className="glass rounded-xl p-3">
                  <p className="text-xs text-slate-400">Persistence</p>
                  <p className="text-sm font-semibold text-emerald-300">SQLite + Audit Trail</p>
                </div>
              </div>
            </section>

            <section className="glass rounded-2xl p-6 sm:p-7 border border-indigo-500/20">
              <h2 className="text-xl font-semibold text-indigo-200 mb-1">Start a Handoff</h2>
              <p className="text-sm text-slate-400 mb-5">Enter care team details and begin recording.</p>

              <div className="space-y-4">
                {[
                  { label: "Outgoing Nurse", val: outgoingNurse, set: setOutgoingNurse, ph: "e.g. Sarah Chen, RN" },
                  { label: "Incoming Nurse", val: incomingNurse, set: setIncomingNurse, ph: "e.g. Marcus Rivera, RN" },
                  { label: "Patient Room",   val: patientRoom,   set: setPatientRoom,   ph: "e.g. ICU-4B" },
                ].map(({ label, val, set, ph }) => (
                  <div key={label}>
                    <label className="block text-xs text-slate-400 mb-1 uppercase tracking-wide">{label}</label>
                    <input
                      type="text"
                      placeholder={ph}
                      value={val}
                      onChange={(e) => set(e.target.value)}
                      className="input-premium w-full"
                    />
                  </div>
                ))}
              </div>

              <div className="pt-5 space-y-3">
                <button onClick={handleStartHandoff} className="w-full p-3.5 rounded-xl text-base font-semibold btn-primary">
                  🎙 Begin Live Handoff
                </button>
                <button
                  onClick={handleDemo}
                  disabled={demoLoading}
                  className="w-full p-3.5 rounded-xl text-base font-semibold btn-accent disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {demoLoading ? <><span className="animate-spin">⟳</span> Running Demo…</> : "⚡ Run Demo (No Audio)"}
                </button>
              </div>
            </section>
          </div>
        </main>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 2 — Active Handoff
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "active" && (
        <main className="max-w-3xl mx-auto mt-8 px-4 pb-12 animate-fadeIn">
          <ProgressStepper currentStage={sessionState.stage} />
          <HandoffSession onEnd={handleEndHandoff} stage={sessionState.stage} sendAudio={sendAudio} />
          <LiveTranscript transcript={sessionState.transcript} />
        </main>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 3 — Report
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "report" && sessionData && (
        <main className="max-w-5xl mx-auto mt-8 px-4 pb-12 animate-fadeIn">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-3xl font-semibold">Handoff Report</h2>
              {sessionData.is_demo && (
                <span className="text-xs bg-purple-900/40 text-purple-300 border border-purple-500/50 px-2 py-0.5 rounded mt-1 inline-block">
                  Demo Session
                </span>
              )}
            </div>
            <button onClick={() => window.print()} className="px-4 py-2 rounded-lg text-sm btn-ghost">
              🖨 Export / Print
            </button>
          </div>

          <RiskAlerts alerts={sessionData.alerts} />
          <div className="mt-6"><SBARReport report={sessionData} onPatientClick={handleViewTimeline} /></div>
          <div className="mt-6">
            <SignOff
              outgoing={sessionData.outgoing_nurse}
              incoming={sessionData.incoming_nurse}
              sessionId={sessionData.session_id}
              initialOutgoingSigned={!!sessionData.signed_by_outgoing}
              initialIncomingSigned={!!sessionData.signed_by_incoming}
            />
          </div>
        </main>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 4 — History
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "history" && (
        <SessionHistory onViewSession={handleViewSession} />
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 5 — Dashboard Analytics (requires view_analytics)
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "dashboard" && canViewAnalytics && <Dashboard />}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 6 — Admin (requires admin-level permission)
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "admin" && canViewAdmin && <AdminPanel />}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 7 — Patient Timeline
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "timeline" && (
        <PatientTimeline
          patientName={timelinePatient}
          onViewSession={handleViewSession}
          onBack={() => setScreen(previousScreen || "report")}
        />
      )}
    </div>
  );
}
