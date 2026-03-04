"""
MedRelay — Agent Orchestration Pipeline
Runs the 4-agent handoff pipeline sequentially:
  Relay -> Extract -> Sentinel -> Bridge
Falls back to rich hardcoded demo data when Claude/OpenAI API keys are unavailable.
"""

import traceback
from datetime import datetime
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, START, END
from backend.agents.relay_agent import RelayAgent
from backend.agents.extract_agent import ExtractAgent
from backend.agents.sentinel_agent import SentinelAgent
from backend.agents.bridge_agent import BridgeAgent
from backend.agents.compliance_agent import ComplianceAgent
from backend.agents.pharma_agent import PharmaAgent
from backend.agents.trend_agent import TrendAgent
from backend.agents.educator_agent import EducatorAgent
from backend.agents.debrief_agent import DebriefAgent
from backend.agents.billing_agent import BillingAgent
from backend.agents.literature_agent import LiteratureAgent
from backend.database import get_history_for_trends
from backend.constants import DEMO_TRANSCRIPT
from backend.models import (
    FinalReport, SBARData, PatientInfo, Situation, Background,
    Assessment, Recommendation, Vitals, RiskAlert,
    ComplianceReport, PharmaReport, TrendReport, VitalTrend, EducatorReport, DebriefReport,
    BillingReport, LiteratureReport
)


def _demo_sbar() -> SBARData:
    """Rich hardcoded SBAR for demo/fallback when Claude is unavailable."""
    return SBARData(
        patient=PatientInfo(name="Sarah Mitchell", age="67", mrn="ICU-2024-0447", room="ICU 4B"),
        situation=Situation(
            primary_diagnosis="Septic shock secondary to pneumonia",
            reason_for_admission="Septic shock — transferred from ED yesterday",
            current_status="Hemodynamically unstable, on vasopressor support",
        ),
        background=Background(
            relevant_history="Hypertension, Type 2 diabetes — otherwise no significant surgical history",
            medications=["Norepinephrine 0.1 mcg/kg/min IV", "Vancomycin 1g IV q12h", "Piperacillin-Tazobactam 3.375g IV q6h"],
            allergies=["Penicillin (anaphylaxis)"],
            recent_procedures=["Central line placement (right subclavian)", "Arterial line (left radial)"],
        ),
        assessment=Assessment(
            vitals=Vitals(bp="88/54", hr=118, rr=24, temp=38.9, spo2=91),
            labs_pending=["Blood cultures x2", "Repeat serum lactate", "Morning CBC with differential"],
            labs_recent=["Lactate 4.2 mmol/L (elevated)", "WBC 18.4 (elevated)", "Procalcitonin 22.1"],
        ),
        recommendation=Recommendation(
            care_plan="Continue vasopressor support; titrate norepi to MAP ≥ 65 mmHg. Await culture results for antibiotic de-escalation.",
            escalation_triggers="MAP < 65 mmHg, SpO2 < 88%, increasing vasopressor requirements — activate Rapid Response",
            pending_orders=["Repeat lactate in 2 hours", "Echo to assess cardiac function", "Infectious disease consult"],
            next_steps="Continue SICU monitoring q1h vitals. Daughter (healthcare proxy) updated at 0700 — contact if status changes.",
        ),
    )


def _demo_alerts() -> list:
    return [
        RiskAlert(severity="HIGH",   category="medication",  description="⚠ Piperacillin-Tazobactam prescribed — CONTAINS PENICILLIN. Patient has documented penicillin allergy (anaphylaxis). Review immediately."),
        RiskAlert(severity="HIGH",   category="vital",       description="SpO2 91% — below threshold of 92%. Patient on high-flow oxygen. Risk of rapid deterioration."),
        RiskAlert(severity="HIGH",   category="vital",       description="BP 88/54 mmHg — critically low. On norepinephrine support. Monitor MAP continuously."),
        RiskAlert(severity="MEDIUM", category="vital",       description="Heart rate 118 bpm — elevated (threshold: 120). May indicate ongoing sepsis or inadequate fluid resuscitation."),
        RiskAlert(severity="MEDIUM", category="vital",       description="Temperature 38.9°C — febrile. Consistent with active infection/sepsis."),
        RiskAlert(severity="LOW",    category="missing",     description="No documented weight/BMI for vasopressor dose calculation. Confirm actual body weight."),
    ]


def _demo_rendered(outgoing: str, incoming: str) -> str:
    return f"""CLINICAL HANDOFF REPORT — ICU 4B
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
Outgoing: {outgoing}  |  Incoming: {incoming}

PATIENT: Sarah Mitchell | 67F | MRN ICU-2024-0447 | ICU 4B

── SITUATION ────────────────────────────────────────────────
Dx: Septic shock secondary to pneumonia (admitted yesterday from ED)
Status: Hemodynamically unstable — on vasopressor support (Norepinephrine 0.1 mcg/kg/min)

── BACKGROUND ───────────────────────────────────────────────
PMH: Hypertension, Type 2 Diabetes
Allergies: ⚠ PENICILLIN (anaphylaxis)
Medications: Norepinephrine, Vancomycin 1g IV q12h, Pip-Tazo 3.375g IV q6h
Procedures: Central line (R subclavian), Art line (L radial)

── ASSESSMENT ───────────────────────────────────────────────
Vitals: BP 88/54 | HR 118 | RR 24 | Temp 38.9°C | SpO2 91% on high-flow O2
Labs:   Lactate 4.2 ↑ | WBC 18.4 ↑ | Procalcitonin 22.1 ↑
Pending: Blood cultures x2, repeat lactate, morning CBC

── RECOMMENDATION ───────────────────────────────────────────
Plan: Continue vasopressor titration to MAP ≥ 65 mmHg. Await cultures for antibiotic de-escalation.
Escalation triggers: MAP < 65, SpO2 < 88%, increasing vasopressors → RAPID RESPONSE
Pending orders: Repeat lactate q2h, Echo, ID consult
Family: Daughter (healthcare proxy) updated at 0700; contact for status changes.

⚠ CRITICAL ALERT: Pip-Tazo contains penicillin — patient has documented anaphylaxis allergy. Review with prescriber immediately."""


def _missing_transcript_rendered(outgoing: str, incoming: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""CLINICAL HANDOFF REPORT
Generated: {ts}
Outgoing: {outgoing}  |  Incoming: {incoming}

No valid transcript was captured from the live recording.

Action required:
- Verify microphone permission in browser settings
- Confirm input device is selected and receiving audio
- Retry handoff capture

This report was generated without clinical content and is NOT demo data.
"""


def _sbar_is_empty(sbar: SBARData) -> bool:
    """Return True if Claude didn't populate the SBAR (all critical fields null)."""
    return (
        sbar.patient.name is None
        and sbar.situation.primary_diagnosis is None
        and sbar.situation.reason_for_admission is None
        and not sbar.background.medications
        and sbar.assessment.vitals.hr is None
        and sbar.assessment.vitals.bp is None
    )


# ── Fallback SBAR extraction from raw transcript (no AI) ─────────────────────

import re as _re


def _extract_field(transcript: str, patterns: list[str]) -> str | None:
    """Try multiple regex patterns against transcript, return first match."""
    for pat in patterns:
        m = _re.search(pat, transcript, _re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_number(transcript: str, patterns: list[str]) -> float | int | None:
    """Try regex patterns that capture a number."""
    for pat in patterns:
        m = _re.search(pat, transcript, _re.IGNORECASE)
        if m:
            try:
                val = m.group(1)
                return float(val) if "." in val else int(val)
            except ValueError:
                continue
    return None


def _sbar_from_transcript(transcript: str) -> SBARData:
    """Best-effort SBAR extraction using regex — no AI needed."""
    t = transcript

    # Patient info
    name = _extract_field(t, [
        r"patient(?:'s)?\s+(?:name\s+(?:is\s+)?)?([A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"(?:this is|handing off|about)\s+(?:patient\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"(?:Mr\.|Mrs\.|Ms\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ])
    age = _extract_field(t, [
        r"(\d{1,3})\s*[-–]?\s*year\s*[-–]?\s*old",
        r"age\s*(?:is\s+)?(\d{1,3})",
    ])
    mrn = _extract_field(t, [
        r"MRN\s*[:=]?\s*([\w-]+)",
        r"medical record\s*(?:number)?\s*[:=]?\s*([\w-]+)",
    ])
    room = _extract_field(t, [
        r"(?:room|bed|bay)\s*[:=]?\s*([\w\d\s-]+?)(?:\.|,|$)",
        r"(ICU\s*\d*\w*)",
    ])

    # Situation
    dx = _extract_field(t, [
        r"diagnos(?:is|ed)\s*(?:is|with|of)?\s*[:=]?\s*(.+?)(?:\.|,|$)",
        r"admitted\s+(?:for|with)\s+(.+?)(?:\.|,|$)",
        r"primary\s+(?:diagnosis|dx)\s*[:=]?\s*(.+?)(?:\.|,|$)",
    ])
    reason = _extract_field(t, [
        r"(?:admitted|admission|came in)\s+(?:for|because|due to)\s+(.+?)(?:\.|,|$)",
        r"reason\s+for\s+admission\s*[:=]?\s*(.+?)(?:\.|,|$)",
    ]) or dx
    status = _extract_field(t, [
        r"(?:currently|current status|right now|at this time)\s*[:=]?\s*(.+?)(?:\.|$)",
        r"(?:patient is|she is|he is)\s+(.+?)(?:\.|$)",
    ])

    # Vitals
    bp = _extract_field(t, [r"(?:blood pressure|BP)\s*(?:is|was|of|:)?\s*(\d+/\d+)"])
    hr = _extract_number(t, [r"(?:heart rate|HR|pulse)\s*(?:is|was|of|:)?\s*(\d+)"])
    rr = _extract_number(t, [r"(?:respiratory rate|RR|resp rate)\s*(?:is|was|of|:)?\s*(\d+)"])
    temp = _extract_number(t, [r"(?:temperature|temp)\s*(?:is|was|of|:)?\s*(\d+\.?\d*)"])
    spo2 = _extract_number(t, [r"(?:SpO2|O2 sat|oxygen sat|sat)\s*(?:is|was|of|:)?\s*(\d+)"])

    hr_i = int(hr) if hr is not None else None
    rr_i = int(rr) if rr is not None else None
    spo2_i = int(spo2) if spo2 is not None else None

    # Background
    allergy_match = _re.findall(r"allerg(?:y|ies|ic)\s+(?:to\s+)?(.+?)(?:\.|,|and|$)", t, _re.IGNORECASE)
    allergies = [a.strip() for a in allergy_match if a.strip()] or []

    med_match = _re.findall(r"(?:medication|med|on)\s+(?:include|:)?\s*(.+?)(?:\.|$)", t, _re.IGNORECASE)
    medications = [m.strip() for m in med_match if m.strip()] or []

    return SBARData(
        patient=PatientInfo(name=name, age=age, mrn=mrn, room=room),
        situation=Situation(
            primary_diagnosis=dx,
            reason_for_admission=reason,
            current_status=status,
        ),
        background=Background(
            relevant_history=None,
            medications=medications,
            allergies=allergies,
            recent_procedures=[],
        ),
        assessment=Assessment(
            vitals=Vitals(bp=bp, hr=hr_i, rr=rr_i, temp=temp, spo2=spo2_i),
            labs_pending=[],
            labs_recent=[],
        ),
        recommendation=Recommendation(
            care_plan=None,
            escalation_triggers=None,
            pending_orders=[],
            next_steps=None,
        ),
    )


def _alerts_from_sbar(sbar: SBARData) -> list[RiskAlert]:
    """Generate risk alerts from extracted vitals — no AI needed."""
    from backend.config import VITALS_THRESHOLDS
    alerts = []
    v = sbar.assessment.vitals

    if v.hr and v.hr > VITALS_THRESHOLDS["hr"]["high"]:
        alerts.append(RiskAlert(severity="HIGH", category="vital",
                                description=f"Heart rate {v.hr} bpm — exceeds threshold of {VITALS_THRESHOLDS['hr']['high']}. Assess for arrhythmia or sepsis."))
    if v.hr and v.hr < VITALS_THRESHOLDS["hr"]["low"]:
        alerts.append(RiskAlert(severity="HIGH", category="vital",
                                description=f"Heart rate {v.hr} bpm — below threshold of {VITALS_THRESHOLDS['hr']['low']}. Assess for bradycardia."))
    if v.spo2 and v.spo2 < VITALS_THRESHOLDS["spo2"]["low"]:
        alerts.append(RiskAlert(severity="HIGH", category="vital",
                                description=f"SpO2 {v.spo2}% — below threshold of {VITALS_THRESHOLDS['spo2']['low']}%. Risk of hypoxemia."))
    if v.bp:
        try:
            sbp = int(v.bp.split("/")[0])
            if sbp < VITALS_THRESHOLDS["sbp"]["low"]:
                alerts.append(RiskAlert(severity="HIGH", category="vital",
                                        description=f"Systolic BP {sbp} mmHg — below {VITALS_THRESHOLDS['sbp']['low']}. Assess for shock."))
            if sbp > VITALS_THRESHOLDS["sbp"]["high"]:
                alerts.append(RiskAlert(severity="MEDIUM", category="vital",
                                        description=f"Systolic BP {sbp} mmHg — above {VITALS_THRESHOLDS['sbp']['high']}. Assess for hypertensive crisis."))
        except (ValueError, IndexError):
            pass
    if v.temp and v.temp > VITALS_THRESHOLDS["temp"]["high"]:
        alerts.append(RiskAlert(severity="MEDIUM", category="vital",
                                description=f"Temperature {v.temp}°C — above {VITALS_THRESHOLDS['temp']['high']}°C. Febrile, assess for infection."))
    if v.rr and v.rr > VITALS_THRESHOLDS["rr"]["high"]:
        alerts.append(RiskAlert(severity="MEDIUM", category="vital",
                                description=f"Respiratory rate {v.rr} — above {VITALS_THRESHOLDS['rr']['high']}. Assess for respiratory distress."))

    if sbar.background.allergies:
        alerts.append(RiskAlert(severity="MEDIUM", category="medication",
                                description=f"Known allergies: {', '.join(sbar.background.allergies)}. Cross-check all active medications."))

    if not alerts:
        alerts.append(RiskAlert(severity="LOW", category="info",
                                description="No threshold violations detected from extracted vitals. Manual review recommended."))
    return alerts


def _rendered_from_real(sbar: SBARData, alerts: list[RiskAlert], outgoing: str, incoming: str, transcript: str) -> str:
    """Build a plain-text handoff report from regex-extracted data + the raw transcript."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    p = sbar.patient
    header = f"""CLINICAL HANDOFF REPORT
Generated: {ts}
Outgoing: {outgoing}  |  Incoming: {incoming}

PATIENT: {p.name or 'Unknown'} | Age: {p.age or '?'} | MRN: {p.mrn or 'N/A'} | Room: {p.room or 'N/A'}
"""

    situation = f"""
── SITUATION ────────────────────────────────────────────────
Dx: {sbar.situation.primary_diagnosis or 'Not identified'}
Reason: {sbar.situation.reason_for_admission or 'Not identified'}
Status: {sbar.situation.current_status or 'Not identified'}
"""

    v = sbar.assessment.vitals
    vitals_str = " | ".join(filter(None, [
        f"BP {v.bp}" if v.bp else None,
        f"HR {v.hr}" if v.hr else None,
        f"RR {v.rr}" if v.rr else None,
        f"Temp {v.temp}°C" if v.temp else None,
        f"SpO2 {v.spo2}%" if v.spo2 else None,
    ])) or "No vitals extracted"

    assessment = f"""
── ASSESSMENT ───────────────────────────────────────────────
Vitals: {vitals_str}
"""

    alert_lines = "\n".join(f"  [{a.severity}] {a.description}" for a in alerts)
    alerts_section = f"""
── RISK ALERTS ──────────────────────────────────────────────
{alert_lines}
"""

    transcript_section = f"""
── RAW TRANSCRIPT ───────────────────────────────────────────
{transcript[:2000]}
"""

    return header + situation + assessment + alerts_section + transcript_section


def _demo_trend_report() -> TrendReport:
    """Rich visual trend data for demo/fallback."""
    return TrendReport(
        patient_mrn="ICU-2024-0447",
        handoffs_analysed=3,
        deterioration_risk="HIGH",
        trajectory_summary="Patient deteriorating over last 24h: worsening hypotension and persistent tachycardia despite fluid resuscitation.",
        vital_trends=[
            VitalTrend(vital_name="MAP (Mean Arterial Pressure)", direction="worsening", interpretation="Progressive hypotension (65 -> 60 -> 58 mmHg) despite Norepinephrine increase."),
            VitalTrend(vital_name="Heart Rate", direction="stable", interpretation="Persistently elevated (110-120 bpm range) consistent with septic shock state."),
            VitalTrend(vital_name="Lactate", direction="worsening", interpretation="Rising (2.1 -> 3.4 -> 4.2 mmol/L) indicating deepening tissue hypoperfusion.")
        ]
    )


class HandoffState(TypedDict):
    audio_chunks: List[bytes]
    outgoing_nurse: str
    incoming_nurse: str
    is_demo: bool
    language: str
    transcript: Optional[str]
    sbar: Optional[SBARData]
    alerts: List[RiskAlert]
    compliance: Optional[ComplianceReport]
    pharma: Optional[PharmaReport]
    trend: Optional[TrendReport]
    educator: Optional[EducatorReport]
    debrief: Optional[DebriefReport]
    billing: Optional[BillingReport]
    literature: Optional[LiteratureReport]
    final_report: Optional[FinalReport]


class HandoffPipeline:
    def __init__(self):
        self.extract = ExtractAgent()
        self.sentinel = SentinelAgent()
        self.bridge = BridgeAgent()
        self.compliance = ComplianceAgent()
        self.pharma = PharmaAgent()
        self.trend = TrendAgent()
        self.educator = EducatorAgent()
        self.debrief = DebriefAgent()
        self.billing = BillingAgent()
        self.literature = LiteratureAgent()

        # Build LangGraph workflow
        workflow = StateGraph(HandoffState)

        workflow.add_node("transcribe", self._transcribe_node)
        workflow.add_node("extract", self._extract_node)
        workflow.add_node("sentinel", self._sentinel_node)
        
        # Parallel agents
        workflow.add_node("compliance", self._compliance_node)
        workflow.add_node("pharma", self._pharma_node)
        workflow.add_node("trend", self._trend_node)
        workflow.add_node("educator", self._educator_node)
        workflow.add_node("debrief", self._debrief_node)
        workflow.add_node("billing", self._billing_node)
        workflow.add_node("literature", self._literature_node)
        
        # Aggregation
        workflow.add_node("bridge", self._bridge_node)

        # Edges
        workflow.add_edge(START, "transcribe")
        workflow.add_edge("transcribe", "extract")
        workflow.add_edge("extract", "sentinel")
        
        # Parallel execution
        workflow.add_edge("sentinel", "compliance")
        workflow.add_edge("sentinel", "pharma")
        workflow.add_edge("sentinel", "trend")
        workflow.add_edge("sentinel", "educator")
        workflow.add_edge("sentinel", "debrief")
        workflow.add_edge("sentinel", "billing")
        workflow.add_edge("sentinel", "literature")
        
        # Fan-in
        workflow.add_edge("compliance", "bridge")
        workflow.add_edge("pharma", "bridge")
        workflow.add_edge("trend", "bridge")
        workflow.add_edge("educator", "bridge")
        workflow.add_edge("debrief", "bridge")
        workflow.add_edge("billing", "bridge")
        workflow.add_edge("literature", "bridge")
        
        workflow.add_edge("bridge", END)

        self.app = workflow.compile()

    # ── Nodes ─────────────────────────────────────────────────────────────────

    async def _transcribe_node(self, state: HandoffState):
        # 1. Check if transcript already provided (e.g. wrapper or demo)
        t = state.get("transcript")
        if t is not None:
            return {"transcript": t}
        
        # 2. Check for demo mode without transcript (should rely on downstream default, but safe to set empty)
        if state.get("is_demo"):
            return {"transcript": DEMO_TRANSCRIPT}

        # 3. Process audio chunks
        chunks = state.get("audio_chunks", [])
        if not chunks:
            return {"transcript": ""}

        language = state.get("language", "en")
        relay = RelayAgent()
        for chunk in chunks:
            await relay.process_audio_chunk(chunk)
        new_transcript = await relay.transcribe_full(language=language)
        return {"transcript": new_transcript}

    async def _extract_node(self, state: HandoffState):
        transcript = state.get("transcript") or ""
        is_demo = state.get("is_demo", False)
        
        # Early exit check for empty/missing transcript in non-demo mode
        if not is_demo and (not transcript or not transcript.strip()):
            # Return empty/error state to flow through
            # In a real graph we might branch here, but linear flow works if downstream handles empty
            return {
                "sbar": SBARData(),
                "alerts": [RiskAlert(severity="LOW", category="missing", description="No transcript captured.")],
                "final_report": FinalReport(
                    sbar=SBARData(),
                    alerts=[],
                    outgoing_nurse=state["outgoing_nurse"],
                    incoming_nurse=state["incoming_nurse"],
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    rendered=_missing_transcript_rendered(state["outgoing_nurse"], state["incoming_nurse"]),
                    is_demo=False
                )
            }

        sbar = SBARData()
        try:
            sbar = await self.extract.extract(transcript)
        except Exception as e:
            print(f"[Graph] Extract failed: {e}")

        # Fallback Logic
        using_real_transcript = transcript and transcript.strip() != DEMO_TRANSCRIPT.strip()
        
        if _sbar_is_empty(sbar):
            if is_demo:
                print("[Graph] Demo fallback")
                return {
                    "sbar": _demo_sbar(), 
                    "alerts": _demo_alerts(),
                    "transcript": DEMO_TRANSCRIPT 
                }
            elif using_real_transcript:
                print("[Graph] Regex fallback")
                sbar = _sbar_from_transcript(transcript)
                alerts = _alerts_from_sbar(sbar)
                return {"sbar": sbar, "alerts": alerts}
            else:
                # Completely failed
                return {
                    "sbar": SBARData(), 
                    "alerts": [RiskAlert(severity="LOW", category="missing", description="No transcript captured.")]
                }
        
        return {"sbar": sbar}

    async def _sentinel_node(self, state: HandoffState):
        sbar = state.get("sbar")
        # If alerts already populated (e.g. via fallback), return existing or merge
        # But usually sentinel adds value. If sbar is empty, return empty.
        if not sbar or _sbar_is_empty(sbar):
            return {"alerts": state.get("alerts", [])}
        
        try:
            alerts = await self.sentinel.check(sbar)
            
            # Calculate Risk Score (Mindblowing Feature)
            try:
                # If ExtractAgent didn't populate it (or we want to ensure it's calculated)
                if not sbar.risk_score or sbar.risk_score.score == 0:
                   sbar.risk_score = self.sentinel.calculate_raw_score(sbar, alerts)
            except Exception as e:
                print(f"[Sentinel] Score calc failed: {e}")

            return {"alerts": alerts, "sbar": sbar}
        except Exception:
            return {"alerts": state.get("alerts", [])}

    async def _compliance_node(self, state: HandoffState):
        sbar = state.get("sbar")
        transcript = state.get("transcript")
        if not sbar or not transcript:
             return {"compliance": ComplianceReport()}
        try:
            res = await self.compliance.audit(sbar, state.get("alerts", []), transcript)
            return {"compliance": res}
        except Exception:
            return {"compliance": ComplianceReport()}

    async def _pharma_node(self, state: HandoffState):
        sbar = state.get("sbar")
        if not sbar:
            return {"pharma": PharmaReport()}
        try:
            res = await self.pharma.analyse(sbar)
            return {"pharma": res}
        except Exception:
            return {"pharma": PharmaReport()}

    async def _trend_node(self, state: HandoffState):
        sbar = state.get("sbar")
        try:
            if state.get("is_demo"):
                return {"trend": _demo_trend_report()}
            
            if not sbar or not sbar.patient:
                return {"trend": TrendReport()}

            history = await get_history_for_trends(sbar.patient.mrn or "", sbar.patient.name or "")
            res = await self.trend.analyse(sbar, history)
            return {"trend": res}
        except Exception:
            return {"trend": TrendReport()}

    async def _educator_node(self, state: HandoffState):
        sbar = state.get("sbar")
        transcript = state.get("transcript")
        if not sbar or not transcript:
             return {"educator": EducatorReport()}
        try:
            res = await self.educator.educate(sbar, transcript)
            return {"educator": res}
        except Exception:
            return {"educator": EducatorReport()}
    
    async def _debrief_node(self, state: HandoffState):
        sbar = state.get("sbar")
        transcript = state.get("transcript")
        if not sbar or not transcript:
            return {"debrief": DebriefReport()}
        try:
            res = await self.debrief.evaluate(sbar, state.get("alerts", []), transcript)
            return {"debrief": res}
        except Exception:
            return {"debrief": DebriefReport()}
            
    async def _billing_node(self, state: HandoffState):
        sbar = state.get("sbar")
        if not sbar:
             return {"billing": BillingReport()}
        try:
            res = await self.billing.analyse(sbar)
            return {"billing": res}
        except Exception:
            return {"billing": BillingReport()}

    async def _literature_node(self, state: HandoffState):
        sbar = state.get("sbar")
        if not sbar:
             return {"literature": LiteratureReport(topic="N/A")}
        try:
            res = await self.literature.fetch_evidence(sbar)
            return {"literature": res}
        except Exception:
            return {"literature": LiteratureReport(topic="N/A")}

    async def _bridge_node(self, state: HandoffState):
        # If final_report was pre-calculated (e.g. error state in extract), keep it
        if state.get("final_report"):
            return {}

        outgoing = state["outgoing_nurse"]
        incoming = state["incoming_nurse"]
        is_demo = state.get("is_demo", False)
        sbar = state.get("sbar") or SBARData()
        alerts = state.get("alerts") or []

        try:
            final = await self.bridge.generate(sbar, alerts, outgoing, incoming)
            # Attach extras
            final.compliance = state.get("compliance")
            final.pharma = state.get("pharma")
            final.trend = state.get("trend")
            final.educator = state.get("educator")
            final.debrief = state.get("debrief")
            final.billing = state.get("billing")
            final.literature = state.get("literature")
        except Exception:
            final = FinalReport(
                sbar=sbar, alerts=alerts, outgoing_nurse=outgoing, incoming_nurse=incoming,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                rendered=_demo_rendered(outgoing, incoming) if is_demo else "",
                is_demo=is_demo,
                compliance=state.get("compliance"),
                pharma=state.get("pharma"),
                trend=state.get("trend"),
                educator=state.get("educator"),
                debrief=state.get("debrief"),
                billing=state.get("billing"),
                literature=state.get("literature")
            )
        
        # Fallback render if bridge failed
        if not final.rendered:
             final.rendered = _demo_rendered(outgoing, incoming) if is_demo else ""

        final.is_demo = is_demo
        return {"final_report": final}

    # ── Entry Points ──────────────────────────────────────────────────────────

    async def run(self, audio_chunks: list, outgoing: str, incoming: str, language: str = "en") -> FinalReport:
        input_state: HandoffState = {
            "audio_chunks": audio_chunks,
            "outgoing_nurse": outgoing,
            "incoming_nurse": incoming,
            "is_demo": False,
            "language": language,
            "transcript": None,
            "sbar": None,
            "alerts": [],
            "final_report": None,
            "compliance": None,
            "pharma": None,
            "trend": None,
            "educator": None,
            "debrief": None,
            "billing": None,
            "literature": None,
        }
        result = await self.app.ainvoke(input_state)
        return result["final_report"]

    async def run_demo(self, outgoing: str, incoming: str) -> FinalReport:
        input_state: HandoffState = {
            "audio_chunks": [],
            "outgoing_nurse": outgoing,
            "incoming_nurse": incoming,
            "is_demo": True,
            "language": "en",
            "transcript": DEMO_TRANSCRIPT,
            "sbar": None,
            "alerts": [],
            "final_report": None,
            "compliance": None,
            "pharma": None,
            "trend": None,
            "educator": None,
            "debrief": None,
            "billing": None,
            "literature": None,
        }
        result = await self.app.ainvoke(input_state)
        return result["final_report"]
    
    async def run_from_transcript(self, transcript: str, outgoing: str, incoming: str) -> FinalReport:
        # For websocket live flow
        input_state: HandoffState = {
            "audio_chunks": [],
            "outgoing_nurse": outgoing,
            "incoming_nurse": incoming,
            "is_demo": False,
            "language": "en",
            "transcript": transcript,
            "sbar": None,
            "alerts": [],
            "final_report": None,
            "compliance": None,
            "pharma": None,
            "trend": None,
            "educator": None,
            "debrief": None,
            "billing": None,
            "literature": None,
        }
        result = await self.app.ainvoke(input_state)
        return result["final_report"]
