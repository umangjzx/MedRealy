"""
MedRelay — Agent Orchestration Pipeline
Runs the 4-agent handoff pipeline sequentially:
  Relay -> Extract -> Sentinel -> Bridge
Falls back to rich hardcoded demo data when Claude/OpenAI API keys are unavailable.
"""

import asyncio
import time
import traceback
from datetime import datetime
from typing import Dict, TypedDict, List, Optional
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
    # Per-node wall-clock timings (ms) — written by each node
    node_timings: Dict[str, float]


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

        # ── LangGraph workflow ─────────────────────────────────────────────
        # Topology:
        #   transcribe -> extract --(has_report?)--> bridge -> END
        #                         \--> sentinel -> parallel_agents -> bridge
        #
        # parallel_agents runs all 7 specialists concurrently via asyncio.gather
        # so their combined latency == the slowest single agent (not their sum).
        workflow = StateGraph(HandoffState)

        workflow.add_node("transcribe",      self._transcribe_node)
        workflow.add_node("extract",         self._extract_node)
        workflow.add_node("sentinel",        self._sentinel_node)
        workflow.add_node("parallel_agents", self._parallel_agents_node)
        workflow.add_node("bridge",          self._bridge_node)

        workflow.add_edge(START, "transcribe")
        workflow.add_edge("transcribe", "extract")

        # Conditional: if extract already produced a final_report (e.g. empty
        # transcript), skip all agents and go straight to bridge for assembly.
        workflow.add_conditional_edges(
            "extract",
            lambda s: "bridge" if s.get("final_report") else "sentinel",
            {"sentinel": "sentinel", "bridge": "bridge"},
        )

        workflow.add_edge("sentinel",        "parallel_agents")
        workflow.add_edge("parallel_agents", "bridge")
        workflow.add_edge("bridge",          END)

        self.app = workflow.compile()

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_state(
        outgoing: str,
        incoming: str,
        *,
        audio_chunks: list | None = None,
        transcript: str | None = None,
        is_demo: bool = False,
        language: str = "en",
    ) -> HandoffState:
        """Factory: build a fully-initialised HandoffState without repeating defaults."""
        return HandoffState(
            audio_chunks=audio_chunks or [],
            outgoing_nurse=outgoing,
            incoming_nurse=incoming,
            is_demo=is_demo,
            language=language,
            transcript=transcript,
            sbar=None,
            alerts=[],
            compliance=None,
            pharma=None,
            trend=None,
            educator=None,
            debrief=None,
            billing=None,
            literature=None,
            final_report=None,
            node_timings={},
        )

    @staticmethod
    def _tick() -> float:
        """Return current perf-counter value."""
        return time.perf_counter()

    @staticmethod
    def _tock(t0: float) -> float:
        """Return elapsed milliseconds since t0."""
        return round((time.perf_counter() - t0) * 1000, 1)

    # ── Nodes ─────────────────────────────────────────────────────────────────

    async def _transcribe_node(self, state: HandoffState):
        t0 = self._tick()
        # 1. Transcript already provided (run_from_transcript or demo injection)
        txt = state.get("transcript")
        if txt is not None:
            return {"transcript": txt, "node_timings": {**state.get("node_timings", {}), "transcribe": self._tock(t0)}}

        # 2. Demo mode: use the canonical demo transcript
        if state.get("is_demo"):
            return {"transcript": DEMO_TRANSCRIPT, "node_timings": {**state.get("node_timings", {}), "transcribe": self._tock(t0)}}

        # 3. Transcribe from accumulated audio chunks
        chunks = state.get("audio_chunks", [])
        if not chunks:
            return {"transcript": "", "node_timings": {**state.get("node_timings", {}), "transcribe": self._tock(t0)}}

        language = state.get("language", "en")
        relay = RelayAgent()
        for chunk in chunks:
            await relay.process_audio_chunk(chunk)
        new_transcript = await relay.transcribe_full(language=language)
        ms = self._tock(t0)
        print(f"[Pipeline] transcribe completed in {ms}ms ({len(new_transcript)} chars)")
        return {"transcript": new_transcript, "node_timings": {**state.get("node_timings", {}), "transcribe": ms}}

    async def _extract_node(self, state: HandoffState):
        t0 = self._tick()
        timings = state.get("node_timings", {})
        transcript = state.get("transcript") or ""
        is_demo = state.get("is_demo", False)

        # Short-circuit: no transcript captured in live mode  →  set final_report
        # so the conditional edge after this node routes straight to bridge.
        if not is_demo and not transcript.strip():
            print("[Pipeline] extract: no transcript — skipping agents")
            return {
                "sbar": SBARData(),
                "alerts": [RiskAlert(severity="LOW", category="missing", description="No transcript captured.")],
                "node_timings": {**timings, "extract": self._tock(t0)},
                "final_report": FinalReport(
                    sbar=SBARData(),
                    alerts=[],
                    outgoing_nurse=state["outgoing_nurse"],
                    incoming_nurse=state["incoming_nurse"],
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    rendered=_missing_transcript_rendered(state["outgoing_nurse"], state["incoming_nurse"]),
                    is_demo=False,
                ),
            }

        sbar = SBARData()
        try:
            sbar = await self.extract.extract(transcript)
        except Exception as e:
            print(f"[Pipeline] extract agent error: {e}")

        using_real_transcript = bool(transcript.strip()) and transcript.strip() != DEMO_TRANSCRIPT.strip()

        if _sbar_is_empty(sbar):
            if is_demo:
                print("[Pipeline] extract: demo SBAR fallback")
                ms = self._tock(t0)
                return {
                    "sbar": _demo_sbar(),
                    "alerts": _demo_alerts(),
                    "transcript": DEMO_TRANSCRIPT,
                    "node_timings": {**timings, "extract": ms},
                }
            if using_real_transcript:
                print("[Pipeline] extract: regex SBAR fallback")
                sbar = _sbar_from_transcript(transcript)
                alerts = _alerts_from_sbar(sbar)
                ms = self._tock(t0)
                return {"sbar": sbar, "alerts": alerts, "node_timings": {**timings, "extract": ms}}
            # Nothing to work with
            ms = self._tock(t0)
            return {
                "sbar": SBARData(),
                "alerts": [RiskAlert(severity="LOW", category="missing", description="No transcript captured.")],
                "node_timings": {**timings, "extract": ms},
            }

        ms = self._tock(t0)
        print(f"[Pipeline] extract completed in {ms}ms")
        return {"sbar": sbar, "node_timings": {**timings, "extract": ms}}

    async def _sentinel_node(self, state: HandoffState):
        t0 = self._tick()
        timings = state.get("node_timings", {})
        sbar = state.get("sbar")

        if not sbar or _sbar_is_empty(sbar):
            return {"alerts": state.get("alerts", []), "node_timings": {**timings, "sentinel": self._tock(t0)}}

        try:
            alerts = await self.sentinel.check(sbar)
            try:
                if not sbar.risk_score or sbar.risk_score.score == 0:
                    sbar.risk_score = self.sentinel.calculate_raw_score(sbar, alerts)
            except Exception as e:
                print(f"[Pipeline] sentinel risk-score calc failed: {e}")
            ms = self._tock(t0)
            print(f"[Pipeline] sentinel completed in {ms}ms ({len(alerts)} alerts)")
            return {"alerts": alerts, "sbar": sbar, "node_timings": {**timings, "sentinel": ms}}
        except Exception as e:
            print(f"[Pipeline] sentinel agent error: {e}")
            return {"alerts": state.get("alerts", []), "node_timings": {**timings, "sentinel": self._tock(t0)}}

    async def _parallel_agents_node(self, state: HandoffState):
        """
        Run all 7 specialist agents concurrently via asyncio.gather.
        Combined latency = slowest single agent (not the sum of all).
        Each agent is individually error-isolated; a failure returns an empty report.
        """
        t0 = self._tick()
        timings = state.get("node_timings", {})
        sbar     = state.get("sbar")
        transcript = state.get("transcript", "")
        alerts   = state.get("alerts", [])
        is_demo  = state.get("is_demo", False)

        async def _run(name: str, coro):
            try:
                return await coro
            except Exception as e:
                print(f"[Pipeline] parallel/{name} failed: {e}")
                return None

        # ── Coroutines for each specialist ────────────────────────────────────
        async def run_compliance():
            if not sbar or not transcript:
                return ComplianceReport()
            return await self.compliance.audit(sbar, alerts, transcript) or ComplianceReport()

        async def run_pharma():
            if not sbar:
                return PharmaReport()
            return await self.pharma.analyse(sbar) or PharmaReport()

        async def run_trend():
            if is_demo:
                return _demo_trend_report()
            if not sbar or not sbar.patient:
                return TrendReport()
            history = await get_history_for_trends(sbar.patient.mrn or "", sbar.patient.name or "")
            return await self.trend.analyse(sbar, history) or TrendReport()

        async def run_educator():
            if not sbar or not transcript:
                return EducatorReport()
            return await self.educator.educate(sbar, transcript) or EducatorReport()

        async def run_debrief():
            if not sbar or not transcript:
                return DebriefReport()
            return await self.debrief.evaluate(sbar, alerts, transcript) or DebriefReport()

        async def run_billing():
            if not sbar:
                return BillingReport()
            return await self.billing.analyse(sbar) or BillingReport()

        async def run_literature():
            if not sbar:
                return LiteratureReport(topic="N/A")
            return await self.literature.fetch_evidence(sbar) or LiteratureReport(topic="N/A")

        # ── True concurrent execution ─────────────────────────────────────────
        results = await asyncio.gather(
            _run("compliance",  run_compliance()),
            _run("pharma",      run_pharma()),
            _run("trend",       run_trend()),
            _run("educator",    run_educator()),
            _run("debrief",     run_debrief()),
            _run("billing",     run_billing()),
            _run("literature",  run_literature()),
        )
        compliance, pharma, trend, educator, debrief, billing, literature = results

        ms = self._tock(t0)
        print(f"[Pipeline] parallel_agents completed in {ms}ms (7 specialists)")
        return {
            "compliance":  compliance  or ComplianceReport(),
            "pharma":      pharma      or PharmaReport(),
            "trend":       trend       or TrendReport(),
            "educator":    educator    or EducatorReport(),
            "debrief":     debrief     or DebriefReport(),
            "billing":     billing     or BillingReport(),
            "literature":  literature  or LiteratureReport(topic="N/A"),
            "node_timings": {**timings, "parallel_agents": ms},
        }

    async def _bridge_node(self, state: HandoffState):
        t0 = self._tick()
        timings = state.get("node_timings", {})

        # Pre-built final_report (empty transcript short-circuit from extract node)
        if state.get("final_report"):
            ms = self._tock(t0)
            return {"node_timings": {**timings, "bridge": ms}}

        outgoing = state["outgoing_nurse"]
        incoming = state["incoming_nurse"]
        is_demo  = state.get("is_demo", False)
        sbar     = state.get("sbar") or SBARData()
        alerts   = state.get("alerts") or []

        def _attach_specialists(report: FinalReport) -> FinalReport:
            report.compliance = state.get("compliance")
            report.pharma     = state.get("pharma")
            report.trend      = state.get("trend")
            report.educator   = state.get("educator")
            report.debrief    = state.get("debrief")
            report.billing    = state.get("billing")
            report.literature = state.get("literature")
            return report

        try:
            final = await self.bridge.generate(sbar, alerts, outgoing, incoming)
            final = _attach_specialists(final)
        except Exception as e:
            print(f"[Pipeline] bridge agent error: {e}")
            final = _attach_specialists(FinalReport(
                sbar=sbar,
                alerts=alerts,
                outgoing_nurse=outgoing,
                incoming_nurse=incoming,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                rendered=_demo_rendered(outgoing, incoming) if is_demo else "",
                is_demo=is_demo,
            ))

        if not final.rendered:
            final.rendered = _demo_rendered(outgoing, incoming) if is_demo else ""
        final.is_demo = is_demo

        ms = self._tock(t0)
        total_ms = round(sum(timings.values()) + ms, 1)
        print(f"[Pipeline] bridge completed in {ms}ms | total pipeline: {total_ms}ms")
        return {"final_report": final, "node_timings": {**timings, "bridge": ms}}

    # ── Entry Points ──────────────────────────────────────────────────────────

    async def run(
        self, audio_chunks: list, outgoing: str, incoming: str, language: str = "en"
    ) -> FinalReport:
        """Run the full pipeline from raw audio chunks."""
        state = self._make_state(outgoing, incoming, audio_chunks=audio_chunks, language=language)
        result = await self.app.ainvoke(state)
        return result["final_report"]

    async def run_demo(self, outgoing: str, incoming: str) -> FinalReport:
        """Run the pipeline with the canonical demo transcript."""
        state = self._make_state(outgoing, incoming, transcript=DEMO_TRANSCRIPT, is_demo=True)
        result = await self.app.ainvoke(state)
        return result["final_report"]

    async def run_from_transcript(
        self, transcript: str, outgoing: str, incoming: str
    ) -> FinalReport:
        """Run the pipeline from a pre-built transcript (WebSocket live flow)."""
        state = self._make_state(outgoing, incoming, transcript=transcript)
        result = await self.app.ainvoke(state)
        return result["final_report"]
