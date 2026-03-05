"""
HF Billing Agent — semantic ICD-10 code matching using sentence-transformers.

Uses sentence-transformers/all-MiniLM-L6-v2 (local, ~90 MB) to perform
cosine-similarity matching between clinical text and a curated ICD-10 code pool.
This complements the keyword-based billing agent with semantic understanding,
catching paraphrased or abbreviated diagnoses the keyword rules miss.
"""

from __future__ import annotations

from backend.config import HF_EMBEDDING_MODEL

# Lazy-loaded model (downloaded once to HF cache, ~90 MB)
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[HFBilling] Loading embedding model: {HF_EMBEDDING_MODEL}")
        _model = SentenceTransformer(HF_EMBEDDING_MODEL)
        print("[HFBilling] Embedding model ready")
    return _model


# ── Curated ICD-10 pool for ICU / critical-care diagnoses ────────────────────
# Each entry: (ICD-10 code, human-readable description used for embedding)
ICD10_POOL: list[tuple[str, str]] = [
    ("A41.9",  "Sepsis, unspecified organism"),
    ("A41.01", "Sepsis due to Staphylococcus aureus"),
    ("A41.02", "Sepsis due to MRSA"),
    ("R65.20", "Severe sepsis without septic shock"),
    ("R65.21", "Severe sepsis with septic shock"),
    ("J18.9",  "Pneumonia, unspecified organism"),
    ("J12.89", "Viral pneumonia and respiratory infection"),
    ("J96.01", "Acute respiratory failure with hypoxia"),
    ("J96.11", "Chronic respiratory failure with hypoxia"),
    ("J80",    "Acute respiratory distress syndrome ARDS"),
    ("N17.9",  "Acute kidney injury AKI, unspecified"),
    ("N18.6",  "End-stage renal disease ESRD"),
    ("E11.9",  "Type 2 diabetes mellitus without complications"),
    ("E10.9",  "Type 1 diabetes mellitus without complications"),
    ("E11.65", "Type 2 diabetes mellitus with hyperglycemia"),
    ("E13.10", "Diabetic ketoacidosis DKA without coma"),
    ("E87.1",  "Hypo-osmolality and hyponatremia"),
    ("E87.6",  "Hypokalemia"),
    ("I10",    "Essential primary hypertension"),
    ("I50.9",  "Heart failure, unspecified"),
    ("I50.22", "Acute systolic heart failure"),
    ("I21.9",  "Acute myocardial infarction MI"),
    ("I21.4",  "NSTEMI non-ST elevation myocardial infarction"),
    ("I21.3",  "STEMI ST elevation myocardial infarction"),
    ("I63.9",  "Cerebral infarction ischemic stroke"),
    ("I61.9",  "Hemorrhagic stroke intracerebral hemorrhage"),
    ("I26.99", "Pulmonary embolism PE"),
    ("G93.1",  "Anoxic brain damage"),
    ("K72.00", "Acute liver failure hepatic failure"),
    ("D65",    "Disseminated intravascular coagulation DIC"),
    ("J44.1",  "COPD chronic obstructive pulmonary disease with acute exacerbation"),
    ("B34.9",  "Viral infection"),
    ("R57.9",  "Shock, unspecified"),
    ("R57.0",  "Cardiogenic shock"),
    ("G41.9",  "Epileptic seizures status epilepticus"),
    ("K92.1",  "Gastrointestinal hemorrhage and GI bleeding"),
    ("T81.10", "Post-procedural shock complication"),
    ("J95.1",  "Post-operative respiratory failure"),
]

# Pre-computed description strings (extracted once for encoding)
_DESCRIPTIONS: list[str] = [desc for _, desc in ICD10_POOL]

# Lazy-encoded description embeddings (computed once; reused on every call)
_desc_embeddings = None


def _get_desc_embeddings():
    global _desc_embeddings
    if _desc_embeddings is None:
        from sentence_transformers import SentenceTransformer
        model = _get_model()
        _desc_embeddings = model.encode(_DESCRIPTIONS, convert_to_tensor=True)
    return _desc_embeddings


def semantic_icd_match(
    clinical_text: str,
    top_k: int = 6,
    threshold: float = 0.38,
) -> list[tuple[str, str, float]]:
    """
    Return the top-K ICD-10 codes most semantically similar to clinical_text.

    Args:
        clinical_text: Free-text diagnosis / clinical summary to match.
        top_k: Maximum number of results to return.
        threshold: Minimum cosine similarity (0–1) to include a result.

    Returns:
        List of (code, description, similarity_score) sorted by score desc.
    """
    if not clinical_text or not clinical_text.strip():
        return []

    try:
        from sentence_transformers import util
        model = _get_model()
        query_emb = model.encode(clinical_text.strip(), convert_to_tensor=True)
        desc_embs = _get_desc_embeddings()

        scores = util.cos_sim(query_emb, desc_embs)[0]
        results: list[tuple[str, str, float]] = []
        for i, score in enumerate(scores):
            s = float(score)
            if s >= threshold:
                code, desc = ICD10_POOL[i]
                results.append((code, desc, round(s, 3)))

        results.sort(key=lambda x: -x[2])
        return results[:top_k]

    except Exception as e:
        print(f"[HFBilling] Semantic matching failed: {e}")
        return []
