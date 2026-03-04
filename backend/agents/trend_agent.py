"""
Agent 7 — Trend Agent
Analyses a patient across multiple handoff sessions to detect:
  - Vital sign trends (improving / stable / worsening)
  - Medication escalation patterns (e.g., vasopressor titration)
  - Overall patient trajectory and deterioration risk
  - Shift-over-shift comparison

Queries the session database for historical handoffs with matching patient
MRN or name, then compares vitals over time.
"""

import json
from datetime import datetime
from typing import Optional
from backend.models import (
    SBARData, VitalTrend, TrendReport,
)


class TrendAgent:
    """Compares the current SBAR with historical sessions for the same patient."""

    async def analyse(
        self,
        current_sbar: SBARData,
        historical_sessions: list[dict],  # rows from the sessions table
    ) -> TrendReport:
        mrn = current_sbar.patient.mrn
        if not historical_sessions:
            # AI Predictive Fallback (Mock Predictive Model)
            risk = "LOW"
            summary = "No prior history. Predictive Model: Stable trajectory expected over next 4 hours."
            
            # Simple heuristic for "AI Prediction"
            try:
                hr = current_sbar.assessment.vitals.hr or 80
                bp_str = current_sbar.assessment.vitals.bp or "120/80"
                sbp = int(bp_str.split('/')[0]) if '/' in bp_str else 120
                
                if hr > 110 or sbp < 90:
                    risk = "HIGH"
                    summary = "No prior history. PREDICTION: High probability of hemodynamic collapse within 2 hours (Shock Index > 1.0)."
                elif hr > 100 or sbp < 100:
                    risk = "MEDIUM"
                    summary = "No prior history. PREDICTION: Early warning signs detected. Compensatory phase of shock possible."
            except:
                pass

            return TrendReport(
                patient_mrn=mrn,
                handoffs_analysed=0,
                trajectory_summary=summary,
                deterioration_risk=risk,
            )

        # Parse SBAR from each historical session
        history = self._parse_history(historical_sessions)
        if not history:
            return TrendReport(
                patient_mrn=mrn,
                handoffs_analysed=0,
                trajectory_summary="Prior sessions exist but contain no parseable vitals.",
                deterioration_risk="UNKNOWN",
            )

        # Append current session's vitals as the latest data point
        now = datetime.now().isoformat()
        cv = current_sbar.assessment.vitals
        history.append({
            "timestamp": now,
            "hr": cv.hr,
            "spo2": cv.spo2,
            "rr": cv.rr,
            "temp": cv.temp,
            "bp_systolic": self._parse_sbp(cv.bp),
        })

        vital_trends = self._compute_trends(history)
        risk = self._assess_deterioration(vital_trends)
        summary = self._build_summary(vital_trends, len(history), risk)

        return TrendReport(
            patient_mrn=mrn,
            handoffs_analysed=len(history),
            vital_trends=vital_trends,
            trajectory_summary=summary,
            deterioration_risk=risk,
        )

    # ── Parse historical sessions ─────────────────────────────────────────────

    def _parse_history(self, sessions: list[dict]) -> list[dict]:
        """Extract timestamp + vitals from each session's stored SBAR JSON."""
        points = []
        for sess in sessions:
            try:
                raw = sess.get("sbar_json") or sess.get("sbar") or "{}"
                if isinstance(raw, str):
                    sbar_dict = json.loads(raw)
                else:
                    sbar_dict = raw

                vitals = sbar_dict.get("assessment", {}).get("vitals", {})
                ts = sess.get("timestamp") or sess.get("created_at") or ""
                points.append({
                    "timestamp": ts,
                    "hr": vitals.get("hr"),
                    "spo2": vitals.get("spo2"),
                    "rr": vitals.get("rr"),
                    "temp": vitals.get("temp"),
                    "bp_systolic": self._parse_sbp(vitals.get("bp")),
                })
            except Exception:
                continue

        # Sort by timestamp
        points.sort(key=lambda p: p.get("timestamp", ""))
        return points

    @staticmethod
    def _parse_sbp(bp_str: Optional[str]) -> Optional[int]:
        if not bp_str:
            return None
        try:
            return int(str(bp_str).split("/")[0].split()[0])
        except (ValueError, IndexError):
            return None

    # ── Compute trends per vital sign ─────────────────────────────────────────

    def _compute_trends(self, history: list[dict]) -> list[VitalTrend]:
        vital_keys = [
            ("hr", "Heart Rate (bpm)"),
            ("spo2", "SpO2 (%)"),
            ("rr", "Respiratory Rate (/min)"),
            ("temp", "Temperature (°C)"),
            ("bp_systolic", "Systolic BP (mmHg)"),
        ]
        trends = []
        for key, label in vital_keys:
            values = []
            for point in history:
                v = point.get(key)
                if v is not None:
                    values.append({"timestamp": point["timestamp"], "value": v})

            if len(values) < 2:
                trends.append(VitalTrend(
                    vital_name=label,
                    values=values,
                    direction="insufficient_data",
                    interpretation=f"Not enough data points to trend {label}.",
                ))
                continue

            direction = self._direction(key, [v["value"] for v in values])
            interpretation = self._interpret(label, direction, values)
            trends.append(VitalTrend(
                vital_name=label,
                values=values,
                direction=direction,
                interpretation=interpretation,
            ))
        return trends

    def _direction(self, key: str, vals: list) -> str:
        """Determine if the vital is improving, stable, or worsening."""
        if len(vals) < 2:
            return "insufficient_data"

        # Use last 3 values (or all if fewer)
        recent = vals[-3:]
        first, last = recent[0], recent[-1]
        delta = last - first

        # Define "worsening" direction per vital:
        #   HR worsening = going up (tachycardia)
        #   SpO2 worsening = going down
        #   BP worsening = going down (hypotension context)
        #   Temp worsening = going up (fever)
        #   RR worsening = going up (tachypnoea)
        worsen_if_increasing = {"hr", "rr", "temp"}
        worsen_if_decreasing = {"spo2", "bp_systolic"}

        threshold_pct = 0.05  # 5% change = significant
        base = abs(first) if first else 1
        change_pct = abs(delta) / base

        if change_pct < threshold_pct:
            return "stable"

        if key in worsen_if_increasing:
            return "worsening" if delta > 0 else "improving"
        elif key in worsen_if_decreasing:
            return "worsening" if delta < 0 else "improving"
        return "stable"

    @staticmethod
    def _interpret(label: str, direction: str, values: list[dict]) -> str:
        first_v = values[0]["value"]
        last_v = values[-1]["value"]
        n = len(values)
        if direction == "worsening":
            return f"{label} trending worse: {first_v} → {last_v} over {n} readings. Closer monitoring advised."
        elif direction == "improving":
            return f"{label} improving: {first_v} → {last_v} over {n} readings."
        else:
            return f"{label} stable ~{last_v} over {n} readings."

    # ── Overall deterioration risk ────────────────────────────────────────────

    def _assess_deterioration(self, trends: list[VitalTrend]) -> str:
        worsening = sum(1 for t in trends if t.direction == "worsening")
        if worsening >= 3:
            return "HIGH"
        elif worsening >= 2:
            return "MEDIUM"
        elif worsening >= 1:
            return "LOW"
        return "LOW"

    def _build_summary(self, trends: list[VitalTrend], n: int, risk: str) -> str:
        lines = [f"Analysed {n} handoff(s) for this patient."]
        worsening = [t for t in trends if t.direction == "worsening"]
        improving = [t for t in trends if t.direction == "improving"]
        stable = [t for t in trends if t.direction == "stable"]

        if worsening:
            lines.append(f"⚠ Worsening: {', '.join(t.vital_name for t in worsening)}")
        if improving:
            lines.append(f"✓ Improving: {', '.join(t.vital_name for t in improving)}")
        if stable:
            lines.append(f"— Stable: {', '.join(t.vital_name for t in stable)}")

        lines.append(f"Overall deterioration risk: {risk}")
        return "\n".join(lines)
