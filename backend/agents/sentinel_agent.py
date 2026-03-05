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


    def calculate_raw_score(self, sbar: SBARData, alerts: list[RiskAlert]):
        """Calculate a 0-100 risk score based on alerts and vital signs."""
        from backend.models import DetailedRiskScore

        base_score = 0
        factors = []
        
        # Weighted alerts
        for alert in alerts:
            if alert.severity == "HIGH":
                base_score += 25
                trunc_desc = alert.description.split('—')[0].strip()
                factors.append(trunc_desc)
            elif alert.severity == "MEDIUM":
                base_score += 10
                trunc_desc = alert.description.split('—')[0].strip()
                factors.append(trunc_desc)
            elif alert.severity == "LOW":
                base_score += 5

        # Critical vital check independently (Sepsis check)
        v = sbar.assessment.vitals
        if (v.hr or 0) > 90 and (v.rr or 0) > 20: 
            base_score += 15
            factors.append("SIRS Criteria Met")

        # Cap at 100
        final_score = min(100, base_score)
        
        level = "LOW"
        if final_score >= 80: level = "CRITICAL"
        elif final_score >= 60: level = "HIGH"
        elif final_score >= 30: level = "MODERATE"
        
        return DetailedRiskScore(
            score=final_score,
            risk_level=level,
            contributing_factors=list(set(factors))[:5]  # Limit to top 5
        )

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
                parts = bp_clean.split("/")
                sbp = int(parts[0])

                # SBP threshold alerts
                if sbp < t["sbp"]["low"]:
                    alerts.append(RiskAlert(severity="HIGH", description=f"Hypotension — SBP {sbp} mmHg (threshold < {t['sbp']['low']})", category="vital"))
                elif sbp > t["sbp"]["high"]:
                    alerts.append(RiskAlert(severity="HIGH", description=f"Hypertension — SBP {sbp} mmHg (threshold > {t['sbp']['high']})", category="vital"))
                elif sbp <= t["sbp"]["low"] * (1 + _BORDERLINE_PCT):
                    alerts.append(RiskAlert(severity="MEDIUM", description=f"Blood pressure borderline low — SBP {sbp} mmHg (near threshold {t['sbp']['low']})", category="vital"))

                # MAP and DBP alerts (requires diastolic component)
                if len(parts) >= 2:
                    dbp = int(parts[1])
                    map_val = round((sbp + 2 * dbp) / 3, 1)

                    # Source: Surviving Sepsis Campaign 2021 (MAP target >= 65 mmHg)
                    if map_val < 65:
                        alerts.append(RiskAlert(
                            severity="HIGH",
                            description=f"Critically low MAP {map_val} mmHg (SSC 2021 vasopressor target >= 65 mmHg) — septic shock criteria",
                            category="vital",
                        ))
                    elif map_val < 70:
                        alerts.append(RiskAlert(
                            severity="MEDIUM",
                            description=f"MAP borderline low {map_val} mmHg (SSC 2021 target >= 65 mmHg) — monitor closely",
                            category="vital",
                        ))

                    # Severe diastolic hypotension: vascular collapse / aortic regurgitation risk
                    if dbp < 40:
                        alerts.append(RiskAlert(
                            severity="HIGH",
                            description=f"Severe diastolic hypotension — DBP {dbp} mmHg (< 40 mmHg) — risk of vascular collapse",
                            category="vital",
                        ))
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
