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
  const { user, isAuthenticated, isAdmin, roleDisplay, loading: authLoading, logout, authFetch, accessToken } = useAuth();

  const [screen, setScreen]             = useState("schedule");  // confirm-handoff | active | report | history | dashboard | timeline | admin | profile | schedule
  const [outgoingNurse, setOutgoingNurse] = useState("");
  const [incomingNurse, setIncomingNurse] = useState("");
  const [sessionData, setSessionData]   = useState(null);
  const [error, setError]               = useState("");
  const [timelinePatient, setTimelinePatient] = useState("");
  const [previousScreen, setPreviousScreen]   = useState("schedule");
  const [handoffPatient, setHandoffPatient]   = useState(null);
  const [handoffLoading, setHandoffLoading]   = useState(false);
  const [language, setLanguage]         = useState("en");

  // Mark assignment as completed after successful handoff
  const markAssignmentCompleted = useCallback(async (assignmentId) => {
    if (!assignmentId) return;
    try {
      await authFetch(`http://${window.location.hostname}:8000/scheduling/assignments/${assignmentId}/handoff-complete`, {
        method: "PUT",
      });
    } catch { /* non-fatal */ }
  }, [authFetch]);

  const { connect, disconnect, sendMessage, sendAudio, sessionState } = useWebSocket({
    onComplete: (data) => {
      setSessionData(data);
      setScreen("report");
      // Auto-mark assignment as completed
      if (handoffPatient?.assignment_id) {
        markAssignmentCompleted(handoffPatient.assignment_id);
      }
    },
    onError: (msg) => setError(msg),
  });

  const handleStartHandoff = () => {
    if (!outgoingNurse.trim() || !incomingNurse.trim()) {
      setError("Please enter both nurse names."); return;
    }
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

  // Start handoff from a scheduled patient assignment
  const handleScheduleHandoff = useCallback(async (patient) => {
    setError("");
    setHandoffLoading(true);

    // Current user is the INCOMING nurse (they are viewing their upcoming shift)
    const incomingName = user?.display_name || user?.username || "";
    setIncomingNurse(incomingName);
    // Try to auto-detect the OUTGOING nurse from the previous shift
    let outgoingName = "";
    try {
      const res = await authFetch(
        `http://${window.location.hostname}:8000/scheduling/patients/${patient.patient_id}/previous-nurse?shift_date=${patient.shift_date}&shift_type=${patient.shift_type}`
      );
      if (res.ok) {
        const data = await res.json();
        if (data.found) outgoingName = data.nurse_name || "";
      }
    } catch { /* swallow — user can enter manually */ }

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
      compliance:     data.compliance   ?? {},
      pharma:         data.pharma       ?? {},
      trend:          data.trend        ?? {},
      educator:       data.educator     ?? {},
      debrief:        data.debrief      ?? {},
    };
    setSessionData(sd); setScreen("report");
  }, []);

  // ── Navigation items — strictly role-gated ─────────────────────────────────
  // USER features (all roles): New Handoff, History, Profile
  // ADMIN features (admin only): Analytics, Admin Panel

  const navItems = [
    { key: "history",   label: "History" },
    { key: "schedule",  label: "Schedule" },
    ...(isAdmin ? [{ key: "dashboard", label: "Analytics" }]  : []),
    ...(isAdmin ? [{ key: "admin",     label: "Admin" }]      : []),
    { key: "profile",   label: "Profile" },
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
    <div className="min-h-screen text-white font-sans selection:bg-indigo-500/30">
      {/* ── Floating Navbar ── */}
      <div className="fixed top-4 left-0 right-0 z-50 flex justify-center px-4">
        <header className="glass rounded-2xl px-4 py-2 flex items-center justify-between w-full max-w-5xl shadow-2xl backdrop-blur-xl border-slate-700/50">
          <button
            onClick={handleReset}
            className="flex items-center gap-3 hover:opacity-80 transition-all active:scale-95"
          >
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm bg-gradient-to-br from-indigo-500 via-purple-500 to-cyan-500 shadow-lg shadow-indigo-500/20">M</div>
            <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent hidden sm:block">MedRelay</span>
          </button>

          <nav className="flex items-center gap-1">
            {navItems.map((item) => {
              const active = screen === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => setScreen(item.key)}
                  className={`relative text-xs sm:text-sm px-3 sm:px-4 py-1.5 rounded-lg transition-all duration-300 font-medium ${
                    active
                      ? "text-white bg-white/10 shadow-inner"
                      : "text-slate-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  {item.label}
                  {active && (
                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1 h-1 bg-indigo-400 rounded-full mb-1"></span>
                  )}
                </button>
              );
            })}
          </nav>

          <div className="flex items-center gap-3 pl-4 border-l border-slate-700/50">
            {user && (
              <div className="hidden md:flex flex-col items-end leading-none">
                <span className="text-xs font-semibold text-slate-200">
                  {user.display_name?.split(" ")[0]}
                </span>
                <span className={`text-[9px] uppercase tracking-wider font-bold ${
                  user.role === "admin" ? "text-red-400" : "text-cyan-400"
                }`}>
                  {roleDisplay}
                </span>
              </div>
            )}
            <button
              onClick={logout}
              className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-red-500/10 text-slate-400 hover:text-red-400 transition-colors"
              title="Sign out"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            </button>
          </div>
        </header>
      </div>

      {/* ── Spacing for fixed header ── */}
      <div className="h-24"></div>

      {/* ── Error banner ── */}
      {error && (
        <div className="mx-4 sm:mx-6 mt-4 rounded-xl bg-red-900/40 border border-red-500/60 text-red-200 px-4 py-3 text-sm flex items-center justify-between animate-fadeIn">
          <span>⚠ {error}</span>
          <button onClick={() => setError("")} className="ml-4 text-red-400 hover:text-white">✕</button>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 1 — Confirm Handoff (from schedule)
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "confirm-handoff" && handoffPatient && (
        <main className="max-w-xl mx-auto mt-10 px-4 pb-14 animate-fadeIn">
          <div className="glass rounded-3xl p-8 border border-indigo-500/20 shadow-2xl relative overflow-hidden">
            {/* Background decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>

            <h2 className="text-3xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent mb-2">Handoff Session</h2>
            <p className="text-sm text-slate-400 mb-8">Review details and verify nurse pairing to begin.</p>

            {/* Patient info card */}
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
                  }`}>
                    Acuity {handoffPatient.acuity}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-y-2 text-sm text-slate-400">
                {handoffPatient.room && <div className="flex items-center gap-2"><span>🏥</span> Room {handoffPatient.room}</div>}
                {handoffPatient.diagnosis && <div className="col-span-2 flex items-center gap-2 text-slate-300"><span>📋</span> {handoffPatient.diagnosis}</div>}
              </div>
            </div>

            {/* Nurse pairing */}
            <div className="grid grid-cols-2 gap-4 mb-8">
              <div className="group rounded-2xl bg-slate-800/40 border border-slate-700/50 p-4 hover:bg-slate-800/60 transition-colors">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-2">Outgoing Nurse</p>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Identify nurse..."
                    value={outgoingNurse}
                    onChange={(e) => setOutgoingNurse(e.target.value)}
                    className="w-full bg-transparent border-b border-slate-600 focus:border-indigo-400 py-1 text-white font-medium outline-none transition-colors placeholder:text-slate-600"
                  />
                  <div className="absolute right-0 top-1.5 w-2 h-2 rounded-full bg-slate-600 group-hover:bg-indigo-400 transition-colors"></div>
                </div>
                <p className="text-[10px] text-slate-500 mt-2">Previous shift</p>
              </div>
              
              <div className="rounded-2xl bg-gradient-to-br from-indigo-500/10 to-cyan-500/5 border border-indigo-500/20 p-4">
                <p className="text-[10px] text-indigo-300/70 uppercase tracking-wider font-bold mb-2">Incoming Nurse</p>
                <div className="py-1 border-b border-indigo-500/30">
                  <p className="text-indigo-100 font-medium">{incomingNurse}</p>
                </div>
                <p className="text-[10px] text-indigo-300/50 mt-2">You (Current shift)</p>
              </div>
            </div>

            {/* Language Selection Pills */}
            <div className="mb-8">
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-3 font-semibold">Session Language</p>
              <div className="flex gap-3">
                {[
                  { code: "en", label: "English", icon: "A" },
                  { code: "hi", label: "Hindi",   icon: "अ" },
                  { code: "ta", label: "Tamil",   icon: "அ" },
                ].map(({ code, label, icon }) => (
                  <button
                    key={code}
                    onClick={() => setLanguage(code)}
                    className={`flex-1 flex flex-col items-center justify-center py-3 rounded-xl border transition-all duration-200 ${
                      language === code
                        ? "bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-900/20 scale-105"
                        : "bg-slate-800/30 border-slate-700/50 text-slate-400 hover:bg-slate-700/50 hover:border-slate-600"
                    }`}
                  >
                    <span className="text-lg font-serif mb-1 opacity-80">{icon}</span>
                    <span className="text-xs font-medium">{label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-3">
              <button
                onClick={handleStartHandoff}
                disabled={!outgoingNurse.trim()}
                className={`w-full py-4 rounded-xl text-base font-bold tracking-wide shadow-xl transition-all duration-300 transform ${
                  outgoingNurse.trim() 
                    ? "bg-gradient-to-r from-indigo-600 to-cyan-600 hover:shadow-indigo-500/25 hover:scale-[1.02] active:scale-[0.98] text-white" 
                    : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                }`}
              >
                {outgoingNurse.trim() ? "🎙 Start Live Session" : "Enter Outgoing Nurse to Start"}
              </button>
              
              <button
                onClick={() => { setHandoffPatient(null); setScreen("schedule"); }}
                className="w-full py-3 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
            </div>
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
          SCREEN 5 — Dashboard Analytics (admin only)
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "dashboard" && isAdmin && <Dashboard />}
      {screen === "dashboard" && !isAdmin && (
        <div className="max-w-xl mx-auto mt-20 text-center animate-fadeIn">
          <p className="text-5xl mb-4">🔒</p>
          <h2 className="text-2xl font-semibold text-slate-200">Access Denied</h2>
          <p className="text-slate-400 mt-2">Analytics dashboard is only available to administrators.</p>
          <button onClick={handleReset} className="mt-6 px-5 py-2 rounded-lg btn-primary text-sm">Back to Home</button>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 6 — Admin Panel (admin only)
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "admin" && isAdmin && <AdminPanel />}
      {screen === "admin" && !isAdmin && (
        <div className="max-w-xl mx-auto mt-20 text-center animate-fadeIn">
          <p className="text-5xl mb-4">🔒</p>
          <h2 className="text-2xl font-semibold text-slate-200">Access Denied</h2>
          <p className="text-slate-400 mt-2">Admin panel is only available to administrators.</p>
          <button onClick={handleReset} className="mt-6 px-5 py-2 rounded-lg btn-primary text-sm">Back to Home</button>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 6b — User Profile (all roles)
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "profile" && <UserProfile />}

      {/* ════════════════════════════════════════════════════════════════════
          SCREEN 8 — Nurse Scheduling (all roles)
      ════════════════════════════════════════════════════════════════════ */}
      {screen === "schedule" && <NurseSchedule onStartHandoff={!isAdmin ? handleScheduleHandoff : undefined} handoffLoading={handoffLoading} />}

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
