import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";

const API = `http://${window.location.hostname}:8000`;

const SHIFT_LABELS = { day: "Day (7a–3p)", evening: "Evening (3p–11p)", night: "Night (11p–7a)" };
const SHIFT_COLORS = { day: "text-amber-300 border-amber-500/40 bg-amber-500/10", evening: "text-purple-300 border-purple-500/40 bg-purple-500/10", night: "text-blue-300 border-blue-500/40 bg-blue-500/10" };
const ACUITY_COLORS = { 5: "bg-red-500", 4: "bg-orange-500", 3: "bg-yellow-500", 2: "bg-green-500", 1: "bg-emerald-500" };
const ACUITY_LABELS = { 5: "Critical", 4: "High", 3: "Moderate", 2: "Low", 1: "Minimal" };
const STATUS_COLORS = { draft: "text-yellow-300 border-yellow-500/40 bg-yellow-500/10", published: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10", archived: "text-slate-400 border-slate-500/40 bg-slate-500/10" };
const STAFF_STATUS_COLORS = { 
  active: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40", 
  absent: "bg-rose-500/20 text-rose-300 border-rose-500/40", 
  break: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  on_call: "bg-blue-500/20 text-blue-300 border-blue-500/40"
};

function todayStr() { return new Date().toISOString().slice(0, 10); }

// ═══════════════════════════════════════════════════════════════════════════════
//  ADMIN VIEW — Staff Availability Manager
// ═══════════════════════════════════════════════════════════════════════════════

function StaffStatusManager({ onUpdate }) {
  const { authFetch } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await authFetch(`${API}/admin/users`);
      if (r.ok) {
        const data = await r.json();
        // Filter only clinical staff
        setUsers(data.filter(u => ['nurse', 'charge_nurse', 'supervisor'].includes(u.role) && u.is_active));
      }
    } catch (err) { console.error(err); }
  }, [authFetch]);

  useEffect(() => { load(); }, [load]);

  const toggleStatus = async (user) => {
    const nextStatus = user.shift_status === 'active' ? 'absent' : 'active';
    // Optimistic update
    setUsers(prev => prev.map(u => u.user_id === user.user_id ? { ...u, shift_status: nextStatus } : u));
    
    await authFetch(`${API}/scheduling/staff/${user.user_id}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus })
    });
    if (onUpdate) onUpdate(); // Trigger re-analysis
  };

  return (
    <div className="glass rounded-xl p-4 mb-6 border border-slate-700/50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <span className="text-lg">👩‍⚕️</span> Staff Availability
        </h3>
        <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">
          Click to toggle Absent/Active
        </span>
      </div>
      
      <div className="flex flex-wrap gap-2">
        {users.map(u => (
          <button key={u.user_id} onClick={() => toggleStatus(u)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all flex items-center gap-2 ${STAFF_STATUS_COLORS[u.shift_status || 'active']}`}>
            <span className={`w-2 h-2 rounded-full ${u.shift_status === 'absent' ? 'bg-rose-500' : 'bg-emerald-500'}`} />
            {u.display_name}
            <span className="opacity-60 text-[10px] uppercase ml-1">
              {u.shift_status === 'absent' ? 'ABSENT' : 'ON SHIFT'}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  NURSE VIEW — My Schedule
// ═══════════════════════════════════════════════════════════════════════════════

function MyScheduleView({ onStartHandoff, handoffLoading }) {
  const { authFetch } = useAuth();
  const [assignments, setAssignments] = useState([]);
  const [date, setDate] = useState(todayStr());
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = date ? `${API}/scheduling/my-schedule?shift_date=${date}` : `${API}/scheduling/my-schedule`;
      const r = await authFetch(url);
      if (r.ok) { const d = await r.json(); setAssignments(d.assignments || []); }
    } finally { setLoading(false); }
  }, [authFetch, date]);

  useEffect(() => { load(); }, [load]);

  // Group by shift
  const byShift = {};
  assignments.forEach(a => {
    const key = `${a.shift_date} — ${SHIFT_LABELS[a.shift_type] || a.shift_type}`;
    if (!byShift[key]) byShift[key] = { shift_type: a.shift_type, items: [] };
    byShift[key].items.push(a);
  });

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <h3 className="text-lg font-semibold text-indigo-200">My Patient Assignments</h3>
        <input type="date" value={date} onChange={e => setDate(e.target.value)}
          className="input-premium text-sm px-3 py-1.5" />
        <button onClick={() => setDate("")} className="text-xs btn-ghost px-2 py-1 rounded-lg border border-slate-600">All Dates</button>
      </div>

      {loading && <p className="text-slate-400 text-sm animate-pulse">Loading schedule...</p>}

      {!loading && assignments.length === 0 && (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-4xl mb-3">📋</p>
          <p className="text-slate-300 font-medium">No assignments found</p>
          <p className="text-slate-500 text-sm mt-1">{date ? `No schedule for ${date}` : "No upcoming schedules"}</p>
        </div>
      )}

      {Object.entries(byShift).map(([label, { shift_type, items }]) => (
        <div key={label} className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${SHIFT_COLORS[shift_type] || ""}`}>
              {label}
            </span>
            <span className="text-xs text-slate-500">{items.length} patient{items.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map(a => (
              <div key={a.assignment_id} className="glass rounded-xl p-4 border border-slate-700/50 hover:border-indigo-500/30 transition-colors">
                <div className="flex items-start justify-between mb-2">
                  <h4 className="font-semibold text-white">{a.patient_name}</h4>
                  <span className={`w-2.5 h-2.5 rounded-full ${ACUITY_COLORS[a.acuity] || "bg-slate-500"}`}
                    title={`Acuity ${a.acuity}: ${ACUITY_LABELS[a.acuity]}`} />
                </div>
                <div className="space-y-1 text-sm text-slate-400">
                  {a.room && <p>🏥 Room {a.room}{a.bed ? `, Bed ${a.bed}` : ""}</p>}
                  {a.mrn && <p>🔖 MRN: {a.mrn}</p>}
                  {a.diagnosis && <p>📋 {a.diagnosis}</p>}
                  <p className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${ACUITY_COLORS[a.acuity]}`} />
                    Acuity {a.acuity} — {ACUITY_LABELS[a.acuity]}
                  </p>
                </div>
                {a.assignment_notes && <p className="mt-2 text-xs text-slate-500 italic">Note: {a.assignment_notes}</p>}
                {onStartHandoff && (
                  <button
                    onClick={() => onStartHandoff({
                      assignment_id: a.assignment_id,
                      patient_id: a.patient_id,
                      patient_name: a.patient_name,
                      room: a.room,
                      bed: a.bed,
                      mrn: a.mrn,
                      diagnosis: a.diagnosis,
                      acuity: a.acuity,
                      shift_date: a.shift_date,
                      shift_type: a.shift_type,
                    })}
                    disabled={handoffLoading || a.handoff_status === "completed"}
                    className="mt-3 w-full py-2 rounded-lg text-xs font-semibold btn-primary flex items-center justify-center gap-1.5 disabled:opacity-50"
                  >
                    {a.handoff_status === "completed"
                      ? "✅ Handoff Completed"
                      : handoffLoading
                        ? <><span className="animate-spin">⟳</span> Loading…</>
                        : "🎙 Start Handoff"}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
//  ADMIN VIEW — Patient Registry
// ═══════════════════════════════════════════════════════════════════════════════

function PatientRegistryTab() {
  const { authFetch } = useAuth();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [filter, setFilter] = useState("admitted");
  const [form, setForm] = useState({ name: "", mrn: "", room: "", bed: "", acuity: 3, diagnosis: "", notes: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = filter ? `${API}/scheduling/patients?status=${filter}` : `${API}/scheduling/patients`;
      const r = await authFetch(url);
      if (r.ok) { const d = await r.json(); setPatients(d.patients || []); }
    } finally { setLoading(false); }
  }, [authFetch, filter]);

  useEffect(() => { load(); }, [load]);

  const resetForm = () => { setForm({ name: "", mrn: "", room: "", bed: "", acuity: 3, diagnosis: "", notes: "" }); setEditing(null); setShowForm(false); };

  const handleSubmit = async () => {
    if (!form.name.trim()) return;
    const url = editing ? `${API}/scheduling/patients/${editing}` : `${API}/scheduling/patients`;
    const method = editing ? "PUT" : "POST";
    const r = await authFetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (r.ok) { resetForm(); load(); }
  };

  const handleDelete = async (id) => {
    if (!confirm("Remove this patient from the registry?")) return;
    await authFetch(`${API}/scheduling/patients/${id}`, { method: "DELETE" });
    load();
  };

  const handleEdit = (p) => {
    setForm({ name: p.name, mrn: p.mrn || "", room: p.room || "", bed: p.bed || "", acuity: p.acuity || 3, diagnosis: p.diagnosis || "", notes: p.notes || "" });
    setEditing(p.patient_id);
    setShowForm(true);
  };

  const handleDischarge = async (id) => {
    const r = await authFetch(`${API}/scheduling/patients/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "discharged", discharge_date: new Date().toISOString() }),
    });
    if (r.ok) load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-indigo-200">Patient Registry</h3>
          <select value={filter} onChange={e => setFilter(e.target.value)}
            className="input-premium text-sm px-2 py-1">
            <option value="">All</option>
            <option value="admitted">Admitted</option>
            <option value="discharged">Discharged</option>
            <option value="transferred">Transferred</option>
          </select>
        </div>
        <button onClick={() => { resetForm(); setShowForm(!showForm); }}
          className="px-3 py-1.5 rounded-lg text-sm btn-primary">
          {showForm ? "✕ Cancel" : "+ Add Patient"}
        </button>
      </div>

      {/* Add/Edit Form */}
      {showForm && (
        <div className="glass rounded-xl p-5 mb-5 border border-indigo-500/20 animate-fadeIn">
          <h4 className="font-semibold mb-3 text-indigo-200">{editing ? "Edit Patient" : "Register New Patient"}</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Name *</label>
              <input className="input-premium w-full text-sm" placeholder="Patient Name" value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">MRN</label>
              <input className="input-premium w-full text-sm" placeholder="MRN-001" value={form.mrn}
                onChange={e => setForm({ ...form, mrn: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Room</label>
              <input className="input-premium w-full text-sm" placeholder="ICU-4B" value={form.room}
                onChange={e => setForm({ ...form, room: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Bed</label>
              <input className="input-premium w-full text-sm" placeholder="A" value={form.bed}
                onChange={e => setForm({ ...form, bed: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Acuity (1–5)</label>
              <select className="input-premium w-full text-sm" value={form.acuity}
                onChange={e => setForm({ ...form, acuity: parseInt(e.target.value) })}>
                {[5,4,3,2,1].map(n => <option key={n} value={n}>{n} — {ACUITY_LABELS[n]}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Diagnosis</label>
              <input className="input-premium w-full text-sm" placeholder="Sepsis, CHF…" value={form.diagnosis}
                onChange={e => setForm({ ...form, diagnosis: e.target.value })} />
            </div>
          </div>
          <div className="mt-3">
            <label className="block text-xs text-slate-400 mb-1">Notes</label>
            <input className="input-premium w-full text-sm" placeholder="Additional notes…" value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>
          <button onClick={handleSubmit} className="mt-3 px-4 py-2 rounded-lg text-sm btn-primary">
            {editing ? "Update Patient" : "Register Patient"}
          </button>
        </div>
      )}

      {/* Patient list */}
      {loading ? (
        <p className="text-slate-400 text-sm animate-pulse">Loading patients...</p>
      ) : patients.length === 0 ? (
        <div className="glass rounded-xl p-6 text-center">
          <p className="text-slate-400">No patients found. Register patients to start scheduling.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 uppercase border-b border-slate-700/50">
                <th className="pb-2 px-2">Patient</th>
                <th className="pb-2 px-2">MRN</th>
                <th className="pb-2 px-2">Room</th>
                <th className="pb-2 px-2">Acuity</th>
                <th className="pb-2 px-2">Diagnosis</th>
                <th className="pb-2 px-2">Status</th>
                <th className="pb-2 px-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {patients.map(p => (
                <tr key={p.patient_id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  <td className="py-2.5 px-2 font-medium text-white">{p.name}</td>
                  <td className="py-2.5 px-2 text-slate-400">{p.mrn || "—"}</td>
                  <td className="py-2.5 px-2 text-slate-400">{p.room}{p.bed ? `-${p.bed}` : ""}</td>
                  <td className="py-2.5 px-2">
                    <span className="flex items-center gap-1.5">
                      <span className={`w-2.5 h-2.5 rounded-full ${ACUITY_COLORS[p.acuity]}`} />
                      {p.acuity} — {ACUITY_LABELS[p.acuity]}
                    </span>
                  </td>
                  <td className="py-2.5 px-2 text-slate-400 max-w-[200px] truncate">{p.diagnosis || "—"}</td>
                  <td className="py-2.5 px-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded-full border ${
                      p.status === "admitted" ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10" :
                      p.status === "discharged" ? "text-slate-400 border-slate-500/40 bg-slate-500/10" :
                      "text-amber-300 border-amber-500/40 bg-amber-500/10"
                    }`}>{p.status}</span>
                  </td>
                  <td className="py-2.5 px-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleEdit(p)} className="text-xs text-indigo-400 hover:text-indigo-300 px-1.5 py-0.5">Edit</button>
                      {p.status === "admitted" && (
                        <button onClick={() => handleDischarge(p.patient_id)}
                          className="text-xs text-amber-400 hover:text-amber-300 px-1.5 py-0.5">Discharge</button>
                      )}
                      <button onClick={() => handleDelete(p.patient_id)}
                        className="text-xs text-red-400 hover:text-red-300 px-1.5 py-0.5">Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
//  ADMIN VIEW — Schedules Manager
// ═══════════════════════════════════════════════════════════════════════════════

function SchedulesTab() {
  const { authFetch } = useAuth();
  const [schedules, setSchedules] = useState([]);
  const [selected, setSelected] = useState(null);   // schedule detail
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ shift_date: todayStr(), shift_type: "day", notes: "" });
  const [autoResult, setAutoResult] = useState(null);
  const [nurses, setNurses] = useState([]);
  const [patients, setPatients] = useState([]);
  const [manualAssign, setManualAssign] = useState({ nurse_user_id: "", patient_id: "" });

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/scheduling/schedules`);
      if (r.ok) { const d = await r.json(); setSchedules(d.schedules || []); }
    } finally { setLoading(false); }
  }, [authFetch]);

  const loadDetail = useCallback(async (id) => {
    const r = await authFetch(`${API}/scheduling/schedules/${id}`);
    if (r.ok) setSelected(await r.json());
  }, [authFetch]);

  const loadNursesAndPatients = useCallback(async () => {
    const [nr, pr] = await Promise.all([
      authFetch(`${API}/admin/users`),
      authFetch(`${API}/scheduling/patients?status=admitted`),
    ]);
    if (nr.ok) {
      const d = await nr.json();
      setNurses((d.users || []).filter(u => u.role !== "admin" && u.is_active));
    }
    if (pr.ok) { const d = await pr.json(); setPatients(d.patients || []); }
  }, [authFetch]);

  useEffect(() => { loadList(); loadNursesAndPatients(); }, [loadList, loadNursesAndPatients]);

  const handleCreate = async () => {
    const r = await authFetch(`${API}/scheduling/schedules`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(createForm),
    });
    if (r.ok) { setShowCreate(false); loadList(); const d = await r.json(); loadDetail(d.schedule_id); }
  };

  const handlePublish = async (id) => {
    await authFetch(`${API}/scheduling/schedules/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "published" }),
    });
    loadDetail(id); loadList();
  };

  const handleArchive = async (id) => {
    await authFetch(`${API}/scheduling/schedules/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "archived" }),
    });
    loadDetail(id); loadList();
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this schedule and all assignments?")) return;
    await authFetch(`${API}/scheduling/schedules/${id}`, { method: "DELETE" });
    setSelected(null); loadList();
  };

  const handleAutoSchedule = async (id, maxPPN = 6) => {
    setAutoResult(null);
    const r = await authFetch(`${API}/scheduling/schedules/${id}/auto`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_patients_per_nurse: maxPPN }),
    });
    if (r.ok) {
      const d = await r.json();
      setAutoResult(d);
      loadDetail(id);
    } else {
      const err = await r.json().catch(() => ({}));
      setAutoResult({ error: err.detail || "Auto-schedule failed" });
    }
  };

  const handleManualAssign = async (scheduleId) => {
    if (!manualAssign.nurse_user_id || !manualAssign.patient_id) return;
    const r = await authFetch(`${API}/scheduling/schedules/${scheduleId}/assignments`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(manualAssign),
    });
    if (r.ok) { setManualAssign({ nurse_user_id: "", patient_id: "" }); loadDetail(scheduleId); }
  };

  const handleRemoveAssignment = async (assignmentId) => {
    await authFetch(`${API}/scheduling/assignments/${assignmentId}`, { method: "DELETE" });
    if (selected) loadDetail(selected.schedule_id);
  };

  // ── Schedule Detail View ──
  if (selected) {
    const assignments = selected.assignments || [];
    // Group by nurse
    const byNurse = {};
    assignments.forEach(a => {
      const key = a.nurse_user_id;
      if (!byNurse[key]) byNurse[key] = { name: a.nurse_name || a.nurse_username, role: a.nurse_role, patients: [] };
      byNurse[key].patients.push(a);
    });

    return (
      <div className="animate-fadeIn">
        <button onClick={() => { setSelected(null); setAutoResult(null); }} className="text-sm text-indigo-400 hover:text-indigo-300 mb-4">
          ← Back to Schedules
        </button>

        <div className="glass rounded-xl p-5 border border-indigo-500/20 mb-5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h3 className="text-xl font-semibold text-white">
                {selected.shift_date} — {SHIFT_LABELS[selected.shift_type]}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLORS[selected.status]}`}>
                  {selected.status}
                </span>
                <span className="text-xs text-slate-500">
                  Created by {selected.creator_name || selected.creator_username || "—"}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {selected.status === "draft" && (
                <>
                  <button onClick={() => handleAutoSchedule(selected.schedule_id)}
                    className="px-3 py-1.5 rounded-lg text-sm btn-accent">
                    ⚡ Auto-Schedule
                  </button>
                  <button onClick={() => handlePublish(selected.schedule_id)}
                    className="px-3 py-1.5 rounded-lg text-sm btn-primary">
                    ✓ Publish
                  </button>
                </>
              )}
              {selected.status === "published" && (
                <button onClick={() => handleArchive(selected.schedule_id)}
                  className="px-3 py-1.5 rounded-lg text-sm btn-ghost border border-slate-600">
                  Archive
                </button>
              )}
              <button onClick={() => handleDelete(selected.schedule_id)}
                className="px-3 py-1.5 rounded-lg text-sm text-red-400 hover:text-red-300 border border-red-500/30 hover:bg-red-500/10">
                Delete
              </button>
            </div>
          </div>
        </div>

        {/* Auto-schedule result */}
        {autoResult && (
          <div className={`glass rounded-xl p-4 mb-5 border animate-fadeIn ${autoResult.error ? "border-red-500/40" : "border-emerald-500/40"}`}>
            {autoResult.error ? (
              <p className="text-red-300 text-sm">⚠ {autoResult.error}</p>
            ) : (
              <>
                <h4 className="font-semibold text-emerald-300 mb-2">✓ Auto-Schedule Complete</h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                  <div><span className="text-slate-400">Assigned:</span> <span className="text-white font-semibold">{autoResult.assigned}</span></div>
                  <div><span className="text-slate-400">Unassigned:</span> <span className="text-white font-semibold">{autoResult.unassigned}</span></div>
                  <div><span className="text-slate-400">Nurses:</span> <span className="text-white font-semibold">{autoResult.total_nurses}</span></div>
                  <div><span className="text-slate-400">Max/Nurse:</span> <span className="text-white font-semibold">{autoResult.max_patients_per_nurse}</span></div>
                </div>
                {autoResult.nurse_summary?.length > 0 && (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {autoResult.nurse_summary.map((ns, i) => (
                      <div key={i} className="bg-slate-800/50 rounded-lg p-2.5 text-sm">
                        <p className="font-medium text-white">{ns.nurse}</p>
                        <p className="text-slate-400">{ns.patient_count} patients · Acuity load: {ns.total_acuity} (avg {ns.avg_acuity})</p>
                      </div>
                    ))}
                  </div>
                )}
                {autoResult.unassigned_patients?.length > 0 && (
                  <div className="mt-3 p-2 bg-red-900/20 rounded-lg border border-red-500/30">
                    <p className="text-xs text-red-300 font-semibold mb-1">⚠ Unassigned Patients (all nurses at capacity):</p>
                    {autoResult.unassigned_patients.map((p, i) => (
                      <span key={i} className="text-xs text-red-200 mr-2">{p.name} (acuity {p.acuity})</span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Manual assignment (only for draft) */}
        {selected.status === "draft" && (
          <div className="glass rounded-xl p-4 mb-5 border border-slate-700/50">
            <h4 className="text-sm font-semibold text-slate-300 mb-2">Manual Assignment</h4>
            <div className="flex items-end gap-3 flex-wrap">
              <div className="flex-1 min-w-[150px]">
                <label className="block text-xs text-slate-400 mb-1">Nurse</label>
                <select className="input-premium w-full text-sm" value={manualAssign.nurse_user_id}
                  onChange={e => setManualAssign({ ...manualAssign, nurse_user_id: e.target.value })}>
                  <option value="">Select nurse…</option>
                  {nurses.map(n => <option key={n.user_id} value={n.user_id}>{n.display_name || n.username} ({n.role})</option>)}
                </select>
              </div>
              <div className="flex-1 min-w-[150px]">
                <label className="block text-xs text-slate-400 mb-1">Patient</label>
                <select className="input-premium w-full text-sm" value={manualAssign.patient_id}
                  onChange={e => setManualAssign({ ...manualAssign, patient_id: e.target.value })}>
                  <option value="">Select patient…</option>
                  {patients.map(p => <option key={p.patient_id} value={p.patient_id}>{p.name} — Rm {p.room} (Acuity {p.acuity})</option>)}
                </select>
              </div>
              <button onClick={() => handleManualAssign(selected.schedule_id)}
                className="px-4 py-2 rounded-lg text-sm btn-primary whitespace-nowrap">
                + Assign
              </button>
            </div>
          </div>
        )}

        {/* Assignments grouped by nurse */}
        {Object.keys(byNurse).length === 0 ? (
          <div className="glass rounded-xl p-6 text-center">
            <p className="text-slate-400">No assignments yet. Use Auto-Schedule or manual assignment above.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(byNurse).map(([nurseId, { name, role, patients: pts }]) => {
              const totalAcuity = pts.reduce((s, p) => s + (p.patient_acuity || 0), 0);
              return (
                <div key={nurseId} className="glass rounded-xl p-4 border border-slate-700/50">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-300 text-sm font-bold">
                        {(name || "N")[0].toUpperCase()}
                      </div>
                      <div>
                        <h4 className="font-semibold text-white text-sm">{name}</h4>
                        <p className="text-xs text-slate-500">{role} · {pts.length} patients · Acuity load: {totalAcuity}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {[...Array(5)].map((_, i) => (
                        <div key={i} className={`w-1.5 h-4 rounded-full ${i < Math.ceil(totalAcuity / pts.length) ? ACUITY_COLORS[Math.ceil(totalAcuity / pts.length)] : "bg-slate-700"}`} />
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {pts.map(a => (
                      <div key={a.assignment_id} className="bg-slate-800/40 rounded-lg p-3 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-white">{a.patient_name}</p>
                          <p className="text-xs text-slate-400">
                            Rm {a.patient_room}{a.patient_bed ? `-${a.patient_bed}` : ""} ·
                            Acuity <span className={`font-semibold ${a.patient_acuity >= 4 ? "text-red-300" : a.patient_acuity >= 3 ? "text-yellow-300" : "text-emerald-300"}`}>{a.patient_acuity}</span>
                            {a.patient_diagnosis ? ` · ${a.patient_diagnosis}` : ""}
                          </p>
                        </div>
                        {selected.status === "draft" && (
                          <button onClick={() => handleRemoveAssignment(a.assignment_id)}
                            className="text-red-400 hover:text-red-300 text-xs ml-2">✕</button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // ── Schedule List View ──
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-indigo-200">Schedules</h3>
        <button onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 rounded-lg text-sm btn-primary">
          {showCreate ? "✕ Cancel" : "+ New Schedule"}
        </button>
      </div>

      {showCreate && (
        <div className="glass rounded-xl p-5 mb-5 border border-indigo-500/20 animate-fadeIn">
          <h4 className="font-semibold mb-3 text-indigo-200">Create Schedule</h4>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Date</label>
              <input type="date" className="input-premium w-full text-sm" value={createForm.shift_date}
                onChange={e => setCreateForm({ ...createForm, shift_date: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Shift</label>
              <select className="input-premium w-full text-sm" value={createForm.shift_type}
                onChange={e => setCreateForm({ ...createForm, shift_type: e.target.value })}>
                <option value="day">Day (7a–3p)</option>
                <option value="evening">Evening (3p–11p)</option>
                <option value="night">Night (11p–7a)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Notes</label>
              <input className="input-premium w-full text-sm" placeholder="Optional notes…" value={createForm.notes}
                onChange={e => setCreateForm({ ...createForm, notes: e.target.value })} />
            </div>
          </div>
          <button onClick={handleCreate} className="mt-3 px-4 py-2 rounded-lg text-sm btn-primary">Create Schedule</button>
        </div>
      )}

      {loading ? (
        <p className="text-slate-400 text-sm animate-pulse">Loading schedules...</p>
      ) : schedules.length === 0 ? (
        <div className="glass rounded-xl p-6 text-center">
          <p className="text-4xl mb-3">📅</p>
          <p className="text-slate-300 font-medium">No schedules yet</p>
          <p className="text-slate-500 text-sm mt-1">Create a schedule to start assigning nurses to patients.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map(s => (
            <button key={s.schedule_id} onClick={() => loadDetail(s.schedule_id)}
              className="w-full text-left glass rounded-xl p-4 border border-slate-700/50 hover:border-indigo-500/30 transition-colors">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-white">{s.shift_date}</h4>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${SHIFT_COLORS[s.shift_type]}`}>
                      {SHIFT_LABELS[s.shift_type]}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLORS[s.status]}`}>
                      {s.status}
                    </span>
                  </div>
                </div>
                <span className="text-slate-500 text-sm">→</span>
              </div>
              {s.notes && <p className="text-xs text-slate-500 mt-2 italic">{s.notes}</p>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


function StaffingInsightPanel({ scheduleId }) {
  const { authFetch } = useAuth();
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/scheduling/ai-analysis?schedule_id=${scheduleId || ''}`);
      if (r.ok) setAnalysis(await r.json());
    } finally { setLoading(false); }
  };
  
  return (
    <div className="glass rounded-xl p-4 mb-6 relative overflow-hidden bg-gradient-to-br from-slate-900 to-indigo-900/50 border border-teal-500/20 shadow-lg shadow-teal-500/5 animate-fadeIn">
      <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-24 h-24 text-teal-400">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
        </svg>
      </div>
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div>
          <h3 className="text-lg font-bold text-teal-100 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 text-teal-400">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            AI Staffing Intelligence
          </h3>
          <p className="text-xs text-slate-400">Real-time acuity balancing & burnout prevention</p>
        </div>
        <button onClick={analyze} disabled={loading} className="px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium transition-colors flex items-center gap-2 shadow-lg shadow-teal-500/20">
            {loading ? (
                <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Analyzing...
                </>
            ) : "Run Analysis"}
        </button>
      </div>

      {analysis && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 relative z-10 animate-fadeIn">
           {/* Unit Status & Prediction */}
           <div className="flex flex-col gap-3">
             <div className={`p-4 rounded-lg border backdrop-blur-sm flex-1 ${
                 analysis.unit_status === 'Green' ? 'bg-emerald-500/10 border-emerald-500/30' : 
                 analysis.unit_status === 'Red' ? 'bg-rose-500/10 border-rose-500/30' : 
                 'bg-amber-500/10 border-amber-500/30'
              }`}>
                <div className="text-[10px] uppercase tracking-wider opacity-70 mb-1 font-bold">Unit Status</div>
                <div className={`text-2xl font-bold mb-2 ${
                    analysis.unit_status === 'Green' ? 'text-emerald-400' : 
                    analysis.unit_status === 'Red' ? 'text-rose-400' : 
                    'text-amber-400'
                }`}>
                    {analysis.unit_status}
                </div>
                <p className="text-xs opacity-90 leading-relaxed font-medium">{analysis.summary}</p>
             </div>
             
             {/* Prediction */}
             {analysis.prediction && (
               <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/30 backdrop-blur-sm">
                 <div className="text-[10px] uppercase tracking-wider text-indigo-300 mb-1 font-bold flex items-center gap-1">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
                    </svg>
                    Forecast (4h)
                 </div>
                 <p className="text-xs text-indigo-100">{analysis.prediction}</p>
               </div>
             )}
           </div>

           {/* Recommendations */}
           <div className="p-4 rounded-lg bg-slate-800/40 border border-slate-700/50 backdrop-blur-sm">
              <div className="text-[10px] uppercase tracking-wider text-indigo-300 mb-3 font-bold">Waitlist / Moves</div>
              <ul className="space-y-3">
                {analysis.recommendations.map((rec, i) => (
                    <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12.75 15l3-3m0 0l-3-3m3 3h-7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>{rec}</span>
                    </li>
                ))}
              </ul>
           </div>
           
           {/* Burnout Risks */}
           <div className="p-4 rounded-lg bg-slate-800/40 border border-slate-700/50 backdrop-blur-sm">
              <div className="text-[10px] uppercase tracking-wider text-orange-300 mb-3 font-bold">Burnout Watch</div>
              {analysis.burnout_risks.length === 0 ? (
                  <div className="text-xs text-slate-500 italic flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 text-emerald-500">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    No immediate risks detected.
                  </div>
              ) : (
                  <ul className="space-y-3">
                    {analysis.burnout_risks.map((risk, i) => (
                        <li key={i} className="text-xs text-orange-200 flex items-start gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 text-orange-500 shrink-0 mt-0.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                            </svg>
                            <span>{risk}</span>
                        </li>
                    ))}
                  </ul>
              )}
           </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ADMIN VIEW — Dashboard Stats Overview
// ═══════════════════════════════════════════════════════════════════════════════

function StatsOverview() {
  const { authFetch } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const r = await authFetch(`${API}/scheduling/stats`);
        if (r.ok) setStats(await r.json());
      } finally { setLoading(false); }
    })();
  }, [authFetch, refreshKey]);

  if (!stats) return null;

  const cards = [
    { label: "Admitted Patients", value: stats.admitted_patients, icon: "🏥", color: "text-cyan-300" },
    { label: "Active Nurses", value: stats.active_nurses, icon: "👩‍⚕️", color: "text-indigo-300" },
    { label: "Avg Patients/Nurse", value: stats.avg_patients_per_nurse, icon: "📊", color: "text-emerald-300" },
    { label: "Published Schedules", value: stats.published_schedules, icon: "✅", color: "text-green-300" },
    { label: "Draft Schedules", value: stats.draft_schedules, icon: "📝", color: "text-yellow-300" },
  ];

  return (
    <div>
      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <StaffStatusManager onUpdate={() => setRefreshKey(k => k + 1)} />
          <StaffingInsightPanel key={refreshKey} />
        </div>
      </div>

      <h3 className="text-lg font-semibold text-indigo-200 mb-4">Scheduling Overview</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        {cards.map(c => (
          <div key={c.label} className="glass rounded-xl p-4 text-center">
            <p className="text-2xl mb-1">{c.icon}</p>
            <p className={`text-2xl font-bold ${c.color}`}>{c.value}</p>
            <p className="text-xs text-slate-400 mt-1">{c.label}</p>
          </div>
        ))}
      </div>

      {stats.acuity_distribution?.length > 0 && (
        <div className="glass rounded-xl p-4">
          <h4 className="text-sm font-semibold text-slate-300 mb-3">Acuity Distribution (Admitted Patients)</h4>
          <div className="flex items-end gap-3 h-32">
            {[5,4,3,2,1].map(level => {
              const entry = stats.acuity_distribution.find(d => d.acuity === level);
              const count = entry?.count || 0;
              const max = Math.max(...stats.acuity_distribution.map(d => d.count), 1);
              const pct = (count / max) * 100;
              return (
                <div key={level} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs text-white font-semibold">{count}</span>
                  <div className="w-full rounded-t-lg transition-all" style={{ height: `${Math.max(pct, 4)}%` }}>
                    <div className={`w-full h-full rounded-t-lg ${ACUITY_COLORS[level]}`} />
                  </div>
                  <span className="text-[10px] text-slate-400">{ACUITY_LABELS[level]}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN EXPORT
// ═══════════════════════════════════════════════════════════════════════════════

export default function NurseSchedule({ onStartHandoff, handoffLoading }) {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState(isAdmin ? "overview" : "my-schedule");

  const adminTabs = [
    { key: "overview",  label: "Overview" },
    { key: "schedules", label: "Schedules" },
    { key: "patients",  label: "Patients" },
    { key: "my-schedule", label: "My Schedule" },
  ];

  const nurseTabs = [
    { key: "my-schedule", label: "My Schedule" },
  ];

  const tabs = isAdmin ? adminTabs : nurseTabs;

  return (
    <main className="max-w-6xl mx-auto mt-8 px-4 pb-12 animate-fadeIn">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-3xl font-semibold">Nurse Scheduling</h2>
          <p className="text-sm text-slate-400 mt-1">
            {isAdmin ? "Manage patient assignments, create shift schedules, and auto-balance workloads" : "View your patient assignments for upcoming shifts"}
          </p>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex items-center gap-1 mb-6 border-b border-slate-700/50 pb-2">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm rounded-t-lg transition-colors ${
              tab === t.key
                ? "bg-indigo-500/20 text-indigo-200 border-b-2 border-indigo-400"
                : "text-slate-400 hover:text-slate-200"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "overview" && isAdmin && <StatsOverview />}
      {tab === "schedules" && isAdmin && <SchedulesTab />}
      {tab === "patients" && isAdmin && <PatientRegistryTab />}
      {tab === "my-schedule" && <MyScheduleView onStartHandoff={onStartHandoff} handoffLoading={handoffLoading} />}
    </main>
  );
}
