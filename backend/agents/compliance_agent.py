"""
Agent 5 — Compliance Agent
Audits the handoff against healthcare regulatory standards:
  - Joint Commission NPSG (National Patient Safety Goals)
  - CMS Conditions of Participation
  - Handoff communication best practices (I-PASS / SBAR)

Returns a ComplianceReport with gap analysis and a compliance score.
"""

from backend.models import SBARData, RiskAlert, ComplianceGap, ComplianceReport


# ── Regulatory checklist ──────────────────────────────────────────────────────
# Each tuple: (standard_id, requirement_text, severity, check_function_name)
_CHECKLIST = [
    # --- Patient Identification (NPSG.01.01.01) ---
    ("NPSG.01.01.01", "Use at least two patient identifiers (name + MRN/DOB)",
     "CRITICAL", "_check_patient_identifiers"),

    # --- Medication Reconciliation (NPSG.03.06.01) ---
    ("NPSG.03.06.01", "Document current medications during handoff",
     "CRITICAL", "_check_medication_list"),

    # --- Allergy Documentation ---
    ("NPSG.03.06.02", "Document known allergies and reactions",
     "CRITICAL", "_check_allergy_documentation"),

    # --- Handoff Communication (NPSG.02.05.01) ---
    ("NPSG.02.05.01", "Handoff includes patient's current condition/status",
     "MAJOR", "_check_current_status"),

    # --- Care Plan / Treatment Plan ---
    ("CMS.482.43(d)", "Document an active plan of care",
     "MAJOR", "_check_care_plan"),

    # --- Escalation Criteria ---
    ("NPSG.ESCALATION", "Document escalation triggers and rapid-response criteria",
     "MAJOR", "_check_escalation_plan"),

    # --- Code Status ---
    ("CMS.482.13(a)", "Document code status / advance directives",
     "MAJOR", "_check_code_status"),

    # --- Fall Risk ---
    ("NPSG.09.02.01", "Assess and communicate fall risk",
     "MAJOR", "_check_fall_risk"),

    # --- Infection Control / Isolation ---
    ("NPSG.07.01.01", "Document infection control precautions / isolation status",
     "MINOR", "_check_isolation_status"),

    # --- Vital Signs Documented ---
    ("CMS.VITALS", "Include recent vital signs in handoff",
     "MAJOR", "_check_vitals_present"),

    # --- Primary Diagnosis ---
    ("CMS.482.24(c)", "Document primary diagnosis / reason for admission",
     "MAJOR", "_check_diagnosis"),

    # --- Lab Results ---
    ("CMS.LABS", "Communicate pending or recent lab results",
     "MINOR", "_check_labs"),

    # --- Room / Location ---
    ("FACILITY.LOC", "Document patient location (room/bed)",
     "MINOR", "_check_location"),

    # --- Pending Orders ---
    ("CMS.482.23(c)", "Communicate pending orders or follow-ups",
     "MINOR", "_check_pending_orders"),
]


class ComplianceAgent:
    """Audits SBAR data + transcript against regulatory standards."""

    async def audit(
        self,
        sbar: SBARData,
        alerts: list[RiskAlert],
        transcript: str = "",
    ) -> ComplianceReport:
        gaps: list[ComplianceGap] = []
        standards_met = 0

        for std_id, requirement, severity, check_fn in _CHECKLIST:
            met = getattr(self, check_fn)(sbar, transcript)
            gap = ComplianceGap(
                standard=std_id,
                requirement=requirement,
                severity=severity,
                met=met,
                recommendation=self._recommendation(std_id, met),
            )
            gaps.append(gap)
            if met:
                standards_met += 1

        total = len(_CHECKLIST)
        score = round((standards_met / total) * 100, 1) if total else 0

        return ComplianceReport(
            score=score,
            gaps=gaps,
            standards_checked=total,
            standards_met=standards_met,
        )

    # ── Individual checks ─────────────────────────────────────────────────────

    def _check_patient_identifiers(self, sbar: SBARData, transcript: str) -> bool:
        """Need at least 2 of: name, MRN, age/DOB."""
        identifiers = sum([
            bool(sbar.patient.name),
            bool(sbar.patient.mrn),
            bool(sbar.patient.age),
        ])
        return identifiers >= 2

    def _check_medication_list(self, sbar: SBARData, transcript: str) -> bool:
        return len(sbar.background.medications) > 0

    def _check_allergy_documentation(self, sbar: SBARData, transcript: str) -> bool:
        # Allergies list populated OR transcript explicitly says "no known allergies"
        if sbar.background.allergies:
            return True
        t = transcript.lower()
        return any(phrase in t for phrase in [
            "no known allergies", "nka", "nkda", "no allergies",
        ])

    def _check_current_status(self, sbar: SBARData, transcript: str) -> bool:
        return bool(sbar.situation.current_status)

    def _check_care_plan(self, sbar: SBARData, transcript: str) -> bool:
        return bool(sbar.recommendation.care_plan)

    def _check_escalation_plan(self, sbar: SBARData, transcript: str) -> bool:
        return bool(sbar.recommendation.escalation_triggers)

    def _check_code_status(self, sbar: SBARData, transcript: str) -> bool:
        """Check if code status / DNR / advance directive is mentioned."""
        t = transcript.lower()
        return any(kw in t for kw in [
            "full code", "dnr", "dni", "do not resuscitate",
            "do not intubate", "comfort care", "comfort measures",
            "advance directive", "code status", "goals of care",
            "healthcare proxy", "power of attorney",
        ])

    def _check_fall_risk(self, sbar: SBARData, transcript: str) -> bool:
        t = transcript.lower()
        return any(kw in t for kw in [
            "fall risk", "fall precaution", "fall prevention",
            "unsteady gait", "morse fall", "bed alarm",
            "call light within reach", "restraint",
        ])

    def _check_isolation_status(self, sbar: SBARData, transcript: str) -> bool:
        t = transcript.lower()
        return any(kw in t for kw in [
            "isolation", "contact precautions", "droplet precautions",
            "airborne precautions", "ppe required", "mrsa", "c diff",
            "c. diff", "vre", "covid", "tb precautions",
            "no isolation", "standard precautions",
        ])

    def _check_vitals_present(self, sbar: SBARData, transcript: str) -> bool:
        v = sbar.assessment.vitals
        return any([v.bp, v.hr, v.rr, v.temp, v.spo2])

    def _check_diagnosis(self, sbar: SBARData, transcript: str) -> bool:
        return bool(sbar.situation.primary_diagnosis)

    def _check_labs(self, sbar: SBARData, transcript: str) -> bool:
        return bool(sbar.assessment.labs_pending or sbar.assessment.labs_recent)

    def _check_location(self, sbar: SBARData, transcript: str) -> bool:
        return bool(sbar.patient.room)

    def _check_pending_orders(self, sbar: SBARData, transcript: str) -> bool:
        return bool(sbar.recommendation.pending_orders)

    # ── Recommendations per standard ──────────────────────────────────────────

    @staticmethod
    def _recommendation(std_id: str, met: bool) -> str:
        if met:
            return ""
        _recs = {
            "NPSG.01.01.01": "Add patient name AND at least one more identifier (MRN or DOB) to the handoff.",
            "NPSG.03.06.01": "List all current medications including dose, route, and frequency.",
            "NPSG.03.06.02": "Document allergies explicitly — if none, state 'No Known Drug Allergies (NKDA)'.",
            "NPSG.02.05.01": "Describe the patient's current clinical status and any changes this shift.",
            "CMS.482.43(d)": "Include the active care plan: what is being done and what to continue.",
            "NPSG.ESCALATION": "Define specific escalation triggers (e.g., MAP < 65, SpO2 < 88%) and when to call rapid response.",
            "CMS.482.13(a)": "Document code status (Full Code / DNR / DNI) or reference advance directives.",
            "NPSG.09.02.01": "Assess and communicate fall risk level and active fall prevention measures.",
            "NPSG.07.01.01": "State isolation status and required precautions, or confirm 'Standard precautions only'.",
            "CMS.VITALS": "Include the most recent set of vital signs in the handoff.",
            "CMS.482.24(c)": "State the primary diagnosis or reason for admission clearly.",
            "CMS.LABS": "Mention recent lab results and any pending lab orders.",
            "FACILITY.LOC": "Specify patient room and bed number.",
            "CMS.482.23(c)": "List pending orders, scheduled tests, or expected follow-ups.",
        }
        return _recs.get(std_id, "Review and address this compliance gap.")
