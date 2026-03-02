/**
 * SBARReport — Full structured SBAR handoff report viewer.
 * Renders both the structured JSON data and the Claude-generated prose report.
 */


function Section({ title, color = "text-blue-300", children }) {
  return (
    <div className="glass rounded-xl p-5 sm:p-6">
      <h3 className={`text-lg font-bold mb-3 ${color}`}>{title}</h3>
      {children}
    </div>
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
