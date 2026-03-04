// frontend/src/components/CMIOBriefing.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

/**
 * CMIOBriefing Component
 * Displays a high-level executive summary from the 'CMIO Agent'.
 * Includes: System Health Score, Narrative Briefing, Strategic Insights, and Revenue Forecast.
 */
export default function CMIOBriefing() {
  const { authFetch } = useAuth();
  const [briefing, setBriefing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadBriefing();
  }, []);

  const loadBriefing = async () => {
    setLoading(true);
    try {
      const API = `http://${window.location.hostname}:8000`;
      const resp = await authFetch(`${API}/analytics/briefing`);
      if (!resp.ok) throw new Error("Failed to load briefing");
      const data = await resp.json();
      setBriefing(data);
    } catch (err) {
      console.error(err);
      setError("Briefing unavailable");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="animate-pulse h-32 bg-slate-800/50 rounded-xl mb-6"></div>;
  if (error || !briefing) return null; // Hide if no data

  // Color logic for health score
  const score = briefing.system_health_score;
  let scoreColor = "text-emerald-400";
  let ringColor = "border-emerald-500";
  if (score < 70) { scoreColor = "text-yellow-400"; ringColor = "border-yellow-500"; }
  if (score < 50) { scoreColor = "text-red-400"; ringColor = "border-red-500"; }

  return (
    <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 mb-8 shadow-xl relative overflow-hidden">
      {/* Decorative background element */ }
      <div className="absolute top-0 right-0 p-8 opacity-5 font-mono text-6xl select-none pointer-events-none">
        AI-CMIO
      </div>

      <div className="flex flex-col md:flex-row gap-8 relative z-10">
        {/* Left: Score & Identification */ }
        <div className="flex flex-col items-center justify-center min-w-[150px] border-r border-slate-700/50 pr-8">
          <div className={`w-24 h-24 rounded-full border-4 ${ringColor} flex items-center justify-center bg-slate-800 shadow-[0_0_15px_rgba(0,0,0,0.5)]`}>
            <span className={`text-3xl font-bold ${scoreColor}`}>{score}</span>
          </div>
          <span className="text-xs uppercase tracking-widest text-slate-500 mt-3">System Health</span>
          <div className="mt-4 px-3 py-1 bg-indigo-500/20 text-indigo-300 text-xs rounded-full border border-indigo-500/30">
            CMIO Agent
          </div>
        </div>

        {/* Center: Narrative */ }
        <div className="flex-1 space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-100 flex items-center gap-2">
              <span className="text-xl">☀️</span> Morning Executive Briefing
            </h2>
            <p className="text-slate-400 text-xs">Generated at {new Date(briefing.generated_at).toLocaleTimeString()}</p>
          </div>
          
          <div className="prose prose-invert prose-sm max-w-none">
            <p className="text-slate-300 leading-relaxed italic">
              "{briefing.narrative_summary}"
            </p>
          </div>

          {/* Strategic Insights Pills */ }
          <div className="flex flex-wrap gap-2 pt-2">
            {briefing.strategic_insights.map((insight, i) => (
              <span key={i} className="px-3 py-1 bg-slate-700/50 border border-slate-600 rounded text-xs text-cyan-200">
                💡 {insight}
              </span>
            ))}
          </div>
        </div>

        {/* Right: Revenue/Critical Stats */ }
        <div className="min-w-[200px] bg-slate-950/30 rounded-lg p-4 border border-slate-700/30 flex flex-col justify-between">
          <div>
            <h4 className="text-slate-400 text-xs uppercase font-bold mb-3">Projected Revenue</h4>
            <div className="text-2xl text-emerald-400 font-mono">
              ${briefing.projected_revenue.toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              Based on {briefing.active_census} active patients
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-700/30">
             <h4 className="text-slate-400 text-xs uppercase font-bold mb-2">Critical Alerts (24h)</h4>
             <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                <span className="text-white font-bold">{briefing.critical_alerts_24h}</span>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}
