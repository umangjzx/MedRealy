import { useState, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";

const API = `http://${window.location.hostname}:8000`;

export default function SignOff({
  outgoing,
  incoming,
  sessionId,
  initialOutgoingSigned = false,
  initialIncomingSigned = false,
}) {
  const { authFetch } = useAuth();
  const [outgoingSigned, setOutgoingSigned] = useState(initialOutgoingSigned);
  const [incomingSigned, setIncomingSigned] = useState(initialIncomingSigned);
  const [saving, setSaving] = useState(false);
  const [persistError, setPersistError] = useState(false);

  const persistSignoff = useCallback(async (sid, out, inc) => {
    if (!sid) return true;
    try {
      const res = await authFetch(`${API}/sessions/${sid}/signoff`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signed_by_outgoing: out, signed_by_incoming: inc }),
      });
      return res.ok;
    } catch (e) {
      console.warn("Sign-off persist failed:", e);
      return false;
    }
  }, [authFetch]);

  const sign = useCallback(async (role) => {
    setSaving(true);
    setPersistError(false);

    // Use functional updates to avoid stale closure race conditions
    let newOut, newIn;
    if (role === "outgoing") {
      setOutgoingSigned(true);
      newOut = true;
      // Read latest incoming from a closure-safe source
      setIncomingSigned((prev) => { newIn = prev; return prev; });
    } else {
      setIncomingSigned(true);
      newIn = true;
      setOutgoingSigned((prev) => { newOut = prev; return prev; });
    }

    // Small delay to let state settle for reads above
    await new Promise((r) => setTimeout(r, 0));

    const ok = await persistSignoff(sessionId, newOut, newIn);
    if (!ok) setPersistError(true);
    setSaving(false);
  }, [sessionId, persistSignoff]);

  const both = outgoingSigned && incomingSigned;

  return (
    <div className="mt-6 rounded-xl glass overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-700/80 flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-100">Digital Sign-Off</h3>
        {saving && <span className="text-xs text-slate-400 animate-pulse">Saving…</span>}
        {!saving && persistError && (
          <span className="text-xs text-red-400">Save failed — try again</span>
        )}
        {!saving && !persistError && sessionId && (
          <span className="text-xs text-slate-500">Session {sessionId.slice(0, 8)}…</span>
        )}
      </div>

      <div className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <SignCard label="Outgoing Nurse" name={outgoing} signed={outgoingSigned}
          onSign={() => sign("outgoing")} color="emerald" />
        <SignCard label="Incoming Nurse" name={incoming} signed={incomingSigned}
          onSign={() => sign("incoming")} color="cyan" />
      </div>

      {both && (
        <div className="mx-5 mb-5 rounded-lg bg-emerald-900/25 border border-emerald-500/40 px-4 py-3 flex items-center gap-3">
          <span className="text-2xl">✅</span>
          <div>
            <p className="text-emerald-300 font-semibold">Handoff Complete</p>
            <p className="text-emerald-400/70 text-xs mt-0.5">
              Both parties signed.{sessionId ? " Record persisted." : ""}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function SignCard({ label, name, signed, onSign, color }) {
  const c = color === "emerald"
    ? { btn: "bg-emerald-600 hover:bg-emerald-500 border-emerald-500", ring: "ring-emerald-500/40", badge: "text-emerald-300" }
    : { btn: "bg-cyan-600 hover:bg-cyan-500 border-cyan-500",         ring: "ring-cyan-500/40",    badge: "text-cyan-300" };
  return (
    <div className={`rounded-lg bg-slate-900/50 border border-slate-700 p-4 ${signed ? `ring-2 ${c.ring}` : ""} transition-all`}> 
      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">{label}</p>
      <p className="font-semibold text-slate-100 mb-3">{name || "—"}</p>
      {signed
        ? <p className={`flex items-center gap-2 text-sm font-medium ${c.badge}`}><span className="text-lg">✓</span> Signed</p>
        : <button onClick={onSign} className={`w-full py-2 rounded-lg border text-sm font-semibold text-white transition-colors ${c.btn}`}>Sign Handoff</button>
      }
    </div>
  );
}
