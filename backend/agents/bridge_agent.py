"""
Agent 4 — Bridge Agent
Generates a human-readable SBAR handoff report from structured SBAR data
and Sentinel risk alerts using Claude.
"""

import anthropic
from datetime import datetime
from backend.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from backend.models import SBARData, RiskAlert, FinalReport

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


class BridgeAgent:
    async def generate(
        self,
        sbar: SBARData,
        alerts: list[RiskAlert],
        outgoing: str,
        incoming: str,
    ) -> FinalReport:
        """Generate a complete clinical SBAR handoff report via Claude."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prompt = (
            "You are a clinical documentation assistant. "
            "Generate a complete, professional SBAR handoff report from the following structured data. "
            "Flag all risk alerts prominently. Use clinical language. "
            "Format for a bedside tablet display with clear section headings.\n\n"
            f"SBAR DATA:\n{sbar.model_dump_json(indent=2)}\n\n"
            f"RISK ALERTS:\n{[a.model_dump() for a in alerts]}\n\n"
            f"OUTGOING NURSE: {outgoing}\n"
            f"INCOMING NURSE: {incoming}\n"
            f"TIMESTAMP: {timestamp}\n\n"
            "Format the report with these sections:\n"
            "1. PATIENT BANNER (name, MRN, room, age)\n"
            "2. SITUATION\n"
            "3. BACKGROUND\n"
            "4. ASSESSMENT (vitals, labs)\n"
            "5. RECOMMENDATION\n"
            "6. RISK ALERTS (clearly marked HIGH/MEDIUM/LOW)\n"
            "7. HANDOFF DETAILS (nurses, timestamp)\n"
        )

        try:
            response = await _client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2500,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            block = response.content[0]
            rendered = getattr(block, "text", "") or ""
        except Exception as e:
            print(f"[BridgeAgent] Report generation failed: {e}")
            rendered = _fallback_report(sbar, alerts, outgoing, incoming, timestamp)

        return FinalReport(
            sbar=sbar,
            alerts=alerts,
            outgoing_nurse=outgoing,
            incoming_nurse=incoming,
            timestamp=timestamp,
            rendered=rendered,
        )


def _fallback_report(sbar, alerts, outgoing, incoming, timestamp) -> str:
    """Plain-text fallback if Claude call fails."""
    lines = [
        f"=== MEDRELAY HANDOFF REPORT ===",
        f"Timestamp: {timestamp}",
        f"Outgoing: {outgoing}  |  Incoming: {incoming}",
        "",
        f"PATIENT: {sbar.patient.name or 'Unknown'} | MRN: {sbar.patient.mrn or 'N/A'} | Room: {sbar.patient.room or 'N/A'} | Age: {sbar.patient.age or 'N/A'}",
        "",
        "SITUATION:",
        f"  Diagnosis: {sbar.situation.primary_diagnosis or 'Not documented'}",
        f"  Status: {sbar.situation.current_status or 'Not documented'}",
        "",
        "BACKGROUND:",
        f"  Medications: {', '.join(sbar.background.medications) or 'None listed'}",
        f"  Allergies: {', '.join(sbar.background.allergies) or 'None listed'}",
        "",
        "ASSESSMENT:",
        f"  BP: {sbar.assessment.vitals.bp or 'N/A'}  HR: {sbar.assessment.vitals.hr or 'N/A'}  SpO2: {sbar.assessment.vitals.spo2 or 'N/A'}%",
        "",
        "RECOMMENDATION:",
        f"  {sbar.recommendation.escalation_triggers or 'No escalation plan documented'}",
        "",
        "RISK ALERTS:",
    ]
    for a in alerts:
        lines.append(f"  [{a.severity}] {a.description}")
    return "\n".join(lines)
