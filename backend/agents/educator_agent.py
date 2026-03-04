"""
Agent 8 — Educator Agent
Generates contextual clinical education content based on the handoff:
  - Plain-language explanations of medical terms found in the transcript
  - Evidence-based care tips relevant to the patient's condition
  - Related clinical protocol references
  - Learning points for nursing students / new hires

Uses Claude for rich explanations when available, falls back to a built-in
knowledge base for common ICU/hospital terms and conditions.
"""

import json
import re
import anthropic
from backend.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from backend.models import SBARData, ClinicalTip, EducatorReport

_client = None
if ANTHROPIC_API_KEY:
    try:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    except: pass


# ── Built-in terminology dictionary (fallback when Claude unavailable) ────────
_TERMINOLOGY: dict[str, str] = {
    "sepsis": "A life-threatening organ dysfunction caused by the body's dysregulated response to infection. Requires early antibiotics and fluid resuscitation.",
    "septic shock": "Sepsis with persistent hypotension requiring vasopressors to maintain MAP ≥ 65 mmHg despite adequate fluid resuscitation.",
    "vasopressor": "Medications (e.g., norepinephrine, vasopressin) that constrict blood vessels to raise blood pressure in shock states.",
    "norepinephrine": "First-line vasopressor for septic shock. Acts on alpha-1 receptors to increase systemic vascular resistance.",
    "map": "Mean Arterial Pressure — the average pressure in the arteries during one cardiac cycle. Target ≥ 65 mmHg in sepsis.",
    "lactate": "A biomarker of tissue hypoperfusion. Elevated lactate (> 2 mmol/L) indicates inadequate oxygen delivery and guides resuscitation.",
    "procalcitonin": "A biomarker that rises in bacterial infections. Useful for guiding antibiotic therapy duration.",
    "sbar": "Situation-Background-Assessment-Recommendation — a structured communication framework for clinical handoffs.",
    "rapid response": "A team activated when a patient shows signs of clinical deterioration. Criteria include changes in vitals, mental status, or nursing concern.",
    "central line": "A catheter placed in a large vein (subclavian, internal jugular, femoral) for medication administration, monitoring, or fluid resuscitation.",
    "arterial line": "A catheter in an artery (usually radial) for continuous blood pressure monitoring and arterial blood gas sampling.",
    "intubation": "Insertion of an endotracheal tube into the trachea to secure the airway and provide mechanical ventilation.",
    "dnr": "Do Not Resuscitate — a medical order indicating that CPR should not be attempted if the patient's heart stops.",
    "code status": "The patient's resuscitation preferences: Full Code (all interventions), DNR, DNI (Do Not Intubate), or Comfort Care.",
    "vancomycin": "A glycopeptide antibiotic used for serious Gram-positive infections including MRSA. Requires therapeutic drug monitoring.",
    "piperacillin-tazobactam": "A beta-lactam/beta-lactamase inhibitor combination antibiotic with broad-spectrum coverage. Contains penicillin component.",
    "anaphylaxis": "A severe, life-threatening allergic reaction causing airway swelling, hypotension, and shock. Treat with epinephrine immediately.",
    "tachycardia": "Heart rate > 100 bpm. May indicate pain, fever, hypovolemia, anxiety, sepsis, or cardiac arrhythmia.",
    "bradycardia": "Heart rate < 60 bpm. May be normal in athletes or indicate heart block, medication effect, or increased intracranial pressure.",
    "hypotension": "Low blood pressure (typically SBP < 90 mmHg). Causes include hypovolemia, sepsis, cardiac failure, and anaphylaxis.",
    "hypertension": "Elevated blood pressure (SBP > 140 mmHg). Hypertensive urgency > 180/120 without organ damage; emergency = with organ damage.",
    "hypoxia": "Inadequate oxygen delivery to tissues. SpO2 < 90% is critical. Treat with supplemental O2 and address underlying cause.",
    "tachypnoea": "Respiratory rate > 20/min. May indicate respiratory distress, metabolic acidosis, pain, or anxiety.",
    "hypothermia": "Core temperature < 36°C. Common causes: exposure, sepsis (late stage), transfusion reactions.",
    "isolation precautions": "Infection control measures (Contact, Droplet, Airborne) to prevent pathogen transmission between patients.",
    "mrsa": "Methicillin-Resistant Staphylococcus Aureus — a resistant bacteria requiring contact precautions and specific antibiotics (e.g., vancomycin).",
    "fall risk": "Assessment (e.g., Morse Fall Scale) to identify patients at risk of falling. Interventions include bed alarms, non-slip socks, and 1:1 sitters.",
}

# ── Condition-specific care tips ──────────────────────────────────────────────
_CONDITION_TIPS: dict[str, list[dict]] = {
    "sepsis": [
        {"topic": "Sepsis Hour-1 Bundle", "explanation": "Within 1 hour: measure lactate, obtain blood cultures, administer broad-spectrum antibiotics, begin 30 mL/kg crystalloid for hypotension/lactate ≥ 4, start vasopressors if hypotensive during/after fluid resuscitation.", "evidence_level": "GUIDELINE", "source": "Surviving Sepsis Campaign 2021"},
        {"topic": "Lactate-Guided Resuscitation", "explanation": "Re-measure lactate every 2-4 hours if initial lactate > 2 mmol/L. Goal: lactate clearance ≥ 20% or normalization. Persistent elevation warrants escalation.", "evidence_level": "GUIDELINE", "source": "SSC 2021 / CMS SEP-1"},
    ],
    "pneumonia": [
        {"topic": "Pneumonia Antibiotics Timing", "explanation": "Administer first antibiotic dose within 4 hours of hospital arrival (community-acquired). Blood cultures should be obtained BEFORE antibiotics if possible.", "evidence_level": "GUIDELINE", "source": "ATS/IDSA 2019 CAP Guidelines"},
        {"topic": "Sputum Culture", "explanation": "Obtain sputum culture before antibiotics for intubated patients and patients with severe pneumonia. Gram stain guides empiric therapy.", "evidence_level": "GUIDELINE", "source": "ATS/IDSA 2016 HAP/VAP Guidelines"},
    ],
    "heart failure": [
        {"topic": "Daily Weights", "explanation": "Weigh patient every morning (same time, same scale, same clothing). Weight gain > 2 lbs/day or 5 lbs/week warrants diuretic adjustment.", "evidence_level": "GUIDELINE", "source": "AHA/ACC 2022 HF Guidelines"},
        {"topic": "I&O Monitoring", "explanation": "Strict intake and output monitoring. Negative fluid balance is the goal in acute decompensated heart failure.", "evidence_level": "GUIDELINE", "source": "AHA 2022"},
    ],
    "diabetes": [
        {"topic": "Insulin Safety", "explanation": "Always double-check insulin type, dose, and route. Use insulin-to-carb ratios for meal boluses. Never abbreviate 'U' for units — write it out.", "evidence_level": "GUIDELINE", "source": "ISMP High-Alert Medication Guidelines"},
        {"topic": "Hypoglycemia Protocol", "explanation": "For BG < 70 mg/dL: give 15-20g fast-acting carbs, recheck in 15 min. For BG < 54 mg/dL (Level 2): consider IV dextrose or glucagon.", "evidence_level": "GUIDELINE", "source": "ADA Standards of Care 2024"},
    ],
    "stroke": [
        {"topic": "NIH Stroke Scale", "explanation": "Repeat NIHSS assessment every shift and with any neurological change. Document exact scores. Worsening by ≥ 2 points may indicate extension or hemorrhagic conversion.", "evidence_level": "GUIDELINE", "source": "AHA/ASA 2019 Stroke Guidelines"},
    ],
}

# Protocols to suggest based on keywords in the diagnosis/transcript
_PROTOCOL_TRIGGERS: dict[str, list[str]] = {
    "sepsis": ["Sepsis Hour-1 Bundle (SSC 2021)", "Early Goal-Directed Therapy Protocol", "Vasopressor Titration Protocol"],
    "pneumonia": ["CAP/HAP Antibiotic Selection Algorithm", "Sputum Sample Collection Protocol"],
    "fall": ["Morse Fall Scale Assessment", "Fall Prevention Bundle", "Post-Fall Assessment Protocol"],
    "pain": ["Numeric Pain Scale Assessment", "Multimodal Analgesia Protocol", "Opioid Stewardship Guidelines"],
    "code": ["Code Blue Response Protocol", "ACLS Algorithm", "Rapid Response Activation Criteria"],
    "diabetes": ["Insulin Sliding Scale Protocol", "Hypoglycemia Treatment Protocol", "DKA Management Protocol"],
    "stroke": ["Acute Stroke Protocol", "tPA Administration Checklist", "Post-tPA Monitoring Protocol"],
    "cardiac": ["Chest Pain Protocol", "Troponin Trending Protocol", "Anticoagulation Protocol"],
    "respiratory": ["Oxygen Therapy Titration Protocol", "Non-Invasive Ventilation Protocol", "Intubation Checklist"],
    "renal": ["AKI KDIGO Staging Protocol", "Renal Replacement Therapy Protocol", "Contrast-Induced Nephropathy Prevention"],
}


class EducatorAgent:
    """Generates clinical education content contextual to the handoff."""

    async def educate(self, sbar: SBARData, transcript: str = "") -> EducatorReport:
        # 1. Identify medical terms in the transcript
        terminology = self._extract_terminology(transcript)

        # 2. Generate condition-specific tips
        tips = self._get_condition_tips(sbar, transcript)

        # 3. Suggest related protocols
        protocols = self._suggest_protocols(sbar, transcript)

        # 4. Try AI (Claude) for richer contextual education
        claude_tips = []
        if _client:
            try:
                # Need to update _claude_educate signature? It uses self.
                claude_tips = await self._claude_educate(sbar, transcript)
            except Exception as e:
                print(f"[EducatorAgent] Claude education failed: {e}")

        tips.extend(claude_tips)

        return EducatorReport(
            tips=tips,
            terminology=terminology,
            related_protocols=protocols,
        )

    # ── Terminology extraction ────────────────────────────────────────────────

    def _extract_terminology(self, transcript: str) -> dict[str, str]:
        """Find known medical terms in the transcript and return definitions."""
        found: dict[str, str] = {}
        t_lower = transcript.lower()
        for term, definition in _TERMINOLOGY.items():
            # Match whole word (with some flexibility for plural/possessive)
            if re.search(rf"\b{re.escape(term)}\b", t_lower):
                found[term] = definition
        return found

    # ── Condition tips ────────────────────────────────────────────────────────

    def _get_condition_tips(self, sbar: SBARData, transcript: str) -> list[ClinicalTip]:
        tips: list[ClinicalTip] = []
        text = " ".join([
            sbar.situation.primary_diagnosis or "",
            sbar.situation.reason_for_admission or "",
            sbar.situation.current_status or "",
            transcript,
        ]).lower()

        for condition, tip_list in _CONDITION_TIPS.items():
            if condition in text:
                for tip_data in tip_list:
                    tips.append(ClinicalTip(**tip_data))
        return tips

    # ── Protocol suggestions ──────────────────────────────────────────────────

    def _suggest_protocols(self, sbar: SBARData, transcript: str) -> list[str]:
        protocols: list[str] = []
        text = " ".join([
            sbar.situation.primary_diagnosis or "",
            sbar.situation.reason_for_admission or "",
            transcript,
        ]).lower()

        for keyword, protocol_list in _PROTOCOL_TRIGGERS.items():
            if keyword in text:
                for p in protocol_list:
                    if p not in protocols:
                        protocols.append(p)
        return protocols

    # ── AI-powered contextual education ───────────────────────────────────

    async def _claude_educate(self, sbar: SBARData, transcript: str) -> list[ClinicalTip]:
        prompt = (
            "You are a clinical nurse educator. Based on this patient handoff, generate "
            "3-5 targeted learning tips for a nursing student or new nurse. "
            "Focus on the specific conditions, medications, and situations in this handoff. "
            "Each tip should be practical, evidence-based, and actionable.\n\n"
            f"Patient: {sbar.patient.name or 'Unknown'}\n"
            f"Diagnosis: {sbar.situation.primary_diagnosis or 'Unknown'}\n"
            f"Medications: {', '.join(sbar.background.medications) or 'None listed'}\n"
            f"Vitals: HR={sbar.assessment.vitals.hr}, BP={sbar.assessment.vitals.bp}, "
            f"SpO2={sbar.assessment.vitals.spo2}, Temp={sbar.assessment.vitals.temp}\n\n"
            "Return ONLY a JSON array of objects with keys: "
            '"topic", "explanation", "evidence_level" (one of GUIDELINE/REVIEW/EXPERT_OPINION), '
            '"source" (nullable string).\n'
            "No markdown fences, no commentary."
        )
        response = await _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (getattr(response.content[0], "text", "") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
        data = json.loads(raw)
        return [ClinicalTip(**item) for item in data]
