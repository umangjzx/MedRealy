"""
Agent 10 — Billing & Coding Agent
Analyzes the clinical extraction to suggest ICD-10 diagnosis codes and CPT procedure codes.
Helps ensuring revenue integrity and documentation completeness for reimbursement.
"""

from backend.models import SBARData, BillingReport, CodeSuggestion

class BillingAgent:
    async def analyse(self, sbar: SBARData) -> BillingReport:
        diagnosis_codes = []
        procedure_codes = []
        complexity = "MODERATE"
        
        # ── 1. Diagnosis Logic (Simple Keyword Matching for Demo) ─────────────
        dx_text = (sbar.situation.primary_diagnosis or "").lower()
        hist_text = (sbar.background.relevant_history or "").lower()
        
        if "sepsis" in dx_text or "septic" in dx_text:
            diagnosis_codes.append(CodeSuggestion(code="A41.9", description="Sepsis, unspecified organism", confidence=0.95))
        if "shock" in dx_text:
            diagnosis_codes.append(CodeSuggestion(code="R65.21", description="Severe sepsis with septic shock", confidence=0.98))
            complexity = "HIGH"
        if "pneumonia" in dx_text:
            diagnosis_codes.append(CodeSuggestion(code="J18.9", description="Pneumonia, unspecified organism", confidence=0.90))
        if "diabetes" in hist_text:
            diagnosis_codes.append(CodeSuggestion(code="E11.9", description="Type 2 diabetes mellitus without complications", confidence=0.85))
        if "hypertension" in hist_text:
            diagnosis_codes.append(CodeSuggestion(code="I10", description="Essential (primary) hypertension", confidence=0.90))
            
        # ── 2. Procedure Logic ────────────────────────────────────────────────
        procedures = sbar.background.recent_procedures or []
        for proc in procedures:
            p_lower = proc.lower()
            if "central line" in p_lower:
                procedure_codes.append(CodeSuggestion(code="36556", description="Insertion of non-tunneled centrally inserted central venous catheter", confidence=0.92))
            if "arterial line" in p_lower:
                procedure_codes.append(CodeSuggestion(code="36620", description="Arterial catheterization or cannulation for sampling, monitoring", confidence=0.92))
            if "intubation" in p_lower:
                procedure_codes.append(CodeSuggestion(code="31500", description="Intubation, endotracheal, emergency procedure", confidence=0.95))

        # ── 3. Critical Care Time Estimation ──────────────────────────────────
        # Heuristic: If HIGH complexity and multiple interventions, suggest Critical Care
        predicted_cpt = "99222" # Initial hospital care, moderate
        if complexity == "HIGH":
            predicted_cpt = "99291" # Critical care, first 30-74 minutes
            
        return BillingReport(
            suggested_lcd_codes=diagnosis_codes,
            suggested_cpt_codes=procedure_codes,
            drg_complexity=complexity,
            billing_tips=[
                "Ensure start/stop times for critical care (99291) are documented explicitly.",
                "Link 'Septic Shock' explicitly to the underlying organism if known for higher specificity."
            ] if complexity == "HIGH" else []
        )
