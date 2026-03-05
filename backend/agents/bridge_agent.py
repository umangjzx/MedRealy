"""
Agent 4 — Bridge Agent
Generates a human-readable SBAR handoff report from structured SBAR data
and Sentinel risk alerts using a deterministic template renderer.
No external API key required.
"""

from datetime import datetime
from backend.models import SBARData, RiskAlert, FinalReport


class BridgeAgent:
    async def generate(
        self,
        sbar: SBARData,
        alerts: list[RiskAlert],
        outgoing: str,
        incoming: str,
    ) -> FinalReport:
        """Generate a complete clinical SBAR handoff report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rendered = _render_report(sbar, alerts, outgoing, incoming, timestamp)
        return FinalReport(
            sbar=sbar,
            alerts=alerts,
            outgoing_nurse=outgoing,
            incoming_nurse=incoming,
            timestamp=timestamp,
            rendered=rendered,
        )


def _render_report(
    sbar: SBARData,
    alerts: list[RiskAlert],
    outgoing: str,
    incoming: str,
    timestamp: str,
) -> str:
    """Deterministic SBAR report renderer — no external API needed."""
    v = sbar.assessment.vitals
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║            MEDRELAY HANDOFF REPORT                      ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        "── PATIENT BANNER ───────────────────────────────────────────",
        f"  Name   : {sbar.patient.name or 'Unknown'}",
        f"  MRN    : {sbar.patient.mrn or 'N/A'}",
        f"  Room   : {sbar.patient.room or 'N/A'}",
        f"  Age    : {sbar.patient.age or 'N/A'}",
        "",
        "── SITUATION ────────────────────────────────────────────────",
        f"  Diagnosis : {sbar.situation.primary_diagnosis or 'Not documented'}",
        f"  Admission : {sbar.situation.reason_for_admission or 'Not documented'}",
        f"  Status    : {sbar.situation.current_status or 'Not documented'}",
        "",
        "── BACKGROUND ───────────────────────────────────────────────",
        f"  History     : {sbar.background.relevant_history or 'Not documented'}",
        f"  Medications : {', '.join(sbar.background.medications) if sbar.background.medications else 'None listed'}",
        f"  Allergies   : {', '.join(sbar.background.allergies) if sbar.background.allergies else 'NKDA'}",
        f"  Procedures  : {', '.join(sbar.background.recent_procedures) if sbar.background.recent_procedures else 'None'}",
        "",
        "── ASSESSMENT ───────────────────────────────────────────────",
        f"  BP   : {v.bp or 'N/A'}",
        f"  HR   : {v.hr or 'N/A'} bpm",
        f"  RR   : {v.rr or 'N/A'} /min",
        f"  Temp : {v.temp or 'N/A'} °C",
        f"  SpO2 : {v.spo2 or 'N/A'}%",
        f"  Pain : {sbar.assessment.pain_level}/10" if sbar.assessment.pain_level else "  Pain : N/A",
        f"  Neuro: {sbar.assessment.neurological_status or 'Not documented'}",
    ]

    if sbar.assessment.labs_recent:
        lines.append(f"  Labs (recent) : {', '.join(sbar.assessment.labs_recent)}")
    if sbar.assessment.labs_pending:
        lines.append(f"  Labs (pending): {', '.join(sbar.assessment.labs_pending)}")

    lines += [
        "",
        "── RECOMMENDATION ───────────────────────────────────────────",
        f"  Care Plan  : {sbar.recommendation.care_plan or 'Not documented'}",
        f"  Escalation : {sbar.recommendation.escalation_triggers or 'Not defined'}",
        f"  Next Steps : {sbar.recommendation.next_steps or 'Not documented'}",
    ]

    if sbar.recommendation.pending_orders:
        lines.append(f"  Pending Orders: {', '.join(sbar.recommendation.pending_orders)}")

    if sbar.recommendation.action_items:
        lines.append("  Action Items :")
        for item in sbar.recommendation.action_items:
            lines.append(
                f"    [{item.priority}] {item.task}"
                f" — Due: {item.due_time or 'ASAP'} → {item.assignee}"
            )

    # ── Risk Alerts ───────────────────────────────────────────────────────────
    lines += ["", "── RISK ALERTS ──────────────────────────────────────────────"]
    if alerts:
        for a in alerts:
            marker = "⚠" if a.severity == "HIGH" else "●"
            lines.append(f"  {marker} [{a.severity}] {a.description}")
    else:
        lines.append("  No active risk alerts")

    # ── Risk Score ────────────────────────────────────────────────────────────
    if sbar.risk_score and sbar.risk_score.score:
        lines += [
            "",
            f"  Risk Score : {sbar.risk_score.score}/100  ({sbar.risk_score.risk_level})",
        ]
        if sbar.risk_score.contributing_factors:
            lines.append(f"  Factors    : {', '.join(sbar.risk_score.contributing_factors)}")

    lines += [
        "",
        "── HANDOFF DETAILS ──────────────────────────────────────────",
        f"  Outgoing Nurse : {outgoing}",
        f"  Incoming Nurse : {incoming}",
        f"  Timestamp      : {timestamp}",
        "",
        "════════════════════════════════════════════════════════════",
    ]

    return "\n".join(lines)

