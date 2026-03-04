"""
Seed script: creates 15 nurse accounts and 40 patients for the scheduling system.
Run once from the project root:
    python -m scripts.seed_scheduling
"""

import asyncio
import sys
import os

# ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, create_admin_user, create_patient

# ── 15 Nurses ────────────────────────────────────────────────────────
NURSES = [
    ("nurse_sarah",    "Sarah Johnson",    "nurse"),
    ("nurse_michael",  "Michael Chen",     "nurse"),
    ("nurse_priya",    "Priya Patel",      "nurse"),
    ("nurse_james",    "James Williams",   "nurse"),
    ("nurse_maria",    "Maria Garcia",     "nurse"),
    ("nurse_david",    "David Kim",        "nurse"),
    ("nurse_emily",    "Emily Thompson",   "nurse"),
    ("nurse_raj",      "Raj Sharma",       "nurse"),
    ("nurse_lisa",     "Lisa Anderson",    "nurse"),
    ("nurse_omar",     "Omar Hassan",      "nurse"),
    ("nurse_jessica",  "Jessica Martinez", "nurse"),
    ("nurse_kevin",    "Kevin O'Brien",    "nurse"),
    ("nurse_aisha",    "Aisha Mohammed",   "nurse"),
    ("nurse_daniel",   "Daniel Lee",       "nurse"),
    ("nurse_natasha",  "Natasha Volkov",   "nurse"),
]

# ── 40 Patients (realistic hospital mix of acuity 1-5) ──────────────
PATIENTS = [
    # Acuity 5 – Critical (4 patients)
    ("Robert Martinez",  "MRN-1001", "ICU",  "101-A", 5, "Septic shock, multi-organ failure"),
    ("Helen Park",       "MRN-1002", "ICU",  "102-A", 5, "Acute respiratory distress syndrome"),
    ("Frank DiMaggio",   "MRN-1003", "ICU",  "103-A", 5, "Status post cardiac arrest – hypothermia protocol"),
    ("Anita Desai",      "MRN-1004", "ICU",  "104-A", 5, "Severe traumatic brain injury"),

    # Acuity 4 – High (8 patients)
    ("George Liu",       "MRN-1005", "3N",   "301-A", 4, "Post-CABG day 1"),
    ("Patricia Brown",   "MRN-1006", "3N",   "301-B", 4, "Acute myocardial infarction – on heparin drip"),
    ("Samuel Okafor",    "MRN-1007", "3N",   "302-A", 4, "Diabetic ketoacidosis"),
    ("Diana Russo",      "MRN-1008", "4S",   "401-A", 4, "Post-op craniotomy for meningioma"),
    ("Hector Vargas",    "MRN-1009", "4S",   "401-B", 4, "GI bleed – active transfusion"),
    ("Yun-Hee Choi",     "MRN-1010", "4S",   "402-A", 4, "Severe pneumonia with BiPAP"),
    ("Thomas Mitchell",  "MRN-1011", "3N",   "302-B", 4, "Acute pancreatitis – NPO with TPN"),
    ("Fatima Al-Rashid", "MRN-1012", "4S",   "402-B", 4, "Post-op hip fracture ORIF – on PCA pump"),

    # Acuity 3 – Moderate (14 patients)
    ("Linda Foster",     "MRN-1013", "5E",   "501-A", 3, "CHF exacerbation – IV diuretics"),
    ("Edward Nakamura",  "MRN-1014", "5E",   "501-B", 3, "COPD exacerbation"),
    ("Carmen Reyes",     "MRN-1015", "5E",   "502-A", 3, "Cellulitis – IV antibiotics"),
    ("William Harris",   "MRN-1016", "5E",   "502-B", 3, "Post-op appendectomy day 1"),
    ("Grace Mbeki",      "MRN-1017", "5W",   "510-A", 3, "New-onset atrial fibrillation"),
    ("Jack Sullivan",    "MRN-1018", "5W",   "510-B", 3, "Acute kidney injury – stage 2"),
    ("Mei-Ling Wu",      "MRN-1019", "5W",   "511-A", 3, "Pneumothorax – chest tube in place"),
    ("Brian Kowalski",   "MRN-1020", "5W",   "511-B", 3, "Deep vein thrombosis – on anticoagulation"),
    ("Sofia Petrov",     "MRN-1021", "6N",   "601-A", 3, "Post-op cholecystectomy day 1"),
    ("Anthony Graves",   "MRN-1022", "6N",   "601-B", 3, "Hypertensive urgency"),
    ("Nora Ibrahim",     "MRN-1023", "6N",   "602-A", 3, "Uncontrolled diabetes – insulin titration"),
    ("Peter Chang",      "MRN-1024", "6N",   "602-B", 3, "Small bowel obstruction – conservative mgmt"),
    ("Ruby Washington",  "MRN-1025", "6S",   "610-A", 3, "Urinary tract infection with bacteremia"),
    ("Marco Bianchi",    "MRN-1026", "6S",   "610-B", 3, "Alcohol withdrawal – CIWA protocol"),

    # Acuity 2 – Low (10 patients)
    ("Dorothy Evans",    "MRN-1027", "7E",   "701-A", 2, "Stable angina – observation"),
    ("Harold Jenkins",   "MRN-1028", "7E",   "701-B", 2, "Post-op hernia repair day 2 – ambulating"),
    ("Amara Ndiaye",     "MRN-1029", "7E",   "702-A", 2, "Iron-deficiency anemia – transfusion complete"),
    ("Philip Rogers",    "MRN-1030", "7E",   "702-B", 2, "Pneumonia – transition to oral antibiotics"),
    ("Janet Kim",        "MRN-1031", "7W",   "710-A", 2, "Stable NSTEMI – awaiting cath lab"),
    ("Douglas Price",    "MRN-1032", "7W",   "710-B", 2, "Post-op knee replacement day 3"),
    ("Irene Sato",       "MRN-1033", "7W",   "711-A", 2, "Mild diverticulitis – IV antibiotics"),
    ("Raymond Torres",   "MRN-1034", "7W",   "711-B", 2, "Syncope workup – telemetry monitoring"),
    ("Cynthia Brooks",   "MRN-1035", "8N",   "801-A", 2, "Asthma exacerbation – improving"),
    ("Walter Schmidt",   "MRN-1036", "8N",   "801-B", 2, "Elective bowel resection pre-op"),

    # Acuity 1 – Minimal (4 patients)
    ("Beverly Adams",    "MRN-1037", "8N",   "802-A", 1, "Observation – chest pain ruled out"),
    ("Eugene Campbell",  "MRN-1038", "8N",   "802-B", 1, "Social admission – awaiting placement"),
    ("Margaret Dunn",    "MRN-1039", "8S",   "810-A", 1, "Post-op cataract – overnight observation"),
    ("Stanley Rivera",   "MRN-1040", "8S",   "810-B", 1, "Dehydration – IV fluids, discharge pending"),
]


async def main():
    await init_db()

    print("=== Seeding 15 Nurse Accounts ===")
    for username, display_name, role in NURSES:
        try:
            user = await create_admin_user(username, display_name, role, "nurse1234")
            print(f"  + {display_name:20s}  @{username:16s}  id={user['user_id'][:8]}…")
        except Exception as e:
            if "UNIQUE" in str(e):
                print(f"  ~ {display_name:20s}  @{username:16s}  (already exists)")
            else:
                print(f"  ! {display_name:20s}  ERROR: {e}")

    print()
    print("=== Seeding 40 Patients ===")
    for name, mrn, room, bed, acuity, diagnosis in PATIENTS:
        try:
            p = await create_patient(name, mrn=mrn, room=room, bed=bed,
                                     acuity=acuity, diagnosis=diagnosis)
            acuity_label = {5: "Critical", 4: "High", 3: "Moderate", 2: "Low", 1: "Minimal"}[acuity]
            print(f"  + {name:22s}  {mrn}  Rm {room:4s}/{bed:6s}  Acuity {acuity} ({acuity_label:8s})  {diagnosis[:40]}")
        except Exception as e:
            if "UNIQUE" in str(e):
                print(f"  ~ {name:22s}  {mrn}  (already exists)")
            else:
                print(f"  ! {name:22s}  ERROR: {e}")

    print()
    print("Done! 15 nurses (password: nurse1234) and 40 patients seeded.")
    print("You can now create a schedule and run auto-assign from the Schedule tab.")


if __name__ == "__main__":
    asyncio.run(main())
