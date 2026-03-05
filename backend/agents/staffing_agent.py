"""
Agent 10 — Staffing Agent
Analyzes unit acuity, nurse load, and patient risk scores to provide
staffing recommendations and burnout warnings.
Uses deterministic rule-based analysis — no external API key required.
"""

from datetime import datetime

# ── Thresholds ────────────────────────────────────────────────────────────────
_ACUITY_RED    = 3.5  # avg acuity per active nurse >= this → Red
_ACUITY_YELLOW = 2.5  # avg acuity per active nurse >= this → Yellow
_BURNOUT_AVG   = 3.5  # per-nurse avg acuity that triggers burnout warning
_BURNOUT_COUNT = 4    # patient count per nurse that triggers burnout warning


class StaffingAgent:
    async def analyze(
        self, nurses: list, patients: list, assignments: list, risk_data: dict
    ) -> dict:
        """
        Analyze the current staffing schedule and patient acuity.

        Args:
            nurses:      List of nurse objects (user_id, display_name, role, shift_status)
            patients:    List of patient objects (patient_id, name, acuity, diagnosis)
            assignments: List of assignment objects (nurse_user_id, patient_id)
            risk_data:   Dict mapping patient_id -> {score: 0-100, alerts: []}

        Returns:
            JSON-serialisable dict with unit_status, summary, prediction,
            recommendations, and burnout_risks.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ── Build nurse load map (active / on_call only) ──────────────────────
        nurse_loads: dict[str, dict] = {
            n["user_id"]: {
                "name": n["display_name"],
                "role": n["role"],
                "status": n.get("shift_status", "active"),
                "patients": [],
                "total_acuity": 0,
                "risk_sum": 0,
            }
            for n in nurses
            if n.get("shift_status", "active") in ("active", "on_call")
        }

        absent_nurses = [n for n in nurses if n.get("shift_status") == "absent"]
        unassigned_patients: list[dict] = []

        # ── Map existing assignments to nurse loads ───────────────────────────
        for a in assignments:
            nid = a["nurse_user_id"]
            pid = a["patient_id"]
            pat = next((p for p in patients if p["patient_id"] == pid), None)
            if not pat:
                continue
            risk = risk_data.get(pid, {"score": 0, "alerts": []})
            p_item = {
                "name": pat["name"],
                "acuity": pat["acuity"],
                "risk": risk["score"],
                "diagnosis": pat["diagnosis"],
                "old_nurse_id": nid,
            }
            if nid in nurse_loads:
                nurse_loads[nid]["patients"].append(p_item)
                nurse_loads[nid]["total_acuity"] += pat["acuity"]
                nurse_loads[nid]["risk_sum"] += risk["score"]
            else:
                # Nurse absent / not in active load map
                unassigned_patients.append(p_item)

        # ── Auto-assign uncovered patients to least-loaded active nurses ──────
        active_nurses = [
            (nid, data)
            for nid, data in nurse_loads.items()
            if data["status"] == "active"
        ]
        recommendations: list[str] = []

        for p in unassigned_patients:
            absent_name = next(
                (
                    n["display_name"]
                    for n in absent_nurses
                    if n["user_id"] == p.get("old_nurse_id")
                ),
                "absent nurse",
            )
            if active_nurses:
                # Assign to the nurse with the lowest total_acuity
                active_nurses.sort(key=lambda x: x[1]["total_acuity"])
                target_nid, target_data = active_nurses[0]
                target_data["patients"].append(p)
                target_data["total_acuity"] += p["acuity"]
                target_data["risk_sum"] += p["risk"]
                recommendations.append(
                    f"Assign {p['name']} (from absent {absent_name}) → {target_data['name']}"
                )
            else:
                recommendations.append(
                    f"CRITICAL: {p['name']} has no nurse — activate on-call staff immediately"
                )

        # ── Activate on-call nurses if unit load is critical ──────────────────
        avg_acuity = (
            sum(d["total_acuity"] for _, d in active_nurses) / len(active_nurses)
            if active_nurses
            else 0.0
        )
        on_call = [
            (nid, data)
            for nid, data in nurse_loads.items()
            if data["status"] == "on_call"
        ]
        if avg_acuity >= _ACUITY_RED and on_call:
            for _, data in on_call:
                recommendations.append(
                    f"Activate on-call nurse: {data['name']} (unit acuity critical)"
                )

        # ── Burnout risk detection ─────────────────────────────────────────────
        burnout_risks: list[str] = []
        for _, data in nurse_loads.items():
            n_pts = len(data["patients"])
            avg_pt_acuity = data["total_acuity"] / n_pts if n_pts else 0
            if n_pts >= _BURNOUT_COUNT or avg_pt_acuity >= _BURNOUT_AVG:
                burnout_risks.append(
                    f"{data['name']} — {n_pts} patients, avg acuity {avg_pt_acuity:.1f}"
                )

        # ── Unit status ───────────────────────────────────────────────────────
        has_unassigned = bool(unassigned_patients) and not active_nurses
        if avg_acuity >= _ACUITY_RED or has_unassigned:
            unit_status = "Red"
        elif avg_acuity >= _ACUITY_YELLOW or bool(unassigned_patients) or burnout_risks:
            unit_status = "Yellow"
        else:
            unit_status = "Green"

        # ── Summary text ──────────────────────────────────────────────────────
        total_active = len(active_nurses)
        total_patients = sum(len(d["patients"]) for d in nurse_loads.values())
        summary = (
            f"As of {timestamp}: {total_active} active nurse(s) covering "
            f"{total_patients} patient(s). "
            f"Average acuity: {avg_acuity:.1f}/5. Unit status: {unit_status}."
        )
        if absent_nurses:
            names = ", ".join(n["display_name"] for n in absent_nurses)
            summary += f" Absent staff: {names}."
        if burnout_risks:
            summary += f" {len(burnout_risks)} nurse(s) flagged for high load."

        # ── 4-hour prediction ─────────────────────────────────────────────────
        if avg_acuity >= _ACUITY_RED:
            prediction = (
                "High acuity load — risk of patient safety incidents in the next "
                "4 hours without staffing relief."
            )
        elif avg_acuity >= _ACUITY_YELLOW:
            prediction = (
                "Moderate acuity load — monitor closely; activate on-call staff "
                "if admissions increase."
            )
        else:
            prediction = "Staffing load appears manageable for the next 4 hours."

        if not recommendations:
            recommendations.append("No immediate reassignments needed.")

        return {
            "unit_status": unit_status,
            "summary": summary,
            "prediction": prediction,
            "recommendations": recommendations,
            "burnout_risks": burnout_risks,
        }
