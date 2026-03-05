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
import NurseSchedule from "./components/NurseSchedule";
import UserProfile from "./components/UserProfile";
import LoginPage from "./components/LoginPage";
import { useWebSocket } from "./api/websocket";
import { useAuth } from "./contexts/AuthContext";

// ─── Inline SVG icons ─────────────────────────────────────────────────────────
const IcoSchedule = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
  </svg>
);
const IcoHistory = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><polyline points="12 7 12 12 15 15"/>
  </svg>
);
const IcoAnalytics = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
  </svg>
);
const IcoAdmin = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
);
const IcoProfile = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
  </svg>
);
const IcoLogout = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);
const IcoMenu = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
);
const IcoClose = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const IcoBell = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
  </svg>
);

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

// ─── Page meta ────────────────────────────────────────────────────────────────
const PAGE_META = {
  schedule:        { title: "Nurse Schedule",       subtitle: "Shift assignments & patient handoffs" },
  history:         { title: "Session History",      subtitle: "Previous handoff records" },
  dashboard:       { title: "Analytics Dashboard",  subtitle: "Handoff performance & clinical insights" },
  admin:           { title: "Admin Panel",          subtitle: "User management & system config" },
  profile:         { title: "My Profile",           subtitle: "Account settings & preferences" },
  "confirm-handoff": { title: "New Handoff",        subtitle: "Review details and start session" },
  active:          { title: "Live Session",         subtitle: "Recording in progress…" },
  report:          { title: "Handoff Report",       subtitle: "AI-generated SBAR & clinical insights" },
  timeline:        { title: "Patient Timeline",     subtitle: "Longitudinal vital history" },
};

// ─── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const { user, isAuthenticated, isAdmin, roleDisplay, loading: authLoading, logout, authFetch, accessToken } = useAuth();

  const [screen, setScreen]                   = useState("schedule");
  const [outgoingNurse, setOutgoingNurse]     = useState("");
  const [incomingNurse, setIncomingNurse]     = useState("");
  const [sessionData, setSessionData]         = useState(null);
  const [error, setError]                     = useState("");
  const [timelinePatient, setTimelinePatient] = useState("");
  const [previousScreen, setPreviousScreen]   = useState("schedule");
  const [handoffPatient, setHandoffPatient]   = useState(null);
  const [handoffLoading, setHandoffLoading]   = useState(false);
  const [language, setLanguage]               = useState("en");
  const [sidebarOpen, setSidebarOpen]         = useState(false);

  const markAssignmentCompleted = useCallback(async (assignmentId) => {
    if (!assignmentId) return;
    try {
      await authFetch(`http://${window.location.hostname}:8000/scheduling/assignments/${assignmentId}/handoff-complete`, { method: "PUT" });
    } catch { /* non-fatal */ }
  }, [authFetch]);

  const { connect, disconnect, sendMessage, sendAudio, sessionState } = useWebSocket({
    onComplete: (data) => {
      setSessionData(data);
      setScreen("report");
      if (handoffPatient?.assignment_id) markAssignmentCompleted(handoffPatient.assignment_id);
    },
    onError: (msg) => setError(msg),
  });

  const handleStartHandoff = () => {
    if (!outgoingNurse.trim() || !incomingNurse.trim()) { setError("Please enter both nurse names."); return; }
    setError(""); setScreen("active");
    connect(outgoingNurse.trim(), incomingNurse.trim(), accessToken, language);
  };

  const handleEndHandoff = () => sendMessage({ type: "end" });

  const handleReset = () => {
    disconnect();
    setScreen("schedule");
    setSessionData(null);
    setError("");
    setOutgoingNurse("");
    setIncomingNurse("");
    setTimelinePatient("");
    setHandoffPatient(null);
    setHandoffLoading(false);
    setLanguage("en");
  };

  const handleScheduleHandoff = useCallback(async (patient) => {
    setError("");
    setHandoffLoading(true);
    const incomingName = user?.display_name || user?.username || "";
    setIncomingNurse(incomingName);
    let outgoingName = "";
    try {
      const res = await authFetch(
        `http://${window.location.hostname}:8000/scheduling/patients/${patient.patient_id}/previous-nurse?shift_date=${patient.shift_date}&shift_type=${patient.shift_type}`
      );
      if (res.ok) { const data = await res.json(); if (data.found) outgoingName = data.nurse_name || ""; }
    } catch { /* swallow */ }
    setOutgoingNurse(outgoingName);
    setHandoffPatient(patient);
    setHandoffLoading(false);
    setScreen("confirm-handoff");
  }, [user, authFetch]);

  const handleViewTimeline = useCallback((patientName) => {
    setPreviousScreen(screen);
    setTimelinePatient(patientName);
    setScreen("timeline");
  }, [screen]);

  const handleViewSession = useCallback((data) => {
    const sd = {
      session_id:          data.session_id,
      outgoing_nurse:      data.outgoing_nurse,
      incoming_nurse:      data.incoming_nurse,
      sbar:                data.sbar_json    ?? null,
      alerts:              data.alerts_json  ?? [],
      rendered:            data.rendered     ?? "",
      timestamp:           data.timestamp    ?? "",
      is_demo:             !!data.is_demo,
      signed_by_outgoing:  !!data.signed_by_outgoing,
      signed_by_incoming:  !!data.signed_by_incoming,
      compliance:          data.compliance   ?? {},
      pharma:              data.pharma       ?? {},
      trend:               data.trend        ?? {},
      educator:            data.educator     ?? {},
      debrief:             data.debrief      ?? {},
    };
    setSessionData(sd); setScreen("report");
  }, []);

  const navItems = [
    { key: "schedule",  label: "Schedule",  icon: <IcoSchedule /> },
    { key: "history",   label: "History",   icon: <IcoHistory /> },
    ...(isAdmin ? [{ key: "dashboard", label: "Analytics", icon: <IcoAnalytics /> }] : []),
    ...(isAdmin ? [{ key: "admin",     label: "Admin",     icon: <IcoAdmin />     }] : []),
    { key: "profile",   label: "Profile",   icon: <IcoProfile /> },
  ];

  const pageMeta = PAGE_META[screen] || { title: "MedRelay", subtitle: "" };

  // ── Auth loading spinner ──────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) return <LoginPage />;

  return (
    <div className="app-shell">
      {/* ── Mobile sidebar backdrop ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ═══════════ SIDEBAR ═══════════ */}
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">M</div>
          <span className="sidebar-logo-text">MedRelay</span>
          <button className="sidebar-close-btn lg:hidden" onClick={() => setSidebarOpen(false)}>
            <IcoClose />
          </button>
        </div>

        {/* Nav section */}
        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="sidebar-menu">
          {navItems.map((item) => {
            const active = screen === item.key ||
              (screen === "confirm-handoff" && item.key === "schedule") ||
              (screen === "active"          && item.key === "schedule") ||
              (screen === "report"          && item.key === "history")  ||
              (screen === "timeline"        && item.key === "history");
            return (
              <button
                key={item.key}
                onClick={() => { setScreen(item.key); setSidebarOpen(false); }}
                className={`sidebar-item ${active ? "sidebar-item-active" : ""}`}
              >
                <span className="sidebar-item-icon">{item.icon}</span>
                <span className="sidebar-item-label">{item.label}</span>
                {active && <span className="sidebar-active-pip" />}
              </button>
            );
          })}
        </nav>

        {/* System status */}
        <div className="sidebar-status">
          <span className="status-dot status-dot-green" />
          <span className="sidebar-status-text">All Systems Online</span>
        </div>

        {/* Bottom user row */}
        <div className="sidebar-user-row">
          <div className="sidebar-avatar">
            {(user?.display_name?.[0] || user?.username?.[0] || "?").toUpperCase()}
          </div>
          <div className="sidebar-user-meta">
            <span className="sidebar-user-name">
              {user?.display_name?.split(" ")[0] || user?.username}
            </span>
            <span className={`sidebar-user-role ${user?.role === "admin" ? "role-admin" : "role-nurse"}`}>
              {roleDisplay}
            </span>
          </div>
          <button onClick={logout} className="sidebar-logout-btn" title="Sign out">
            <IcoLogout />
          </button>
        </div>
      </aside>

      {/* ═══════════ MAIN AREA ═══════════ */}
      <div className="main-area">
        {/* Top bar */}
        <header className="topbar">
          <div className="topbar-left">
            <button className="topbar-hamburger lg:hidden" onClick={() => setSidebarOpen(true)}>
              <IcoMenu />
            </button>
            <div>
              <h1 className="topbar-title">{pageMeta.title}</h1>
              <p className="topbar-subtitle">{pageMeta.subtitle}</p>
            </div>
          </div>
          <div className="topbar-right">
            <div className="topbar-pill">
              <span className="status-dot status-dot-green" />
              <span>Live</span>
            </div>
            <button className="topbar-icon-btn" title="Notifications">
              <IcoBell />
            </button>
            <div className="topbar-avatar">
              {(user?.display_name?.[0] || user?.username?.[0] || "?").toUpperCase()}
            </div>
          </div>
        </header>

        {/* Error banner */}
        {error && (
          <div className="mx-4 sm:mx-6 mt-2 rounded-xl bg-red-900/40 border border-red-500/60 text-red-200 px-4 py-3 text-sm flex items-center justify-between animate-fadeIn">
            <span>⚠ {error}</span>
            <button onClick={() => setError("")} className="ml-4 text-red-400 hover:text-white transition-colors">✕</button>
          </div>
        )}

        {/* ── Scrollable content ── */}
        <main className="content-area">

          {/* ── SCREEN: Confirm Handoff ── */}
          {screen === "confirm-handoff" && handoffPatient && (
            <div className="max-w-xl mx-auto px-4 pb-14 animate-fadeIn">
              <div className="glass rounded-3xl p-8 border border-indigo-500/20 shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />
                <h2 className="text-3xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent mb-2">Handoff Session</h2>
                <p className="text-sm text-slate-400 mb-8">Review details and verify nurse pairing to begin.</p>
                <div className="rounded-2xl bg-white/5 border border-white/10 p-5 mb-6 backdrop-blur-sm">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-bold text-white text-xl tracking-tight">{handoffPatient.patient_name}</h3>
                      <p className="text-xs text-indigo-300 font-medium mt-0.5">ID: {handoffPatient.mrn}</p>
                    </div>
                    {handoffPatient.acuity && (
                      <span className={`px-3 py-1 rounded-full text-xs font-bold border ${
                        handoffPatient.acuity >= 4 ? "bg-red-500/20 text-red-300 border-red-500/30" :
                        handoffPatient.acuity === 3 ? "bg-amber-500/20 text-amber-300 border-amber-500/30" :
                        "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                      }`}>Acuity {handoffPatient.acuity}</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-y-2 text-sm text-slate-400">
                    {handoffPatient.room && <div className="flex items-center gap-2"><span>🏥</span> Room {handoffPatient.room}</div>}
                    {handoffPatient.diagnosis && <div className="col-span-2 flex items-center gap-2 text-slate-300"><span>📋</span> {handoffPatient.diagnosis}</div>}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mb-8">
                  <div className="group rounded-2xl bg-slate-800/40 border border-slate-700/50 p-4 hover:bg-slate-800/60 transition-colors">
                    <p className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-2">Outgoing Nurse</p>
                    <div className="relative">
                      <input type="text" placeholder="Identify nurse..." value={outgoingNurse} onChange={(e) => setOutgoingNurse(e.target.value)}
                        className="w-full bg-transparent border-b border-slate-600 focus:border-indigo-400 py-1 text-white font-medium outline-none transition-colors placeholder:text-slate-600" />
                      <div className="absolute right-0 top-1.5 w-2 h-2 rounded-full bg-slate-600 group-hover:bg-indigo-400 transition-colors" />
                    </div>
                    <p className="text-[10px] text-slate-500 mt-2">Previous shift</p>
                  </div>
                  <div className="rounded-2xl bg-gradient-to-br from-indigo-500/10 to-cyan-500/5 border border-indigo-500/20 p-4">
                    <p className="text-[10px] text-indigo-300/70 uppercase tracking-wider font-bold mb-2">Incoming Nurse</p>
                    <div className="py-1 border-b border-indigo-500/30"><p className="text-indigo-100 font-medium">{incomingNurse}</p></div>
                    <p className="text-[10px] text-indigo-300/50 mt-2">You (Current shift)</p>
                  </div>
                </div>
                <div className="mb-8">
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-3 font-semibold">Session Language</p>
                  <div className="flex gap-3">
                    {[{ code: "en", label: "English", icon: "A" }, { code: "hi", label: "Hindi", icon: "अ" }, { code: "ta", label: "Tamil", icon: "அ" }].map(({ code, label, icon }) => (
                      <button key={code} onClick={() => setLanguage(code)}
                        className={`flex-1 flex flex-col items-center justify-center py-3 rounded-xl border transition-all duration-200 ${
                          language === code ? "bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-900/20 scale-105"
                          : "bg-slate-800/30 border-slate-700/50 text-slate-400 hover:bg-slate-700/50 hover:border-slate-600"
                        }`}>
                        <span className="text-lg font-serif mb-1 opacity-80">{icon}</span>
                        <span className="text-xs font-medium">{label}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col gap-3">
                  <button onClick={handleStartHandoff} disabled={!outgoingNurse.trim()}
                    className={`w-full py-4 rounded-xl text-base font-bold tracking-wide shadow-xl transition-all duration-300 transform ${
                      outgoingNurse.trim()
                        ? "bg-gradient-to-r from-indigo-600 to-cyan-600 hover:shadow-indigo-500/25 hover:scale-[1.02] active:scale-[0.98] text-white"
                        : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                    }`}>
                    {outgoingNurse.trim() ? "🎙 Start Live Session" : "Enter Outgoing Nurse to Start"}
                  </button>
                  <button onClick={() => { setHandoffPatient(null); setScreen("schedule"); }}
                    className="w-full py-3 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ── SCREEN: Active Handoff ── */}
          {screen === "active" && (
            <div className="max-w-3xl mx-auto px-4 pb-12 animate-fadeIn">
              <ProgressStepper currentStage={sessionState.stage} />
              <HandoffSession onEnd={handleEndHandoff} stage={sessionState.stage} sendAudio={sendAudio} />
              <LiveTranscript transcript={sessionState.transcript} />
            </div>
          )}

          {/* ── SCREEN: Report ── */}
          {screen === "report" && sessionData && (
            <div className="max-w-5xl mx-auto px-4 pb-12 animate-fadeIn">
              <div className="flex items-center justify-between mb-6">
                <div>
                  {sessionData.is_demo && (
                    <span className="text-xs bg-purple-900/40 text-purple-300 border border-purple-500/50 px-2 py-0.5 rounded mb-2 inline-block">
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
            </div>
          )}

          {/* ── SCREEN: History ── */}
          {screen === "history" && <SessionHistory onViewSession={handleViewSession} />}

          {/* ── SCREEN: Analytics (admin only) ── */}
          {screen === "dashboard" && isAdmin && <Dashboard />}
          {screen === "dashboard" && !isAdmin && (
            <div className="max-w-xl mx-auto mt-20 text-center animate-fadeIn">
              <p className="text-5xl mb-4">🔒</p>
              <h2 className="text-2xl font-semibold text-slate-200">Access Denied</h2>
              <p className="text-slate-400 mt-2">Analytics is only available to administrators.</p>
              <button onClick={handleReset} className="mt-6 px-5 py-2 rounded-lg btn-primary text-sm">Back to Home</button>
            </div>
          )}

          {/* ── SCREEN: Admin (admin only) ── */}
          {screen === "admin" && isAdmin && <AdminPanel />}
          {screen === "admin" && !isAdmin && (
            <div className="max-w-xl mx-auto mt-20 text-center animate-fadeIn">
              <p className="text-5xl mb-4">🔒</p>
              <h2 className="text-2xl font-semibold text-slate-200">Access Denied</h2>
              <p className="text-slate-400 mt-2">Admin panel is only available to administrators.</p>
              <button onClick={handleReset} className="mt-6 px-5 py-2 rounded-lg btn-primary text-sm">Back to Home</button>
            </div>
          )}

          {/* ── SCREEN: Profile ── */}
          {screen === "profile" && <UserProfile />}

          {/* ── SCREEN: Schedule ── */}
          {screen === "schedule" && (
            <NurseSchedule
              onStartHandoff={!isAdmin ? handleScheduleHandoff : undefined}
              handoffLoading={handoffLoading}
            />
          )}

          {/* ── SCREEN: Patient Timeline ── */}
          {screen === "timeline" && (
            <PatientTimeline
              patientName={timelinePatient}
              onViewSession={handleViewSession}
              onBack={() => setScreen(previousScreen || "report")}
            />
          )}
        </main>
      </div>
    </div>
  );
}
