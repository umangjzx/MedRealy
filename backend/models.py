from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

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

class Recommendation(BaseModel):
    care_plan: Optional[str] = None
    escalation_triggers: Optional[str] = None
    pending_orders: List[str] = Field(default_factory=list)
    next_steps: Optional[str] = None

class SBARData(BaseModel):
    patient: PatientInfo = Field(default_factory=PatientInfo)
    situation: Situation = Field(default_factory=Situation)
    background: Background = Field(default_factory=Background)
    assessment: Assessment = Field(default_factory=Assessment)
    recommendation: Recommendation = Field(default_factory=Recommendation)

class RiskAlert(BaseModel):
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    description: str
    category: str  # e.g., "medication", "vital", "missing"

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