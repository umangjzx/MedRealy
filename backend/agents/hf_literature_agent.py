"""
HF Literature Agent — semantic evidence retrieval using sentence-transformers.

Uses sentence-transformers/all-MiniLM-L6-v2 to perform semantic similarity
matching between a patient's diagnosis and a curated clinical guidelines database.
This replaces rigid keyword matching, catching synonyms, abbreviations, and
multi-morbidity scenarios that exact string checks miss.
"""

from __future__ import annotations

from backend.config import HF_EMBEDDING_MODEL

# ── Evidence knowledge base ───────────────────────────────────────────────────
# Each entry: (trigger_keywords, EvidenceResource dict)
# trigger_keywords is a short phrase that best represents the clinical concept.
EVIDENCE_DB: list[dict] = [
    {
        "concept": "sepsis septic shock severe infection bacteremia",
        "title": "Surviving Sepsis Campaign: International Guidelines 2021",
        "source": "SCCM / ESICM",
        "url": "https://www.sccm.org/SurvivingSepsisCampaign/Guidelines/Adult-Patients",
        "summary": "Recommend immediate broad-spectrum antibiotics, 30 ml/kg crystalloid fluid resuscitation for hypotension, and vasopressors to target MAP ≥65 mmHg.",
        "relevance_score": 0.99,
    },
    {
        "concept": "sepsis early goal directed therapy resuscitation",
        "title": "Early Goal-Directed Therapy in Treatment of Severe Sepsis",
        "source": "NEJM",
        "url": "https://www.nejm.org/doi/full/10.1056/NEJMoa010307",
        "summary": "Landmark study establishing protocolized resuscitation targets: CVP 8–12 mmHg, MAP ≥65, ScvO2 ≥70%.",
        "relevance_score": 0.85,
    },
    {
        "concept": "pneumonia community-acquired chest infection pulmonary consolidation",
        "title": "ATS/IDSA Guidelines for Community-Acquired Pneumonia",
        "source": "Am J Respir Crit Care Med",
        "url": "https://www.thoracic.org/statements/resources/mtpi/cap-2019.pdf",
        "summary": "Guidelines for diagnosis and antibiotic treatment of adults with community-acquired pneumonia.",
        "relevance_score": 0.90,
    },
    {
        "concept": "ARDS acute respiratory distress syndrome hypoxia low oxygen mechanical ventilation",
        "title": "ARDSNet Protocol — Low Tidal Volume Ventilation",
        "source": "ARDSNet",
        "url": "http://www.ardsnet.org/files/ventilator_protocol_2008-07.pdf",
        "summary": "Ventilation with lower tidal volumes (6 ml/kg PBW) plus PEEP significantly reduces mortality in ARDS.",
        "relevance_score": 0.92,
    },
    {
        "concept": "ARDS Berlin definition prone positioning ECMO oxygenation failure",
        "title": "ERS/ATS/ESICM/SCCM Berlin Definition & ARDS Guidelines 2023",
        "source": "Eur Respir J / Am J Respir Crit Care Med",
        "url": "https://erj.ersjournals.com/content/61/6/2200827",
        "summary": "Updated Berlin criteria and management recommendations for ARDS including prone positioning and ECMO criteria.",
        "relevance_score": 0.95,
    },
    {
        "concept": "acute kidney injury AKI renal failure oliguria creatinine rise",
        "title": "KDIGO Clinical Practice Guideline for Acute Kidney Injury",
        "source": "KDIGO / Kidney Int Suppl",
        "url": "https://kdigo.org/guidelines/acute-kidney-injury/",
        "summary": "AKI staging by creatinine/urine-output criteria, fluid management, avoidance of nephrotoxins, and RRT initiation thresholds.",
        "relevance_score": 0.93,
    },
    {
        "concept": "heart failure CHF congestive cardiac decompensation dyspnea edema",
        "title": "2022 AHA/ACC/HFSA Guideline for the Management of Heart Failure",
        "source": "J Am Coll Cardiol 2022",
        "url": "https://www.jacc.org/doi/10.1016/j.jacc.2021.12.012",
        "summary": "Comprehensive HFrEF/HFpEF management: GDMT pillars (ARNI, beta-blocker, MRA, SGLT2i), device therapy, and diuresis targets.",
        "relevance_score": 0.94,
    },
    {
        "concept": "myocardial infarction MI STEMI NSTEMI ACS chest pain troponin",
        "title": "2023 AHA/ACC Guideline for Acute Coronary Syndromes",
        "source": "J Am Coll Cardiol 2023",
        "url": "https://www.jacc.org/doi/10.1016/j.jacc.2023.10.018",
        "summary": "Evidence-based recommendations for antithrombotic therapy, revascularisation timing, and secondary prevention in ACS.",
        "relevance_score": 0.95,
    },
    {
        "concept": "stroke CVA cerebral infarction ischemic TIA thrombolysis thrombectomy",
        "title": "2019 AHA/ASA Guidelines for Early Management of Acute Ischaemic Stroke",
        "source": "Stroke 2019",
        "url": "https://www.ahajournals.org/doi/10.1161/STR.0000000000000211",
        "summary": "Thrombolysis window (4.5 h), mechanical thrombectomy criteria, BP targets, and post-stroke care protocols.",
        "relevance_score": 0.93,
    },
    {
        "concept": "COPD chronic obstructive pulmonary exacerbation bronchospasm wheeze inhaler",
        "title": "GOLD 2025 Global Strategy for COPD Prevention, Diagnosis and Management",
        "source": "Global Initiative for Chronic Obstructive Lung Disease 2025",
        "url": "https://goldcopd.org/2025-gold-report/",
        "summary": "Updated ABCD assessment, inhaler escalation (LAMA/LABA/ICS), and exacerbation management guidance.",
        "relevance_score": 0.92,
    },
    {
        "concept": "pulmonary embolism PE DVT deep vein thrombosis anticoagulation",
        "title": "2019 ESC Guidelines on Acute Pulmonary Embolism",
        "source": "Eur Heart J 2019",
        "url": "https://academic.oup.com/eurheartj/article/41/4/543/5556136",
        "summary": "Risk stratification (PESI/sPESI), anticoagulation selection, thrombolysis thresholds, CTPA/V-Q criteria.",
        "relevance_score": 0.93,
    },
    {
        "concept": "diabetic ketoacidosis DKA hyperglycemia insulin glucose acidosis",
        "title": "ADA Standards of Medical Care in Diabetes 2024 — DKA & HHS Management",
        "source": "Diabetes Care 2024 (ADA)",
        "url": "https://doi.org/10.2337/dc24-S016",
        "summary": "Fluid resuscitation, insulin infusion protocol, potassium replacement, and transition to subcutaneous insulin for DKA/HHS.",
        "relevance_score": 0.94,
    },
]

# Lazy-loaded model and embeddings
_model = None
_concept_embeddings = None
_concepts: list[str] = [e["concept"] for e in EVIDENCE_DB]


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[HFLiterature] Loading embedding model: {HF_EMBEDDING_MODEL}")
        _model = SentenceTransformer(HF_EMBEDDING_MODEL)
        print("[HFLiterature] Embedding model ready")
    return _model


def _get_concept_embeddings():
    global _concept_embeddings
    if _concept_embeddings is None:
        model = _get_model()
        _concept_embeddings = model.encode(_concepts, convert_to_tensor=True)
    return _concept_embeddings


def semantic_evidence_search(
    diagnosis_text: str,
    top_k: int = 4,
    threshold: float = 0.30,
) -> list[dict]:
    """
    Return the most relevant evidence resources for the given diagnosis text.

    Args:
        diagnosis_text: Free-text primary diagnosis / clinical summary.
        top_k: Maximum number of resources to return.
        threshold: Minimum cosine similarity to include a result.

    Returns:
        List of evidence dicts (title, source, url, summary, relevance_score),
        sorted by similarity score descending.
    """
    if not diagnosis_text or not diagnosis_text.strip():
        return []

    try:
        from sentence_transformers import util
        model = _get_model()
        query_emb = model.encode(diagnosis_text.strip(), convert_to_tensor=True)
        concept_embs = _get_concept_embeddings()

        scores = util.cos_sim(query_emb, concept_embs)[0]
        results: list[tuple[float, dict]] = []
        for i, score in enumerate(scores):
            s = float(score)
            if s >= threshold:
                entry = dict(EVIDENCE_DB[i])  # shallow copy
                entry["relevance_score"] = round(s, 3)
                results.append((s, entry))

        results.sort(key=lambda x: -x[0])
        return [entry for _, entry in results[:top_k]]

    except Exception as e:
        print(f"[HFLiterature] Semantic search failed: {e}")
        return []
