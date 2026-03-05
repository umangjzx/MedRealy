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
            
        # ── 2. Procedure Logic (CPT codes, AMA 2024) ────────────────────
        # Source: AMA CPT Professional Edition 2024
        procedures = sbar.background.recent_procedures or []
        for proc in procedures:
            p_lower = proc.lower()
            if "central line" in p_lower:
                procedure_codes.append(CodeSuggestion(code="36556", description="Insertion of non-tunneled centrally inserted central venous catheter", confidence=0.92))
            if "arterial line" in p_lower:
                procedure_codes.append(CodeSuggestion(code="36620", description="Arterial catheterization or cannulation for sampling, monitoring", confidence=0.92))
            if "intubation" in p_lower or "endotracheal" in p_lower:
                procedure_codes.append(CodeSuggestion(code="31500", description="Intubation, endotracheal, emergency procedure", confidence=0.95))
            if "dialysis" in p_lower or "crrt" in p_lower or "renal replacement" in p_lower:
                procedure_codes.append(CodeSuggestion(code="90945", description="Dialysis procedure other than hemodialysis (CRRT/peritoneal)", confidence=0.90))
            if "chest tube" in p_lower or "thoracostomy" in p_lower:
                procedure_codes.append(CodeSuggestion(code="32551", description="Tube thoracostomy, includes connection to drainage system", confidence=0.91))
            if "foley" in p_lower or "urinary catheter" in p_lower:
                procedure_codes.append(CodeSuggestion(code="51702", description="Insertion of temporary indwelling bladder catheter", confidence=0.88))
            if "bronchoscopy" in p_lower:
                procedure_codes.append(CodeSuggestion(code="31622", description="Bronchoscopy, rigid or flexible; diagnostic", confidence=0.90))
            if "lumbar puncture" in p_lower or "spinal tap" in p_lower or "lp" in p_lower:
                procedure_codes.append(CodeSuggestion(code="62270", description="Spinal puncture, lumbar, diagnostic", confidence=0.91))

        # ── 3. Critical Care Time Estimation ──────────────────────────────────
        # Heuristic: If HIGH complexity and multiple interventions, suggest Critical Care
        predicted_cpt = "99222" # Initial hospital care, moderate
        if complexity == "HIGH":
            predicted_cpt = "99291" # Critical care, first 30-74 minutes
            
        return BillingReport(
            suggested_lcd_codes=diagnosis_codes,
            suggested_cpt_codes=procedure_codes,
            drg_complexity=complexity,
            billing_tips=(
                [
                    # HIGH complexity tips
                    "Document start/stop times for critical care (CPT 99291) explicitly in nursing notes.",
                    "Link 'Septic Shock' to the underlying organism if known for maximum ICD-10 specificity (A41.0-A41.9).",
                    "For ARDS/respiratory failure: document PaO2/FiO2 ratio to support J96.01 vs J96.00.",
                    "Ensure CC/MCC (Complication/Comorbidity) pairs are all captured to maximise DRG weight.",
                    "Document vasopressor dependency (e.g., norepinephrine dose and duration) to support septic shock code R65.21.",
                    "For AKI: document baseline creatinine or eGFR to establish the acute-on-chronic distinction (N17 vs N18).",
                ] if complexity == "HIGH" else [
                    # MODERATE complexity tips
                    "Review discharge diagnosis vs admission diagnosis; late changes can shift DRG significantly.",
                    "Ensure all chronic comorbidities encountered during stay (CKD, A-fib, COPD) are documented.",
                    "Link procedures to diagnoses explicitly in the clinical note for clean claim submission.",
                ]
            )
        )
