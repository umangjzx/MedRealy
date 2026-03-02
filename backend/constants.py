"""
MedRelay — Shared Constants
"""

# ── Role-Based Access Control ─────────────────────────────────────────────────

ROLES = ("admin", "supervisor", "charge_nurse", "nurse")

# Permissions granted to each role (cumulative via hierarchy)
ROLE_PERMISSIONS = {
    "admin": {
        "manage_users", "manage_settings", "view_audit", "manage_sessions",
        "purge_demos", "bulk_delete", "view_analytics", "view_sessions",
        "create_handoff", "sign_off", "import_excel", "change_any_password",
        "assign_roles", "view_all_patients", "export_data",
    },
    "supervisor": {
        "view_audit", "view_analytics", "view_sessions", "manage_sessions",
        "create_handoff", "sign_off", "import_excel", "view_all_patients",
        "export_data",
    },
    "charge_nurse": {
        "view_analytics", "view_sessions", "create_handoff", "sign_off",
        "import_excel", "view_all_patients", "export_data",
    },
    "nurse": {
        "view_sessions", "create_handoff", "sign_off",
    },
}

ROLE_DISPLAY = {
    "admin": "Administrator",
    "supervisor": "Supervisor",
    "charge_nurse": "Charge Nurse",
    "nurse": "Nurse",
}


def role_has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: str) -> set:
    """Return the permission set for a role."""
    return ROLE_PERMISSIONS.get(role, set())


# Demo transcript injected when Demo Mode is triggered or when no real audio is captured
DEMO_TRANSCRIPT = """Speaker A (Outgoing): Alright, so we have Sarah Mitchell in ICU 4B, 67-year-old female admitted yesterday with septic shock from pneumonia. She has been on norepi since 2am, currently at 0.1 mics per kilo. She got vanc and pip-tazo overnight. Oh, she is allergic to penicillin by the way, I think that is in the chart. BP is still low, last was 88 over 54, heart rate 118. Sat is sitting around 91% on high flow. Temp was 38.9 this morning. We are waiting on blood cultures and a repeat lactate. If MAP drops below 65 or sats go below 88, call the rapid response.
Speaker B (Incoming): Got it. Any family at the bedside?
Speaker A: Daughter was here earlier, she has healthcare proxy. She has been updated."""
