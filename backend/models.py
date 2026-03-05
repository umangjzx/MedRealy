from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

# ── Clinical Safety Disclaimer ──────────────────────────────────────────────
# Displayed on every report output. Required for FDA SaMD advisory-only
# classification and hospital procurement compliance.
CLINICAL_DISCLAIMER = (
    "MedRelay outputs are clinical decision support only and do not constitute "
    "medical advice. All treatment, medication, and care decisions remain the "
    "sole responsibility of the licensed clinician. Always verify AI-generated "
    "information against primary clinical sources before acting."
)

# ── Embedded Knowledge Base Versions ────────────────────────────────────────
# Stamps each report with the exact dataset versions used, enabling audit
# traceability and supporting regulatory review (FDA, HIPAA, HITRUST).
_KB_VERSIONS: Dict[str, str] = {
    "drug_interactions":    "ISMP-2023 / FDA-Labeling / NICE-CG182 / MHRA-DSU",
    "high_alert_meds":      "ISMP-Acute-Care-2023",
    "dose_limits":          "FDA-Labeling / ASHP-IDSA-2020 / AHA-HF-2022",
    "allergy_classes":      "FDA-Labeling / IDSA-2021 / Macy-Romano-JACI-2014",
    "vital_thresholds":     "SSC-2021 / NEWS2 / BTS-O2 / ACLS",
    "icd10_codes":          "ICD-10-CM-FY2024 (CMS)",
    "cpt_codes":            "AMA-CPT-2024",
    "clinical_guidelines":  "SSC-2021 / KDIGO-2012 / AHA-ACC-HF-2022 / AHA-ACC-ACS-2023 / AHA-ASA-Stroke-2019 / GOLD-2025 / ESC-PE-2019 / ADA-2024 / ERS-ATS-ARDS-2023",
    "compliance_standards": "TJC-NPSG-2024 / CMS-CoP-482",
}


class PatientInfo(BaseModel):
    name: Optional[str] = None
    age: Optional[str] = None
    mrn: Optional[str] = None
    room: Optional[str] = None

class Vitals(BaseModel):
    bp: Optional[str] = None
    hr: Optional[int] = None
    rr: Optional[int] = None
    temp: Optional[float] = None
    spo2: Optional[int] = None

class Situation(BaseModel):
    primary_diagnosis: Optional[str] = None
    reason_for_admission: Optional[str] = None
    current_status: Optional[str] = None

class Background(BaseModel):
    relevant_history: Optional[str] = None
    medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    recent_procedures: List[str] = Field(default_factory=list)

class Assessment(BaseModel):
    vitals: Vitals = Field(default_factory=Vitals)
    labs_pending: List[str] = Field(default_factory=list)
    labs_recent: List[str] = Field(default_factory=list)
    pain_level: int = 0  # 0-10 scale
    neurological_status: str = "Intact"  # GCS or desc

class ActionItem(BaseModel):
    task: str
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    due_time: Optional[str] = None  # e.g. "14:00" or "In 1 hour"
    assignee: Literal["Incoming Nurse", "Doctor", "Tech"] = "Incoming Nurse"

class Recommendation(BaseModel):
    care_plan: Optional[str] = None
    escalation_triggers: Optional[str] = None
    pending_orders: List[str] = Field(default_factory=list)
    next_steps: Optional[str] = None
    action_items: List[ActionItem] = Field(default_factory=list)

class DetailedRiskScore(BaseModel):
    score: int  # 0-100
    risk_level: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    contributing_factors: List[str]

class SBARData(BaseModel):
    patient: PatientInfo = Field(default_factory=PatientInfo)
    situation: Situation = Field(default_factory=Situation)
    background: Background = Field(default_factory=Background)
    assessment: Assessment = Field(default_factory=Assessment)
    recommendation: Recommendation = Field(default_factory=Recommendation)
    risk_score: Optional[DetailedRiskScore] = None

class RiskAlert(BaseModel):
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    description: str
    category: str  # e.g., "medication", "vital", "missing"

# ── Agent 5: Compliance Agent models ──────────────────────────────────────────

class ComplianceGap(BaseModel):
    """A single regulatory compliance gap found in the handoff."""
    standard: str                                    # e.g. "NPSG.02.03.01"
    requirement: str                                 # human description
    severity: Literal["CRITICAL", "MAJOR", "MINOR"]
    met: bool = False
    recommendation: str = ""

class ComplianceReport(BaseModel):
    """Overall compliance audit result."""
    score: float = 0.0                               # 0-100 percentage
    gaps: List[ComplianceGap] = Field(default_factory=list)
    standards_checked: int = 0
    standards_met: int = 0

# ── Agent 6: Pharma Agent models ─────────────────────────────────────────────

class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity: Literal["CONTRAINDICATED", "SEVERE", "MODERATE", "MILD"]
    description: str
    clinical_action: str = ""

class DoseAlert(BaseModel):
    medication: str
    issue: Literal["OVERDOSE", "UNDERDOSE", "DUPLICATE", "RENAL_ADJUST", "HEPATIC_ADJUST"]
    description: str
    recommendation: str = ""

class PharmaReport(BaseModel):
    interactions: List[DrugInteraction] = Field(default_factory=list)
    dose_alerts: List[DoseAlert] = Field(default_factory=list)
    safe_count: int = 0                              # medications with no flags
    total_medications: int = 0
    knowledge_base_versions: Dict[str, str] = Field(
        default_factory=lambda: {
            k: _KB_VERSIONS[k]
            for k in ("drug_interactions", "high_alert_meds", "dose_limits", "allergy_classes")
        }
    )
    disclaimer: str = CLINICAL_DISCLAIMER

# ── Agent 7: Trend Agent models ──────────────────────────────────────────────

class VitalTrend(BaseModel):
    vital_name: str                                  # e.g. "hr", "spo2"
    values: List[Dict[str, Any]] = Field(default_factory=list)  # [{timestamp, value}]
    direction: Literal["improving", "stable", "worsening", "insufficient_data"] = "insufficient_data"
    interpretation: str = ""

class TrendReport(BaseModel):
    patient_mrn: Optional[str] = None
    handoffs_analysed: int = 0
    vital_trends: List[VitalTrend] = Field(default_factory=list)
    trajectory_summary: str = ""
    deterioration_risk: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"] = "UNKNOWN"

# ── Agent 8: Educator Agent models ───────────────────────────────────────────

class ClinicalTip(BaseModel):
    topic: str
    explanation: str
    evidence_level: Literal["GUIDELINE", "REVIEW", "EXPERT_OPINION"] = "EXPERT_OPINION"
    source: Optional[str] = None                     # e.g. "AHA 2023 Guidelines"

class EducatorReport(BaseModel):
    tips: List[ClinicalTip] = Field(default_factory=list)
    terminology: Dict[str, str] = Field(default_factory=dict)  # term -> definition
    related_protocols: List[str] = Field(default_factory=list)

# ── Agent 9: Debrief Agent models ────────────────────────────────────────────

class HandoffScorecard(BaseModel):
    category: str                                    # e.g. "Completeness", "Clarity"
    score: float = 0.0                               # 0-10
    max_score: float = 10.0
    findings: List[str] = Field(default_factory=list)

class DebriefReport(BaseModel):
    overall_score: float = 0.0                       # 0-100
    grade: Literal["A", "B", "C", "D", "F"] = "F"
    scorecards: List[HandoffScorecard] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    coaching_note: str = ""

# ── Agent 10: Billing Agent models ───────────────────────────────────────────

class CodeSuggestion(BaseModel):
    code: str
    description: str
    confidence: float

class BillingReport(BaseModel):
    suggested_lcd_codes: List[CodeSuggestion] = Field(default_factory=list)
    suggested_cpt_codes: List[CodeSuggestion] = Field(default_factory=list)
    drg_complexity: Literal["LOW", "MODERATE", "HIGH"] = "MODERATE"
    billing_tips: List[str] = Field(default_factory=list)
    knowledge_base_versions: Dict[str, str] = Field(
        default_factory=lambda: {
            k: _KB_VERSIONS[k]
            for k in ("icd10_codes", "cpt_codes")
        }
    )
    disclaimer: str = CLINICAL_DISCLAIMER

# ── Agent 11: Literature Agent models ────────────────────────────────────────

class EvidenceResource(BaseModel):
    title: str
    source: str
    url: str
    summary: str
    relevance_score: float

class LiteratureReport(BaseModel):
    topic: str
    resources: List[EvidenceResource] = Field(default_factory=list)
    knowledge_base_versions: Dict[str, str] = Field(
        default_factory=lambda: {"clinical_guidelines": _KB_VERSIONS["clinical_guidelines"]}
    )
    disclaimer: str = CLINICAL_DISCLAIMER

# ── Final Report (updated with new agent outputs) ────────────────────────────

class FinalReport(BaseModel):
    session_id: Optional[str] = None          # Set after DB persistence
    sbar: SBARData
    alerts: List[RiskAlert] = Field(default_factory=list)
    outgoing_nurse: str
    incoming_nurse: str
    timestamp: str
    rendered: Optional[str] = None
    signed_by_outgoing: bool = False
    signed_by_incoming: bool = False
    is_demo: bool = False
    # New agent outputs (optional — populated when agents run)
    compliance: Optional[ComplianceReport] = None
    pharma: Optional[PharmaReport] = None
    trend: Optional[TrendReport] = None
    educator: Optional[EducatorReport] = None
    debrief: Optional[DebriefReport] = None
    billing: Optional[BillingReport] = None
    literature: Optional[LiteratureReport] = None
    # Trust & compliance metadata
    disclaimer: str = CLINICAL_DISCLAIMER
    knowledge_base_versions: Dict[str, str] = Field(default_factory=lambda: dict(_KB_VERSIONS))


# ═══════════════════════════════════════════════════════════════════════════════
#  NURSE SCHEDULING MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class PatientRegistryCreate(BaseModel):
    name: str
    mrn: str = ""
    room: str = ""
    bed: str = ""
    acuity: int = Field(default=3, ge=1, le=5)
    diagnosis: str = ""
    notes: str = ""
    admission_date: Optional[str] = None

class PatientRegistryUpdate(BaseModel):
    name: Optional[str] = None
    mrn: Optional[str] = None
    room: Optional[str] = None
    bed: Optional[str] = None
    acuity: Optional[int] = Field(default=None, ge=1, le=5)
    diagnosis: Optional[str] = None
    status: Optional[Literal["admitted", "discharged", "transferred"]] = None
    notes: Optional[str] = None
    discharge_date: Optional[str] = None

class ScheduleCreate(BaseModel):
    shift_date: str                           # YYYY-MM-DD
    shift_type: Literal["day", "evening", "night"]
    notes: str = ""

class ScheduleUpdate(BaseModel):
    status: Optional[Literal["draft", "published", "archived"]] = None
    notes: Optional[str] = None

class AssignmentCreate(BaseModel):
    nurse_user_id: str
    patient_id: str
    is_primary: bool = True
    notes: str = ""

class AutoScheduleRequest(BaseModel):
    max_patients_per_nurse: int = Field(default=6, ge=1, le=20)