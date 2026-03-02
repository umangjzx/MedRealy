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
    """Return True if the medication belongs to the penicillin antibiotic class."""
    penicillin_keywords = [
        "penicillin", "amoxicillin", "ampicillin", "piperacillin",
        "tazobactam", "pip-tazo", "nafcillin", "oxacillin",
        "dicloxacillin", "cloxacillin", "augmentin",
    ]
    med_lower = medication.lower()
    return any(kw in med_lower for kw in penicillin_keywords)


async def check_allergy_drug_conflict(
    medications: list[str], allergies: list[str]
) -> list[dict]:
    """
    Cross-reference medications with allergies.
    Returns a list of conflict dicts: {"medication": str, "allergy": str}.
    """
    conflicts = []
    allergy_lower = [a.lower() for a in allergies]

    for med in medications:
        # Check for penicillin class conflict
        if any("penicillin" in a for a in allergy_lower):
            if check_penicillin_class(med):
                conflicts.append({
                    "medication": med,
                    "allergy": "Penicillin (class allergy)",
                })

        # Generic keyword matching for other allergies
        for allergy in allergy_lower:
            # Extract base allergy term (e.g. "sulfa" from "sulfa drugs")
            allergy_base = allergy.split(" ")[0].split("-")[0]
            # Lower the threshold to 3 chars to catch abbreviations like ASA, PCN
            if len(allergy_base) >= 3 and allergy_base in med.lower():
                conflict_entry = {"medication": med, "allergy": allergy}
                if conflict_entry not in conflicts:
                    conflicts.append(conflict_entry)

    return conflicts
