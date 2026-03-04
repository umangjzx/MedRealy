"""
Agent 11 — Literature & Evidence Agent
Retrieves relevant clinical guidelines and research papers based on the patient's condition.
Simulates a Clinical Decision Support (CDS) system.
"""

from backend.models import SBARData, LiteratureReport, EvidenceResource

class LiteratureAgent:
    async def fetch_evidence(self, sbar: SBARData) -> LiteratureReport:
        resources = []
        dx_text = (sbar.situation.primary_diagnosis or "").lower()
        
        # ── Sepsis bundle ─────────────────────────────────────────────────────
        if "sepsis" in dx_text or "septic" in dx_text:
            resources.append(EvidenceResource(
                title="Surviving Sepsis Campaign: International Guidelines 2021",
                source="SCCM / ESICM",
                url="https://www.sccm.org/SurvivingSepsisCampaign/Guidelines/Adult-Patients",
                summary="Recommend immediate administration of broad-spectrum antibiotics and 30ml/kg crystaloid fluid for hypotension.",
                relevance_score=0.99
            ))
            resources.append(EvidenceResource(
                title="Early Goal-Directed Therapy in Treatment of Severe Sepsis",
                source="NEJM",
                url="https://www.nejm.org/doi/full/10.1056/NEJMoa010307",
                summary="Landmark study establishing protocolized resuscitation targets (CVP, MAP, ScvO2).",
                relevance_score=0.85
            ))

        # ── Pneumonia ─────────────────────────────────────────────────────────
        if "pneumonia" in dx_text:
            resources.append(EvidenceResource(
                title="ATS/IDSA Guidelines for Community-Acquired Pneumonia",
                source="Am J Respir Crit Care Med",
                url="https://www.thoracic.org/statements/resources/mtpi/cap-2019.pdf",
                summary="Guidelines for diagnosis and treatment of adults with CAP.",
                relevance_score=0.90
            ))

        # ── ARDS / Hypoxia ────────────────────────────────────────────────────
        if "hypoxia" in dx_text or "ards" in dx_text:
            resources.append(EvidenceResource(
                title="ARDSNet Protocol (Low Tidal Volume)",
                source="ARDSNet",
                url="http://www.ardsnet.org/files/ventilator_protocol_2008-07.pdf",
                summary="Ventilation with lower tidal volumes (6ml/kg PBW) reduces mortality in ARDS.",
                relevance_score=0.92
            ))

        return LiteratureReport(
            topic=sbar.situation.primary_diagnosis or "General Care",
            resources=resources
        )
