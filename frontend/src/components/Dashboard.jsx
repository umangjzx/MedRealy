/**
 * Dashboard — Analytics dashboard with CSS-only charts.
 * Shows handoff volume, alert severity, sign-off compliance, hourly distribution,
 * top diagnoses, nurse performance, trend analysis, and quality scores.
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import CMIOBriefing from "./CMIOBriefing";

const API = `http://${window.location.hostname}:8000`;

// ─── Stat Card ───────────────────────────────────────────────────────────────
const COLOR_TO_ACCENT = {
  "text-cyan-400":    "cyan",
  "text-purple-400":  "purple",
  "text-red-400":     "red",
  "text-emerald-400": "emerald",
  "text-yellow-400":  "amber",
  "text-amber-400":   "amber",
  "text-indigo-400":  "indigo",
};

function StatCard({ label, value, icon, color, trend }) {
  const accent = COLOR_TO_ACCENT[color] || "indigo";
  return (
    <div className={`stat-card stat-card-${accent} stagger-1`}>
      <div className="flex items-center gap-3">
        <div className={`stat-card-icon stat-card-icon-${accent}`}>{icon}</div>
        <div className="min-w-0 flex-1">
          <p className={`stat-card-value ${color}`}>{value}</p>
          <p className="stat-card-label">{label}</p>
        </div>
        {trend !== undefined && (
          <span className={`text-xs font-bold px-1.5 py-0.5 rounded-md ${trend >= 0 ? "text-emerald-400 bg-emerald-500/10" : "text-red-400 bg-red-500/10"}`}>
            {trend >= 0 ? "▲" : "▼"} {Math.abs(trend)}%
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Bar Chart ───────────────────────────────────────────────────────────────
function BarChart({ data, labelKey, valueKey, color = "bg-cyan-500", title, badge }) {
  const maxVal = Math.max(...data.map((d) => d[valueKey]), 1);
  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <h3 className="chart-card-title">{title}</h3>
        {badge && <span className="chart-card-badge">{badge}</span>}
      </div>
      {data.length === 0 ? (
        <p className="text-slate-500 text-sm text-center py-8">No data yet</p>
      ) : (
        <div className="flex items-end gap-1 h-32">
          {data.map((d, i) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-1 group">
              <span className="text-[9px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
                {d[valueKey]}
              </span>
              <div
                className={`w-full ${color} rounded-t transition-all duration-300 hover:opacity-80`}
                style={{
                  height: `${(d[valueKey] / maxVal) * 100}%`,
                  minHeight: d[valueKey] > 0 ? "4px" : "0",
                }}
                title={`${d[labelKey]}: ${d[valueKey]}`}
              />
              <span className="text-[8px] text-slate-500 truncate w-full text-center">
                {d[labelKey]?.slice(-5)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Severity Distribution ───────────────────────────────────────────────────
function SeverityBars({ severity }) {
  const total = (severity.high || 0) + (severity.medium || 0) + (severity.low || 0);
  if (total === 0) return <p className="text-slate-500 text-sm">No alerts recorded yet.</p>;

  const bars = [
    { label: "HIGH", count: severity.high || 0, color: "bg-red-500", text: "text-red-400" },
    { label: "MEDIUM", count: severity.medium || 0, color: "bg-yellow-500", text: "text-yellow-400" },
    { label: "LOW", count: severity.low || 0, color: "bg-blue-500", text: "text-blue-400" },
  ];

  return (
    <div className="space-y-3">
      {bars.map((b) => (
        <div key={b.label}>
          <div className="flex justify-between text-xs mb-1">
            <span className={`font-semibold ${b.text}`}>{b.label}</span>
            <span className="text-slate-400">
              {b.count} ({Math.round((b.count / total) * 100)}%)
            </span>
          </div>
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full ${b.color} rounded-full transition-all duration-500`}
              style={{ width: `${(b.count / total) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Sign-off Compliance Ring ────────────────────────────────────────────────
function ComplianceMeter({ compliance }) {
  const { total = 0, fully_signed = 0, partially_signed = 0 } = compliance;
  const rate = total > 0 ? Math.round((fully_signed / total) * 100) : 0;
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (rate / 100) * circumference;

  return (
    <div className="flex items-center gap-6">
      <div className="relative w-24 h-24 shrink-0">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#334155" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="40" fill="none" stroke="#10b981" strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" className="transition-all duration-1000"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold text-emerald-400">{rate}%</span>
        </div>
      </div>
      <div className="text-sm space-y-1">
        <p>
          <span className="text-emerald-400 font-semibold">{fully_signed}</span>
          <span className="text-slate-400"> fully signed</span>
        </p>
        <p>
          <span className="text-yellow-400 font-semibold">{Math.max(0, partially_signed - fully_signed)}</span>
          <span className="text-slate-400"> partially signed</span>
        </p>
        <p>
          <span className="text-slate-500 font-semibold">{Math.max(0, total - partially_signed)}</span>
          <span className="text-slate-400"> unsigned</span>
        </p>
      </div>
    </div>
  );
}

// ─── Hourly Heatmap ──────────────────────────────────────────────────────────
function HourlyHeatmap({ hourly }) {
  const hours = Array.from({ length: 24 }, (_, i) => {
    const match = hourly.find((h) => h.hour === i);
    return { hour: i, count: match?.count || 0 };
  });
  const maxCount = Math.max(...hours.map((h) => h.count), 1);

  return (
    <div className="grid grid-cols-12 gap-1">
      {hours.map((h) => (
        <div key={h.hour} className="flex flex-col items-center">
          <div
            className="w-full aspect-square rounded-sm transition-all cursor-default"
            style={{
              backgroundColor:
                h.count > 0
                  ? `rgba(6, 182, 212, ${0.2 + (h.count / maxCount) * 0.8})`
                  : "rgb(30, 41, 59)",
            }}
            title={`${String(h.hour).padStart(2, "0")}:00 — ${h.count} session${h.count !== 1 ? "s" : ""}`}
          />
          <span className="text-[8px] text-slate-500 mt-0.5">
            {h.hour % 6 === 0 ? `${String(h.hour).padStart(2, "0")}h` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Top Diagnoses ───────────────────────────────────────────────────────────
function DiagnosisList({ diagnoses }) {
  if (!diagnoses?.length) return <p className="text-slate-500 text-sm">No data yet.</p>;
  const maxCount = diagnoses[0]?.count || 1;

  return (
    <div className="space-y-2.5">
      {diagnoses.map((d, i) => (
        <div key={i}>
          <div className="flex justify-between text-xs mb-0.5">
            <span className="text-slate-200 truncate mr-2">{d.diagnosis}</span>
            <span className="text-slate-500 shrink-0">{d.count}</span>
          </div>
          <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-500 rounded-full transition-all"
              style={{ width: `${(d.count / maxCount) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Quality Score Ring ──────────────────────────────────────────────────────
function QualityRing({ score, size = 96 }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="#334155" strokeWidth="8" />
          <circle
            cx="50" cy="50" r={radius} fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" className="transition-all duration-1000"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold" style={{ color }}>{Math.round(score)}</span>
        </div>
      </div>
      <span className="text-xs text-slate-400 mt-1">Quality Score</span>
    </div>
  );
}

// ─── Completeness Bars ───────────────────────────────────────────────────────
function CompletenessBars({ data }) {
  if (!data) return null;
  const items = [
    { label: "Patient Name", pct: data.patient_name ?? 0, color: "bg-cyan-500" },
    { label: "MRN", pct: data.mrn ?? 0, color: "bg-indigo-500" },
    { label: "Diagnosis", pct: data.diagnosis ?? 0, color: "bg-emerald-500" },
    { label: "Room", pct: data.room ?? 0, color: "bg-yellow-500" },
    { label: "Report Generated", pct: data.report_generated ?? 0, color: "bg-purple-500" },
    { label: "Dual Sign-Off", pct: data.dual_signoff ?? 0, color: "bg-rose-500" },
  ];

  return (
    <div className="space-y-3">
      {items.map((b) => (
        <div key={b.label}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-300">{b.label}</span>
            <span className="text-slate-400">{b.pct}%</span>
          </div>
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full ${b.color} rounded-full transition-all duration-500`}
              style={{ width: `${b.pct}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Nurse Leaderboard ───────────────────────────────────────────────────────
function NurseLeaderboard({ nurses }) {
  if (!nurses?.length) return <p className="text-slate-500 text-sm">No data yet.</p>;
  const maxHandoffs = nurses[0]?.total_handoffs || nurses[0]?.total_received || 1;

  return (
    <div className="space-y-2">
      {nurses.slice(0, 10).map((n, i) => {
        const count = n.total_handoffs ?? n.total_received ?? 0;
        const signRate = n.total_handoffs
          ? Math.round(((n.fully_signed || 0) / n.total_handoffs) * 100)
          : n.total_received
          ? Math.round(((n.signed_off || 0) / n.total_received) * 100)
          : 0;
        return (
          <div key={i} className="group">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-200 flex items-center gap-2">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  i === 0 ? "bg-yellow-500/20 text-yellow-300" :
                  i === 1 ? "bg-slate-400/20 text-slate-300" :
                  i === 2 ? "bg-amber-700/20 text-amber-400" :
                  "bg-slate-700 text-slate-500"
                }`}>{i + 1}</span>
                {n.nurse}
              </span>
              <span className="text-slate-400">
                {count} handoff{count !== 1 ? "s" : ""} · {signRate}% signed
              </span>
            </div>
            <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-full transition-all"
                style={{ width: `${(count / maxHandoffs) * 100}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Trend Bars ──────────────────────────────────────────────────────────────
function TrendBars({ data, labelKey, valueKey, color = "bg-cyan-500", title, secondaryKey, secondaryColor = "bg-purple-500" }) {
  if (!data?.length) return <p className="text-slate-500 text-sm text-center py-6">No trend data yet.</p>;
  const allVals = data.flatMap((d) => [d[valueKey] || 0, secondaryKey ? (d[secondaryKey] || 0) : 0]);
  const maxVal = Math.max(...allVals, 1);

  return (
    <div>
      <h4 className="text-xs text-slate-400 mb-3">{title}</h4>
      <div className="flex items-end gap-1 h-28">
        {data.map((d, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-0.5 group">
            <span className="text-[8px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
              {d[valueKey]}
            </span>
            <div className="w-full flex gap-px" style={{ height: "100%" }}>
              <div className="flex-1 flex items-end">
                <div
                  className={`w-full ${color} rounded-t-sm transition-all duration-300`}
                  style={{ height: `${(d[valueKey] / maxVal) * 100}%`, minHeight: d[valueKey] > 0 ? "3px" : "0" }}
                  title={`${d[labelKey]}: ${d[valueKey]}`}
                />
              </div>
              {secondaryKey && (
                <div className="flex-1 flex items-end">
                  <div
                    className={`w-full ${secondaryColor} rounded-t-sm transition-all duration-300`}
                    style={{ height: `${((d[secondaryKey] || 0) / maxVal) * 100}%`, minHeight: (d[secondaryKey] || 0) > 0 ? "3px" : "0" }}
                    title={`${d[labelKey]}: ${d[secondaryKey]}`}
                  />
                </div>
              )}
            </div>
            <span className="text-[7px] text-slate-500 truncate w-full text-center">
              {(d[labelKey] || "").slice(-6)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Risk Heatmap ────────────────────────────────────────────────────────────
function RiskHeatmap({ risks }) {
  if (!risks?.length) return <p className="text-slate-500 text-sm text-center py-6">No risk data detected.</p>;
  const maxVal = Math.max(...risks.map(r => r.count), 1);

  return (
    <div className="space-y-3">
      {risks.map((item, i) => (
        <div key={i} className="flex items-center gap-3 text-sm">
          <div className="w-1/3 text-right text-slate-400 truncate" title={item.alert}>
            {item.alert}
          </div>
          <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
             <div 
               className="h-full bg-gradient-to-r from-red-500 to-orange-500 rounded-full" 
               style={{ width: `${(item.count / maxVal) * 100}%` }}
             />
          </div>
          <div className="w-8 text-slate-300 font-mono text-xs text-right">{item.count}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Nurse Pairs ─────────────────────────────────────────────────────────────
function NursePairs({ pairs }) {
  if (!pairs?.length) return <p className="text-slate-500 text-sm">No pair data yet.</p>;
  const maxCount = pairs[0]?.count || 1;

  return (
    <div className="space-y-2">
      {pairs.map((p, i) => (
        <div key={i}>
          <div className="flex justify-between text-xs mb-0.5">
            <span className="text-slate-200 truncate mr-2">{p.pair}</span>
            <span className="text-slate-500 shrink-0">{p.count}</span>
          </div>
          <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-pink-500 to-orange-400 rounded-full transition-all"
              style={{ width: `${(p.count / maxCount) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Tab Bar ─────────────────────────────────────────────────────────────────
function TabBar({ tabs, active, onChange }) {
  return (
    <div className="dash-tabs">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={`dash-tab ${active === t.key ? "dash-tab-active" : ""}`}
        >
          {t.icon && <span className="mr-1.5 text-sm">{t.icon}</span>}
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ─── Main Dashboard ──────────────────────────────────────────────────────────
export default function Dashboard() {
  const { authFetch } = useAuth();
  const [tab, setTab] = useState("overview");
  const [analytics, setAnalytics] = useState(null);
  const [stats, setStats] = useState(null);
  const [nurseData, setNurseData] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [qualityData, setQualityData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [aRes, sRes] = await Promise.all([
        authFetch(`${API}/analytics`),
        authFetch(`${API}/stats`),
      ]);
      if (!aRes.ok) throw new Error(`Analytics fetch failed: ${aRes.status}`);
      setAnalytics(await aRes.json());
      if (sRes.ok) setStats(await sRes.json());

      // Fetch enhanced analytics in parallel (graceful fallback)
      const [nRes, tRes, qRes] = await Promise.all([
        authFetch(`${API}/analytics/nurses`).catch(() => null),
        authFetch(`${API}/analytics/trends`).catch(() => null),
        authFetch(`${API}/analytics/quality`).catch(() => null),
      ]);
      if (nRes?.ok) setNurseData(await nRes.json());
      if (tRes?.ok) setTrendData(await tRes.json());
      if (qRes?.ok) setQualityData(await qRes.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto mt-8 px-4">
        <div className="bg-red-900/40 border border-red-500 rounded-xl px-5 py-4 text-red-300 text-sm">
          Failed to load analytics: {error}
        </div>
      </div>
    );
  }

  const a = analytics || {};
  const s = stats || {};
  const n = nurseData || {};
  const t = trendData || {};
  const q = qualityData || {};

  const dashTabs = [
    { key: "overview", label: "Overview", icon: "📊" },
    { key: "nurses", label: "Nurse Performance", icon: "👩‍⚕️" },
    { key: "trends", label: "Trends", icon: "📈" },
    { key: "quality", label: "Quality", icon: "✨" },
  ];

  return (
    <div className="max-w-7xl mx-auto px-2 pb-12 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <span className="badge-info">Live Analytics</span>
          {trendData && <span className="badge-success">Data Loaded</span>}
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-white/5 border border-transparent hover:border-white/10 transition-all"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>
          Refresh
        </button>
      </div>

      {/* CMIO Executive Agent Briefing */}
      <CMIOBriefing />

      {/* Tabs */}
      <TabBar tabs={dashTabs} active={tab} onChange={setTab} />

      {/* ═══ OVERVIEW TAB ═══ */}
      {tab === "overview" && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
            <StatCard label="Total Sessions" value={s.total_sessions ?? 0} icon="📋" color="text-cyan-400" />
            <StatCard label="Unique Patients" value={a.unique_patients ?? 0} icon="🧑‍⚕️" color="text-purple-400" />
            <StatCard label="High Alerts" value={s.total_high_alerts ?? 0} icon="🔴" color="text-red-400" />
            <StatCard
              label="Sign-off Rate"
              value={s.total_sessions ? `${Math.round(((s.fully_signed || 0) / s.total_sessions) * 100)}%` : "—"}
              icon="✅" color="text-emerald-400"
            />
            <StatCard
              label="Quality Score"
              value={q.overall_quality_score ? `${Math.round(q.overall_quality_score)}` : "—"}
              icon="⭐" color="text-yellow-400"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <BarChart data={a.daily_sessions || []} labelKey="day" valueKey="count" color="bg-cyan-500" title="Daily Handoff Volume" />
            <div className="chart-card">
              <div className="chart-card-header"><h3 className="chart-card-title">Alert Severity Distribution</h3><span className="chart-card-badge">Risk</span></div>
              <SeverityBars severity={a.severity_distribution || {}} />
            </div>
            <div className="chart-card">
              <div className="chart-card-header"><h3 className="chart-card-title">Sign-off Compliance</h3><span className="chart-card-badge">TJC</span></div>
              <ComplianceMeter compliance={a.signoff_compliance || {}} />
            </div>
            <div className="chart-card">
              <div className="chart-card-header"><h3 className="chart-card-title">Handoffs by Hour of Day</h3></div>
              <HourlyHeatmap hourly={a.hourly_distribution || []} />
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-card-header"><h3 className="chart-card-title">Top Diagnoses</h3><span className="chart-card-badge">ICD-10</span></div>
            <DiagnosisList diagnoses={a.top_diagnoses || []} />
          </div>
        </>
      )}

      {/* ═══ NURSE PERFORMANCE TAB ═══ */}
      {tab === "nurses" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="chart-card">
            <div className="chart-card-header"><h3 className="chart-card-title">Top Outgoing Nurses</h3><span className="chart-card-badge">Handoffs Given</span></div>
            <NurseLeaderboard nurses={n.outgoing_nurses} />
          </div>
          <div className="chart-card">
            <div className="chart-card-header"><h3 className="chart-card-title">Top Incoming Nurses</h3><span className="chart-card-badge">Handoffs Received</span></div>
            <NurseLeaderboard nurses={n.incoming_nurses} />
          </div>
          <div className="chart-card lg:col-span-2">
            <div className="chart-card-header"><h3 className="chart-card-title">Most Frequent Nurse Pairs</h3></div>
            <NursePairs pairs={n.top_pairs} />
          </div>
        </div>
      )}

      {/* ═══ TRENDS TAB ═══ */}
      {tab === "trends" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="chart-card">
              <TrendBars
                data={t.weekly || []} labelKey="week" valueKey="sessions"
                secondaryKey="fully_signed" color="bg-cyan-500" secondaryColor="bg-emerald-500"
                title="Weekly Sessions vs Fully Signed"
              />
              <div className="flex gap-4 mt-2 text-[10px] text-slate-500">
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-cyan-500 rounded-sm" /> Sessions</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-sm" /> Fully Signed</span>
              </div>
            </div>
            <div className="chart-card">
              <TrendBars
                data={t.monthly || []} labelKey="month" valueKey="sessions"
                secondaryKey="unique_patients" color="bg-indigo-500" secondaryColor="bg-purple-500"
                title="Monthly Sessions vs Unique Patients"
              />
              <div className="flex gap-4 mt-2 text-[10px] text-slate-500">
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-indigo-500 rounded-sm" /> Sessions</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-purple-500 rounded-sm" /> Unique Patients</span>
              </div>
            </div>
          </div>

          <div className="chart-card">
            <TrendBars 
              data={a.efficiency_trend} 
              labelKey="day" 
              valueKey="avg_score" 
              color="bg-emerald-400" 
              title="Daily Efficiency Trend (Avg Score)" 
            />
          </div>

          <div className="chart-card">
            <div className="chart-card-header"><h3 className="chart-card-title">Daily Alert Trend — last 30 days</h3><span className="chart-card-badge">Clinical Risk</span></div>
            {(t.alert_trend?.length) ? (
              <>
                <div className="flex items-end gap-1 h-28">
                  {t.alert_trend.map((d, i) => {
                    const total = (d.high || 0) + (d.medium || 0) + (d.low || 0);
                    const maxBar = Math.max(...t.alert_trend.map((x) => (x.high || 0) + (x.medium || 0) + (x.low || 0)), 1);
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center group">
                        <span className="text-[8px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">{total}</span>
                        <div className="w-full flex flex-col-reverse" style={{ height: `${(total / maxBar) * 100}%`, minHeight: total > 0 ? "4px" : "0" }}>
                          {d.low > 0 && <div className="bg-blue-500" style={{ height: `${(d.low / total) * 100}%`, minHeight: "2px" }} />}
                          {d.medium > 0 && <div className="bg-yellow-500" style={{ height: `${(d.medium / total) * 100}%`, minHeight: "2px" }} />}
                          {d.high > 0 && <div className="bg-red-500 rounded-t-sm" style={{ height: `${(d.high / total) * 100}%`, minHeight: "2px" }} />}
                        </div>
                        <span className="text-[6px] text-slate-500">{d.day?.slice(-2)}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="flex gap-3 mt-2 text-[10px] text-slate-500">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500 rounded-sm" /> High</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 bg-yellow-500 rounded-sm" /> Medium</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 bg-blue-500 rounded-sm" /> Low</span>
                </div>
              </>
            ) : (
              <p className="text-slate-500 text-sm text-center py-6">No alert data yet.</p>
            )}
          </div>
        </div>
      )}

      {/* ═══ QUALITY TAB ═══ */}
      {tab === "quality" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="chart-card flex flex-col items-center justify-center">
              <QualityRing score={q.overall_quality_score || 0} size={120} />
              <p className="text-sm text-slate-300 mt-3">Overall Handoff Quality</p>
              <p className="text-xs text-slate-500 mt-1">Based on completeness + sign-off compliance</p>
            </div>

            <div className="chart-card">
              <div className="chart-card-header"><h3 className="chart-card-title">Summary</h3></div>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Total Sessions</span>
                  <span className="text-white font-semibold">{q.total_sessions ?? 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Avg Alerts / Session</span>
                  <span className="text-white font-semibold">{q.avg_alerts_per_session ?? 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Data Completeness</span>
                  <span className={`font-semibold ${(q.completeness?.diagnosis ?? 0) >= 80 ? "text-emerald-400" : "text-yellow-400"}`}>
                    {q.completeness?.diagnosis ?? 0}% (diagnosis)
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Dual Sign-Off</span>
                  <span className={`font-semibold ${(q.completeness?.dual_signoff ?? 0) >= 80 ? "text-emerald-400" : "text-yellow-400"}`}>
                    {q.completeness?.dual_signoff ?? 0}%
                  </span>
                </div>
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-header"><h3 className="chart-card-title">Field Completeness</h3><span className="chart-card-badge">CMS</span></div>
              <CompletenessBars data={q.completeness} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="chart-card">
              <TrendBars 
                data={a.quality_trend} 
                labelKey="day" 
                valueKey="avg_score" 
                color="bg-amber-400" 
                title="Daily Quality Score Trend" 
              />
            </div>
            <div className="chart-card">
              <div className="chart-card-header"><h3 className="chart-card-title">Risk Heatmap — Top Alerts</h3><span className="chart-card-badge">SSC</span></div>
              <RiskHeatmap risks={a.risk_heatmap} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
