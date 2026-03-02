"""
MedRelay — Agent Orchestration Pipeline
Runs the 4-agent handoff pipeline sequentially:
  Relay -> Extract -> Sentinel -> Bridge
Falls back to rich hardcoded demo data when Claude/OpenAI API keys are unavailable.
"""

import traceback
from datetime import datetime
from backend.agents.relay_agent import RelayAgent
from backend.agents.extract_agent import ExtractAgent
from backend.agents.sentinel_agent import SentinelAgent
from backend.agents.bridge_agent import BridgeAgent
from backend.constants import DEMO_TRANSCRIPT
from backend.models import (
    FinalReport, SBARData, PatientInfo, Situation, Background,
    Assessment, Recommendation, Vitals, RiskAlert,
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


class HandoffPipeline:
    def __init__(self):
        self.extract = ExtractAgent()
        self.sentinel = SentinelAgent()
        self.bridge = BridgeAgent()

    async def run(self, audio_chunks: list, outgoing: str, incoming: str) -> FinalReport:
        """Full pipeline: transcribe audio -> extract SBAR -> check risks -> generate report."""
        # Create a fresh RelayAgent per-run to avoid buffer leaks between sessions
        relay = RelayAgent()
        for chunk in audio_chunks:
            await relay.process_audio_chunk(chunk)
        transcript = await relay.transcribe_full()
        return await self._run_from_transcript(transcript, outgoing, incoming)

    async def run_demo(self, outgoing: str, incoming: str) -> FinalReport:
        """Demo pipeline: skip audio capture, use the pre-written demo transcript."""
        return await self._run_from_transcript(DEMO_TRANSCRIPT, outgoing, incoming, is_demo=True)

    async def run_from_transcript(self, transcript: str, outgoing: str, incoming: str) -> FinalReport:
        """Public API: run pipeline from an already-transcribed text (used by WebSocket live flow)."""
        return await self._run_from_transcript(transcript, outgoing, incoming)

    async def _run_from_transcript(
        self, transcript: str, outgoing: str, incoming: str, is_demo: bool = False
    ) -> FinalReport:
        """Shared logic: Extract -> Sentinel -> Bridge. Falls back to demo data if AI unavailable."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Guardrail: in real mode, never auto-inject demo content when transcript is missing.
        if not is_demo:
            text = (transcript or "").strip()
            if not text or text == DEMO_TRANSCRIPT.strip():
                return FinalReport(
                    sbar=SBARData(),
                    alerts=[
                        RiskAlert(
                            severity="LOW",
                            category="missing",
                            description="No transcript captured from live audio. Clinical handoff content unavailable.",
                        )
                    ],
                    outgoing_nurse=outgoing,
                    incoming_nurse=incoming,
                    timestamp=timestamp,
                    rendered=_missing_transcript_rendered(outgoing, incoming),
                    is_demo=False,
                )

        try:
            sbar = await self.extract.extract(transcript)
        except Exception as e:
            print(f"[Pipeline] Extract failed: {traceback.format_exc()}")
            sbar = SBARData()

        # If ExtractAgent returned empty data (Claude + HF both failed), fall back
        # but still use the REAL transcript if we have one
        using_real_transcript = transcript and transcript.strip() != DEMO_TRANSCRIPT.strip()

        if _sbar_is_empty(sbar):
            if is_demo:
                print("[Pipeline] Demo mode active — using hardcoded demo data")
                sbar = _demo_sbar()
                alerts = _demo_alerts()
                rendered = _demo_rendered(outgoing, incoming)
            elif using_real_transcript:
                # Last resort: regex-based extraction from raw transcript
                print(f"[Pipeline] AI extraction failed — using regex fallback on real transcript ({len(transcript)} chars)")
                sbar = _sbar_from_transcript(transcript)
                alerts = _alerts_from_sbar(sbar)
                rendered = _rendered_from_real(sbar, alerts, outgoing, incoming, transcript)
            else:
                print("[Pipeline] No transcript available in real mode — returning non-demo missing-transcript report")
                sbar = SBARData()
                alerts = [
                    RiskAlert(
                        severity="LOW",
                        category="missing",
                        description="No transcript captured from live audio. Clinical handoff content unavailable.",
                    )
                ]
                rendered = _missing_transcript_rendered(outgoing, incoming)
            return FinalReport(
                sbar=sbar,
                alerts=alerts,
                outgoing_nurse=outgoing,
                incoming_nurse=incoming,
                timestamp=timestamp,
                rendered=rendered,
                is_demo=is_demo,
            )

        try:
            alerts = await self.sentinel.check(sbar)
        except Exception as e:
            print(f"[Pipeline] Sentinel failed: {traceback.format_exc()}")
            alerts = _demo_alerts() if is_demo else []

        try:
            final_report = await self.bridge.generate(sbar, alerts, outgoing, incoming)
        except Exception as e:
            print(f"[Pipeline] Bridge failed: {traceback.format_exc()}")
            final_report = FinalReport(
                sbar=sbar,
                alerts=alerts,
                outgoing_nurse=outgoing,
                incoming_nurse=incoming,
                timestamp=timestamp,
                rendered=_demo_rendered(outgoing, incoming) if is_demo else "",
                is_demo=is_demo,
            )

        # If bridge also failed to produce rendered report, fill fallback
        if not final_report.rendered:
            final_report.rendered = _demo_rendered(outgoing, incoming) if is_demo else ""

        final_report.is_demo = is_demo
        return final_report
