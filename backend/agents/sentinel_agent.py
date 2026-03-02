"""
Agent 3 — Sentinel Agent
Flags clinical risks from SBAR data:
  - Vital sign threshold violations (with borderline warnings)
  - Allergy / medication cross-conflicts (via fda_client)
  - Missing critical documentation fields
"""

from backend.models import SBARData, RiskAlert
from backend.config import VITALS_THRESHOLDS
from backend.fda_client import check_allergy_drug_conflict

# Borderline margin: flag MEDIUM if within this % of a threshold
_BORDERLINE_PCT = 0.10


class SentinelAgent:
    async def check(self, sbar: SBARData) -> list[RiskAlert]:
        """Run all risk checks and return a prioritised list of RiskAlerts."""
        alerts: list[RiskAlert] = []

        alerts.extend(self._check_vitals(sbar))
        alerts.extend(await self._check_medications(sbar))
        alerts.extend(self._check_missing_fields(sbar))

        # Sort: HIGH first, then MEDIUM, then LOW
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 3))
        return alerts

    # ------------------------------------------------------------------
    # Vital sign threshold checks (with borderline warnings)
    # ------------------------------------------------------------------

    def _check_vitals(self, sbar: SBARData) -> list[RiskAlert]:
        alerts = []
        v = sbar.assessment.vitals
        t = VITALS_THRESHOLDS

        if v.hr is not None:
            if v.hr < t["hr"]["low"]:
                alerts.append(RiskAlert(severity="HIGH", description=f"Bradycardia — HR {v.hr} bpm (threshold < {t['hr']['low']})", category="vital"))
            elif v.hr > t["hr"]["high"]:
                alerts.append(RiskAlert(severity="HIGH", description=f"Tachycardia — HR {v.hr} bpm (threshold > {t['hr']['high']})", category="vital"))
            elif v.hr >= t["hr"]["high"] * (1 - _BORDERLINE_PCT):
                alerts.append(RiskAlert(severity="MEDIUM", description=f"Heart rate borderline elevated — HR {v.hr} bpm (near threshold {t['hr']['high']})", category="vital"))
            elif v.hr <= t["hr"]["low"] * (1 + _BORDERLINE_PCT):
                alerts.append(RiskAlert(severity="MEDIUM", description=f"Heart rate borderline low — HR {v.hr} bpm (near threshold {t['hr']['low']})", category="vital"))

        if v.bp:
            try:
                # Strip units if present (e.g., "88/54 mmHg" -> "88/54")
                bp_clean = v.bp.split()[0] if " " in v.bp else v.bp
                sbp = int(bp_clean.split("/")[0])
                if sbp < t["sbp"]["low"]:
                    alerts.append(RiskAlert(severity="HIGH", description=f"Hypotension — SBP {sbp} mmHg (threshold < {t['sbp']['low']})", category="vital"))
                elif sbp > t["sbp"]["high"]:
                    alerts.append(RiskAlert(severity="HIGH", description=f"Hypertension — SBP {sbp} mmHg (threshold > {t['sbp']['high']})", category="vital"))
                elif sbp <= t["sbp"]["low"] * (1 + _BORDERLINE_PCT):
                    alerts.append(RiskAlert(severity="MEDIUM", description=f"Blood pressure borderline low — SBP {sbp} mmHg (near threshold {t['sbp']['low']})", category="vital"))
            except (ValueError, IndexError):
                pass

        if v.spo2 is not None:
            if v.spo2 < t["spo2"]["low"]:
                alerts.append(RiskAlert(severity="HIGH", description=f"Hypoxia — SpO2 {v.spo2}% (threshold < {t['spo2']['low']}%)", category="vital"))
            elif v.spo2 <= t["spo2"]["low"] + 2:
                # SpO2 92-94 is borderline
                alerts.append(RiskAlert(severity="MEDIUM", description=f"SpO2 borderline low — {v.spo2}% (near threshold {t['spo2']['low']}%)", category="vital"))

        if v.rr is not None:
            if v.rr < t["rr"]["low"]:
                alerts.append(RiskAlert(severity="HIGH", description=f"Bradypnoea — RR {v.rr} /min (threshold < {t['rr']['low']})", category="vital"))
            elif v.rr > t["rr"]["high"]:
                alerts.append(RiskAlert(severity="HIGH", description=f"Tachypnoea — RR {v.rr} /min (threshold > {t['rr']['high']})", category="vital"))

        if v.temp is not None:
            if v.temp < t["temp"]["low"]:
                alerts.append(RiskAlert(severity="MEDIUM", description=f"Hypothermia — Temp {v.temp}°C (threshold < {t['temp']['low']}°C)", category="vital"))
            elif v.temp > t["temp"]["high"]:
                alerts.append(RiskAlert(severity="HIGH", description=f"Fever — Temp {v.temp}°C (threshold > {t['temp']['high']}°C)", category="vital"))

        return alerts

    # ------------------------------------------------------------------
    # Medication / allergy conflict checks
    # ------------------------------------------------------------------

    async def _check_medications(self, sbar: SBARData) -> list[RiskAlert]:
        alerts = []
        meds = sbar.background.medications
        allergies = sbar.background.allergies

        if not meds or not allergies:
            return alerts

        conflicts = await check_allergy_drug_conflict(meds, allergies)
        for c in conflicts:
            alerts.append(RiskAlert(
                severity="HIGH",
                description=(
                    f"ALLERGY CONFLICT: Patient allergic to {c['allergy']} "
                    f"but is receiving {c['medication']}"
                ),
                category="medication",
            ))

        return alerts

    # ------------------------------------------------------------------
    # Missing critical documentation fields
    # ------------------------------------------------------------------

    def _check_missing_fields(self, sbar: SBARData) -> list[RiskAlert]:
        alerts = []

        if not sbar.patient.name:
            alerts.append(RiskAlert(severity="MEDIUM", description="Patient name not documented in handoff", category="missing"))
        if not sbar.patient.room:
            alerts.append(RiskAlert(severity="LOW", description="Patient room/bed not documented", category="missing"))
        if not sbar.patient.mrn:
            alerts.append(RiskAlert(severity="LOW", description="Patient MRN not documented", category="missing"))
        if not sbar.recommendation.escalation_triggers:
            alerts.append(RiskAlert(severity="MEDIUM", description="No escalation plan documented — add MAP/SpO2 thresholds and rapid-response criteria", category="missing"))
        if not sbar.recommendation.care_plan:
            alerts.append(RiskAlert(severity="MEDIUM", description="No care plan documented in handoff", category="missing"))
        if not sbar.background.allergies:
            alerts.append(RiskAlert(severity="LOW", description="Allergy information not documented in handoff", category="missing"))
        if not sbar.situation.primary_diagnosis:
            alerts.append(RiskAlert(severity="MEDIUM", description="Primary diagnosis not documented", category="missing"))

        return alerts
