/**
 * SBARReport — Full structured SBAR handoff report viewer.
 * Renders both the structured JSON data and the Claude-generated prose report.
 */


function Section({ title, color = "text-blue-300", children, className = "" }) {
  return (
    <div className={`glass rounded-xl p-5 sm:p-6 ${className}`}>
      <h3 className={`text-lg font-bold mb-3 ${color}`}>{title}</h3>
      {children}
    </div>
  );
}

function RiskScoreSection({ data }) {
  if (!data) return null;
  const { score, risk_level, contributing_factors } = data;
  
  const getColor = (s) => {
    if (s < 30) return "text-emerald-400 border-emerald-500/50 bg-emerald-950/30";
    if (s < 60) return "text-yellow-400 border-yellow-500/50 bg-yellow-950/30";
    if (s < 80) return "text-orange-400 border-orange-500/50 bg-orange-950/30";
    return "text-red-500 border-red-500/50 bg-red-950/30";
  };

  const colorClass = getColor(score);

  return (
    <div className={`glass rounded-xl p-5 sm:p-6 border-l-4 ${colorClass} mb-4`}>
       <div className="flex justify-between items-center mb-3">
          <h3 className="text-xl font-bold uppercase tracking-wider flex items-center gap-2">
             <span className="text-2xl">⚠</span> Clinical Risk Score
          </h3>
          <div className="text-right">
             <span className="text-4xl font-black">{score}</span><span className="text-sm opacity-60">/100</span>
             <div className="text-xs uppercase font-bold tracking-widest opacity-80">{risk_level}</div>
          </div>
       </div>
       {contributing_factors?.length > 0 && (
         <div className="mt-2">
            <p className="text-xs uppercase font-bold opacity-60 mb-1">Contributing Factors:</p>
            <div className="flex flex-wrap gap-2">
              {contributing_factors.map((f, i) => (
                <span key={i} className="px-2 py-1 rounded bg-black/20 text-xs shadow-inner border border-white/10">{f}</span>
              ))}
            </div>
         </div>
       )}
    </div>
  );
}

function ActionItemsSection({ items }) {
  if (!items?.length) return null;
  
  return (
    <Section title="⚡ Action Items" color="text-fuchsia-400" className="border border-fuchsia-500/20 bg-fuchsia-950/10">
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-900/50 border border-slate-700/50 hover:bg-slate-800/50 transition-colors group">
             <input type="checkbox" className="mt-1.5 w-4 h-4 rounded border-slate-600 bg-slate-800 text-fuchsia-500 focus:ring-fuchsia-500/50" />
             <div className="flex-1">
                <div className="flex justify-between items-start">
                   <span className="font-medium text-slate-200 group-hover:text-white transition-colors">{item.task}</span>
                   <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                      item.priority === 'HIGH' ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
                      item.priority === 'MEDIUM' ? 'bg-orange-500/20 text-orange-300 border border-orange-500/30' :
                      'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                   }`}>
                      {item.priority}
                   </span>
                </div>
                <div className="flex gap-3 mt-1 text-xs text-slate-400">
                   {item.due_time && <span>🕒 {item.due_time}</span>}
                   {item.assignee && <span>👤 {item.assignee}</span>}
                </div>
             </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Field({ label, value }) {
  if (!value && value !== 0) return null;
  return (
    <p className="text-sm mb-1">
      <span className="text-slate-400 font-medium">{label}: </span>
      <span className="text-white">{value}</span>
    </p>
  );
}

function ListField({ label, items }) {
  if (!items?.length) return null;
  return (
    <div className="text-sm mb-1">
      <span className="text-slate-400 font-medium">{label}: </span>
      <ul className="list-disc list-inside mt-0.5 ml-2">
        {items.map((item, i) => (
          <li key={i} className="text-white">{item}</li>
        ))}
      </ul>
    </div>
  );
}

/* ── New Agent Sections ─────────────────────────────────────────────────── */

function ComplianceSection({ data }) {
  if (!data) return null;
  const criticalGaps = data.gaps.filter(g => !g.met && g.severity === "CRITICAL");
  const otherGaps = data.gaps.filter(g => !g.met && g.severity !== "CRITICAL");

  return (
    <Section title="Agent 5 — Compliance Audit" color="text-red-400" className="border border-red-500/20">
      <div className="flex justify-between items-center mb-4">
        <span className="text-sm text-slate-300">Standards Checked: {data.standards_checked}</span>
        <span className={`px-3 py-1 rounded-full text-sm font-bold ${data.score >= 90 ? "bg-green-900/40 text-green-300" : "bg-red-900/40 text-red-300"}`}>
          Score: {data.score}%
        </span>
      </div>
      
      {data.gaps.every(g => g.met) ? (
        <div className="bg-green-900/20 border border-green-700/30 p-3 rounded-lg text-green-200 text-sm">
          ✓ All checked standards met. Excellent documentation.
        </div>
      ) : (
        <div className="space-y-3">
          {criticalGaps.map((gap, i) => (
            <div key={`crit-${i}`} className="bg-red-950/40 border border-red-700/40 p-3 rounded-lg">
              <div className="flex justify-between items-start">
                <span className="text-red-300 font-bold text-sm tracking-wide">CRITICAL GAP</span>
                <span className="text-xs text-slate-400 font-mono">{gap.standard}</span>
              </div>
              <p className="text-white font-medium mt-1">{gap.requirement}</p>
              <p className="text-sm text-red-200 mt-2 bg-red-900/20 p-2 rounded">Recommendation: {gap.recommendation}</p>
            </div>
          ))}
          {otherGaps.map((gap, i) => (
            <div key={`gap-${i}`} className="bg-slate-800/40 border border-slate-700 p-2 rounded">
               <div className="flex justify-between">
                 <span className="text-amber-300 text-xs font-bold">{gap.severity}</span>
                 <span className="text-xs text-slate-500 font-mono">{gap.standard}</span>
               </div>
               <p className="text-slate-200 text-sm mt-1">{gap.requirement}</p>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

function PharmaSection({ data }) {
  if (!data || (data.interactions.length === 0 && data.dose_alerts.length === 0)) return null;

  return (
    <Section title="Agent 6 — Medication Safety" color="text-orange-400" className="border border-orange-500/20">
      <div className="space-y-3">
        {data.interactions.map((ix, i) => (
          <div key={`ix-${i}`} className="bg-orange-950/40 border border-orange-700/40 p-3 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <span className="bg-orange-600 text-white text-xs font-bold px-2 py-0.5 rounded uppercase">{ix.severity}</span>
              <span className="text-orange-200 font-bold">{ix.drug_a} + {ix.drug_b}</span>
            </div>
            <p className="text-sm text-white mb-2">{ix.description}</p>
            {ix.clinical_action && (
              <p className="text-xs text-orange-200 bg-orange-900/30 p-2 rounded">Action: {ix.clinical_action}</p>
            )}
          </div>
        ))}

        {data.dose_alerts.map((al, i) => (
          <div key={`dose-${i}`} className="bg-yellow-900/20 border border-yellow-700/30 p-3 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-yellow-400 font-bold text-sm">{al.medication}</span>
              <span className="text-xs text-slate-400 uppercase tracking-wide">— {al.issue}</span>
            </div>
            <p className="text-sm text-slate-200">{al.description}</p>
            {al.recommendation && <p className="text-xs text-yellow-500 mt-1">Rec: {al.recommendation}</p>}
          </div>
        ))}
      </div>
    </Section>
  );
}

function TrendSection({ data }) {
  if (!data || data.handoffs_analysed === 0) return null;

  return (
    <Section title="Agent 7 — Trend Analysis" color="text-cyan-400" className="border border-cyan-500/20">
      <div className="mb-4 text-sm text-slate-300 flex justify-between items-center">
        <span>Analysed {data.handoffs_analysed} previous handoffs</span>
        <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${data.deterioration_risk === 'HIGH' ? 'bg-red-500/20 text-red-300' : 'bg-cyan-500/20 text-cyan-300'}`}> Risk: {data.deterioration_risk} </span>
      </div>
      
      {data.trajectory_summary && (
        <p className="text-sm text-white bg-cyan-950/40 p-3 rounded-lg mb-4 italic border-l-2 border-cyan-500">"{data.trajectory_summary}"</p>
      )}

      <div className="grid grid-cols-2 gap-3">
        {data.vital_trends.map((trend, i) => (
          <div key={i} className="bg-slate-800/40 p-2 rounded border border-slate-700 flex flex-col">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs font-bold text-slate-300 uppercase">{trend.vital_name}</span>
              <span className={`text-xs ${trend.direction === 'worsening' ? 'text-red-400' : trend.direction === 'improving' ? 'text-green-400' : 'text-slate-400'}`}>{trend.direction}</span>
            </div>
            <p className="text-xs text-slate-400 line-clamp-2">{trend.interpretation}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function EducatorSection({ data }) {
  if (!data || !data.tips?.length) return null;

  return (
    <Section title="Agent 8 — Clinical Education" color="text-indigo-400" className="border border-indigo-500/20">
      <div className="space-y-3">
        {data.tips.map((tip, i) => (
          <div key={i} className="bg-indigo-950/30 border-l-2 border-indigo-500 pl-3 py-1">
            <h4 className="text-indigo-200 font-bold text-sm mb-1">{tip.topic}</h4>
            <p className="text-slate-300 text-sm mb-2">{tip.explanation}</p>
            <div className="flex gap-2 text-[10px] text-slate-500 uppercase tracking-wider">
              <span>{tip.evidence_level.replace('_', ' ')}</span>
              {tip.source && <span>• {tip.source}</span>}
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function DebriefSection({ data }) {
  if (!data) return null;

  return (
    <Section title="Agent 9 — Handoff Quality Debrief" color="text-fuchsia-400" className="border border-fuchsia-500/20">
      <div className="flex items-center gap-4 mb-4">
        <div className="text-center bg-slate-800/60 p-2 rounded-lg min-w-[60px]">
          <div className="text-2xl font-black text-white">{data.grade}</div>
          <div className="text-[10px] text-slate-400 uppercase">Grade</div>
        </div>
        <div className="flex-1">
          <p className="text-fuchsia-200 font-medium italic">"{data.coaching_note || 'No specific coaching needed.'}"</p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {data.scorecards.map((card, i) => (
          <div key={i} className="bg-slate-900/40 p-2 rounded border border-slate-700/50">
             <div className="flex justify-between text-xs mb-1">
               <span className="text-slate-300">{card.category}</span>
               <span className={card.score === card.max_score ? "text-green-400" : "text-yellow-400"}> {card.score}/{card.max_score} </span>
             </div>
             <div className="w-full bg-slate-700 h-1 rounded-full overflow-hidden">
               <div className="bg-fuchsia-500 h-full" style={{ width: `${(card.score / card.max_score) * 100}%` }} />
             </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function BillingSection({ data }) {
  if (!data) return null; // Relaxed check for demo purposes

  return (
    <Section title="Agent 10 — Revenue Integrity & Coding" color="text-teal-400" className="border border-teal-500/20">
      <div className="flex justify-between items-center mb-4">
        <div>
          <span className="text-sm text-slate-300 block">Estimated DRG Complexity</span>
          <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase mt-1 inline-block ${
            data.drg_complexity === 'HIGH' ? 'bg-red-500/20 text-red-300' :
            data.drg_complexity === 'MODERATE' ? 'bg-teal-500/20 text-teal-300' : 'bg-slate-700 text-slate-300'
          }`}>
            {data.drg_complexity || "MODERATE"}
          </span>
        </div>
        <div className="text-right">
           <span className="text-[10px] text-slate-500 uppercase tracking-widest">Potential Revenue</span>
           <div className="text-xl font-mono text-teal-300 font-bold">
              {data.drg_complexity === 'HIGH' ? '$12,450' : data.drg_complexity === 'MODERATE' ? '$8,200' : '$4,100'}
           </div>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-2 border-b border-slate-700 pb-1">ICD-10-CM (Diagnosis)</p>
          <div className="space-y-1.5">
            {(data.suggested_lcd_codes || []).map((c, i) => (
              <div key={`lcd-${i}`} className="flex items-center justify-between text-sm bg-slate-900/40 p-2 rounded hover:bg-slate-800/60 transition-colors group">
                <div className="flex items-center gap-3">
                   <span className="text-teal-400 font-mono font-bold bg-teal-950/50 px-1.5 rounded">{c.code}</span>
                   <span className="text-slate-300 group-hover:text-white transition-colors">{c.description}</span>
                </div>
                <span className="text-[10px] text-slate-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">{(c.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
        
        <div>
          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-2 border-b border-slate-700 pb-1">CPT (Procedures)</p>
          <div className="space-y-1.5">
            {(data.suggested_cpt_codes || []).map((c, i) => (
              <div key={`cpt-${i}`} className="flex items-center justify-between text-sm bg-slate-900/40 p-2 rounded hover:bg-slate-800/60 transition-colors group">
                <div className="flex items-center gap-3">
                   <span className="text-purple-400 font-mono font-bold bg-purple-950/50 px-1.5 rounded">{c.code}</span>
                   <span className="text-slate-300 group-hover:text-white transition-colors">{c.description}</span>
                </div>
                 <span className="text-[10px] text-slate-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">{(c.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Section>
  );
}

function LiteratureSection({ data }) {
  if (!data?.resources?.length) return null;

  return (
    <Section title="Agent 11 — Clinical Decision Support" color="text-sky-400" className="border border-sky-500/20">
      <p className="text-xs text-slate-400 mb-3 uppercase tracking-wide">Evidence-based guidelines for: <span className="text-white font-bold">{data.topic}</span></p>
      <div className="space-y-3">
        {data.resources.map((res, i) => (
          <a key={i} href={res.url} target="_blank" rel="noopener noreferrer" className="block group bg-sky-950/20 border border-sky-900/50 hover:bg-sky-900/30 hover:border-sky-500/50 p-3 rounded-lg transition-all">
             <div className="flex justify-between items-start mb-1">
               <h4 className="text-sky-300 font-bold text-sm group-hover:text-sky-200 underline decoration-dotted">{res.title}</h4>
               <span className="text-[10px] bg-sky-900 text-sky-200 px-1.5 rounded">{res.source}</span>
             </div>
             <p className="text-slate-400 text-xs line-clamp-2">{res.summary}</p>
          </a>
        ))}
      </div>
    </Section>
  );
}


/* ── Main Component ─────────────────────────────────────────────────────── */

export default function SBARReport({ report, onPatientClick }) {
  if (!report) return null;
  const { sbar, timestamp, outgoing_nurse, incoming_nurse, rendered } = report;
  const patientName = sbar?.patient?.name || "Unknown Patient";

  return (
    <div className="space-y-4">
      {/* Patient Banner */}
      <div className="glass rounded-xl p-5 sm:p-6 border border-indigo-500/30">
        <div className="flex flex-wrap gap-4 justify-between">
          <div>
            <p className="text-2xl font-semibold">
              {onPatientClick && patientName !== "Unknown Patient" ? (
                <button
                  onClick={() => onPatientClick(patientName)}
                  className="hover:text-cyan-300 transition-colors underline decoration-dotted underline-offset-4"
                  title="View patient timeline"
                >
                  {patientName}
                </button>
              ) : (
                patientName
              )}
            </p>
            <p className="text-slate-300 text-sm mt-1">
              {[sbar?.patient?.age && `Age ${sbar.patient.age}`, sbar?.patient?.mrn && `MRN: ${sbar.patient.mrn}`, sbar?.patient?.room && `Room: ${sbar.patient.room}`].filter(Boolean).join("  |  ") || "No demographics available"}
            </p>
          </div>
          <div className="text-right text-sm text-slate-400 glass rounded-lg px-3 py-2 min-w-[180px]">
            <p>{timestamp || "—"}</p>
            <p>Out: <span className="text-white">{outgoing_nurse}</span></p>
            <p>In: <span className="text-white">{incoming_nurse}</span></p>
          </div>
        </div>
      </div>

      <RiskScoreSection data={sbar?.risk_score} />

      {/* S — Situation */}
      <Section title="S — Situation">
        <Field label="Primary Diagnosis"  value={sbar?.situation?.primary_diagnosis} />
        <Field label="Reason for Admission" value={sbar?.situation?.reason_for_admission} />
        <Field label="Current Status"     value={sbar?.situation?.current_status} />
      </Section>

      {/* B — Background */}
      <Section title="B — Background">
        <Field label="Relevant History" value={sbar?.background?.relevant_history} />
        <ListField label="Medications"  items={sbar?.background?.medications} />
        <ListField label="Allergies"    items={sbar?.background?.allergies} />
        <ListField label="Recent Procedures" items={sbar?.background?.recent_procedures} />
      </Section>

      {/* A — Assessment */}
      <Section title="A — Assessment" color="text-yellow-300">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3">
          {[
            { label: "BP",    value: sbar?.assessment?.vitals?.bp,   unit: "mmHg" },
            { label: "HR",    value: sbar?.assessment?.vitals?.hr,   unit: "bpm"  },
            { label: "RR",    value: sbar?.assessment?.vitals?.rr,   unit: "/min" },
            { label: "Temp",  value: sbar?.assessment?.vitals?.temp, unit: "°C"   },
            { label: "SpO2",  value: sbar?.assessment?.vitals?.spo2, unit: "%"    },
          ].map(({ label, value, unit }) =>
            value != null ? (
              <div key={label} className="bg-slate-900/60 rounded-lg p-3 text-center border border-slate-700">
                <p className="text-xs text-slate-400 mb-1">{label}</p>
                <p className="text-lg font-bold">{value}<span className="text-xs text-slate-400 ml-0.5">{unit}</span></p>
              </div>
            ) : null
          )}
        </div>
        <ListField label="Labs Pending" items={sbar?.assessment?.labs_pending} />
        <ListField label="Recent Labs"  items={sbar?.assessment?.labs_recent} />
      </Section>

      {/* R — Recommendation */}
      <Section title="R — Recommendation" color="text-green-300">
        <Field label="Care Plan"          value={sbar?.recommendation?.care_plan} />
        <Field label="Escalation Triggers" value={sbar?.recommendation?.escalation_triggers} />
        <ListField label="Pending Orders" items={sbar?.recommendation?.pending_orders} />
        <Field label="Next Steps"         value={sbar?.recommendation?.next_steps} />
      </Section>

      <ActionItemsSection items={sbar?.recommendation?.action_items} />

      {/* NEW AGENT OUTPUTS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ComplianceSection data={report.compliance} />
        <PharmaSection data={report.pharma} />
      </div>
      <TrendSection data={report.trend} />
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <EducatorSection data={report.educator} />
        <DebriefSection data={report.debrief} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BillingSection data={report.billing} />
        <LiteratureSection data={report.literature} />
      </div>

      {/* Claude-generated prose report */}
      {rendered && (
        <Section title="AI-Generated Report" color="text-purple-300">
          <div className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed font-mono bg-slate-950/60 rounded-lg p-4 border border-slate-700">
            {rendered}
          </div>
        </Section>
      )}
    </div>
  );
}
