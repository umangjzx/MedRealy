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
            resources.append(EvidenceResource(
                title="Official ERS/ATS/ESICM/SCCM/ALAT Berlin Definition & Guidelines for ARDS 2023",
                source="Eur Respir J 2023 / Am J Respir Crit Care Med",
                url="https://erj.ersjournals.com/content/61/6/2200827",
                summary="Updated Berlin criteria and management recommendations for ARDS including prone positioning and ECMO criteria.",
                relevance_score=0.95
            ))

        # ── Acute Kidney Injury ───────────────────────────────────────────────
        if "aki" in dx_text or "acute kidney" in dx_text or "renal failure" in dx_text:
            resources.append(EvidenceResource(
                title="KDIGO Clinical Practice Guideline for Acute Kidney Injury",
                source="KDIGO / Kidney Int Suppl 2012",
                url="https://kdigo.org/guidelines/acute-kidney-injury/",
                summary="Staging AKI by creatinine/urine output criteria, fluid management, and RRT initiation thresholds.",
                relevance_score=0.93
            ))

        # ── Heart Failure ─────────────────────────────────────────────────────
        if "heart failure" in dx_text or "chf" in dx_text:
            resources.append(EvidenceResource(
                title="2022 AHA/ACC/HFSA Guideline for the Management of Heart Failure",
                source="J Am Coll Cardiol 2022",
                url="https://www.jacc.org/doi/10.1016/j.jacc.2021.12.012",
                summary="Comprehensive HFrEF/HFpEF management: GDMT pillars (ARNI, beta-blocker, MRA, SGLT2i), device therapy, and diuresis targets.",
                relevance_score=0.94
            ))

        # ── Acute Coronary Syndrome / MI ─────────────────────────────────────
        if "myocardial infarction" in dx_text or "stemi" in dx_text or "nstemi" in dx_text or "acs" in dx_text:
            resources.append(EvidenceResource(
                title="2023 AHA/ACC Guideline for Diagnosis and Management of Acute Coronary Syndromes",
                source="J Am Coll Cardiol 2023",
                url="https://www.jacc.org/doi/10.1016/j.jacc.2023.10.018",
                summary="Evidence-based recommendations for antithrombotic therapy, revascularisation timing, and secondary prevention.",
                relevance_score=0.95
            ))

        # ── Stroke ────────────────────────────────────────────────────────────
        if "stroke" in dx_text or "cva" in dx_text or "cerebral infarction" in dx_text:
            resources.append(EvidenceResource(
                title="2019 AHA/ASA Guidelines for the Early Management of Acute Ischaemic Stroke",
                source="Stroke 2019",
                url="https://www.ahajournals.org/doi/10.1161/STR.0000000000000211",
                summary="Thrombolysis window (4.5h), mechanical thrombectomy criteria, BP targets, and post-stroke care protocols.",
                relevance_score=0.93
            ))

        # ── COPD ──────────────────────────────────────────────────────────────
        if "copd" in dx_text or "chronic obstructive" in dx_text:
            resources.append(EvidenceResource(
                title="GOLD 2025 Global Strategy for COPD Prevention, Diagnosis and Management",
                source="Global Initiative for Chronic Obstructive Lung Disease (GOLD) 2025",
                url="https://goldcopd.org/2025-gold-report/",
                summary="Updated ABCD assessment, inhaler escalation, and exacerbation management with LAMA/LABA/ICS stepwise therapy.",
                relevance_score=0.92
            ))

        # ── Pulmonary Embolism ────────────────────────────────────────────────
        if "pulmonary embolism" in dx_text or " pe " in dx_text:
            resources.append(EvidenceResource(
                title="2019 ESC Guidelines on the Diagnosis and Management of Acute Pulmonary Embolism",
                source="Eur Heart J 2019",
                url="https://academic.oup.com/eurheartj/article/41/4/543/5556136",
                summary="Risk stratification (PESI/sPESI), anticoagulation selection, thrombolysis thresholds, CTPA/V/Q criteria.",
                relevance_score=0.93
            ))

        # ── Diabetic Ketoacidosis ─────────────────────────────────────────────
        if "dka" in dx_text or "diabetic ketoacidosis" in dx_text or "hyperglycemi" in dx_text:
            resources.append(EvidenceResource(
                title="ADA Standards of Medical Care in Diabetes 2024 — DKA & HHS Management",
                source="Diabetes Care 2024 (ADA)",
                url="https://doi.org/10.2337/dc24-S016",
                summary="Fluid resuscitation, insulin infusion protocol, potassium replacement, and transition to subcutaneous insulin for DKA/HHS.",
                relevance_score=0.94
            ))

        return LiteratureReport(
            topic=sbar.situation.primary_diagnosis or "General Care",
            resources=resources
        )
