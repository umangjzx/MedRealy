"""
OpenFDA API Client
Queries the FDA drug adverse-event endpoint to flag potential drug interactions
and allergy conflicts based on the patient's medication list.
"""

import httpx
from backend.config import OPENFDA_BASE_URL


async def query_drug_events(drug_name: str, limit: int = 5) -> list[dict]:
    """
    Query OpenFDA for adverse events related to a drug name.
    Returns a list of event records (simplified).
    """
    # Escape special characters in the drug name for the FDA query
    safe_name = drug_name.replace('"', '').replace("'", "")
    params = {
        "search": f'patient.drug.medicinalproduct:"{safe_name}"',
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPENFDA_BASE_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
    except Exception as e:
        print(f"[FDAClient] Query failed for '{drug_name}': {e}")
    return []


def check_penicillin_class(medication: str) -> bool:
    """Return True if the medication belongs to the penicillin antibiotic class.
    Source: FDA prescribing information / IDSA antibiotic reference
    """
    penicillin_keywords = [
        # Original keywords
        "penicillin", "amoxicillin", "ampicillin", "piperacillin",
        "tazobactam", "pip-tazo", "nafcillin", "oxacillin",
        "dicloxacillin", "cloxacillin", "augmentin",
        # Extended list
        "flucloxacillin", "ticarcillin", "co-amoxiclav", "temocillin",
        "benzylpenicillin", "phenoxymethylpenicillin", "pivampicillin",
    ]
    med_lower = medication.lower()
    return any(kw in med_lower for kw in penicillin_keywords)


# Cephalosporin antibiotic class
# Source: FDA prescribing information / Merck Manual antibiotic reference
CEPHALOSPORIN_KEYWORDS = [
    "cephalexin", "cefazolin", "cefuroxime", "ceftriaxone", "ceftazidime",
    "cefepime", "cefdinir", "cefprozil", "cefadroxil", "cefotaxime",
    "cefoxitin", "cefpodoxime", "ceftolozane", "loracarbef",
]


def check_cephalosporin_class(medication: str) -> bool:
    """Return True if the medication belongs to the cephalosporin antibiotic class.
    Source: FDA prescribing information / Merck Manual
    """
    med_lower = medication.lower()
    return any(kw in med_lower for kw in CEPHALOSPORIN_KEYWORDS)


# Sulfonamide antibiotic class
# Source: FDA prescribing information / IDSA antibiotic reference
SULFONAMIDE_KEYWORDS = [
    "sulfamethoxazole", "trimethoprim", "co-trimoxazole", "bactrim",
    "septra", "sulfadiazine", "sulfisoxazole", "sulfadoxine",
    "dapsone", "sulfasalazine",
]


def check_sulfonamide_class(medication: str) -> bool:
    """Return True if the medication belongs to the sulfonamide antibiotic class.
    Source: FDA prescribing information
    """
    med_lower = medication.lower()
    return any(kw in med_lower for kw in SULFONAMIDE_KEYWORDS)


async def check_allergy_drug_conflict(
    medications: list[str], allergies: list[str]
) -> list[dict]:
    """
    Cross-reference medications with allergies.
    Returns a list of conflict dicts: {"medication": str, "allergy": str}.

    Class-level checks implemented:
      - Penicillin class allergy (FDA / IDSA)
      - Cephalosporin class allergy (FDA)
      - Sulfonamide class allergy (FDA)
      - Penicillin -> Cephalosporin cross-reactivity (~2% risk)
        Source: Macy & Romano (2014) JACI / IDSA 2021 antibiotic allergy guidelines
    """
    conflicts = []
    allergy_lower = [a.lower() for a in allergies]

    for med in medications:
        # --- Penicillin class allergy ---
        if any("penicillin" in a for a in allergy_lower):
            if check_penicillin_class(med):
                conflicts.append({
                    "medication": med,
                    "allergy": "Penicillin (class allergy)",
                })

        # --- Cephalosporin class allergy ---
        if any("cephalosporin" in a or "ceph" in a for a in allergy_lower):
            if check_cephalosporin_class(med):
                conflicts.append({
                    "medication": med,
                    "allergy": "Cephalosporin (class allergy)",
                })

        # --- Sulfonamide / sulfa class allergy ---
        if any("sulfa" in a or "sulfonamide" in a or "bactrim" in a or "trimethoprim" in a
               for a in allergy_lower):
            if check_sulfonamide_class(med):
                conflicts.append({
                    "medication": med,
                    "allergy": "Sulfonamide/Sulfa (class allergy)",
                })

        # --- Penicillin -> Cephalosporin cross-reactivity (~2% risk) ---
        # Source: Macy E & Romano A (2014) JACI 133(2):333-34; IDSA Allergy Management 2021
        if any("penicillin" in a for a in allergy_lower):
            if check_cephalosporin_class(med):
                conflicts.append({
                    "medication": med,
                    "allergy": "Penicillin allergy (cross-reactivity risk ~2% with cephalosporins per Macy & Romano 2014 JACI)",
                })

        # --- Generic keyword matching for other allergies ---
        for allergy in allergy_lower:
            # Extract base allergy term (e.g. "sulfa" from "sulfa drugs")
            allergy_base = allergy.split(" ")[0].split("-")[0]
            # Lower the threshold to 3 chars to catch abbreviations like ASA, PCN
            if len(allergy_base) >= 3 and allergy_base in med.lower():
                conflict_entry = {"medication": med, "allergy": allergy}
                if conflict_entry not in conflicts:
                    conflicts.append(conflict_entry)

    return conflicts
