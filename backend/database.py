"""
MedRelay — SQLite Database Layer (aiosqlite)
Persists every completed handoff session with full SBAR data, risk alerts,
rendered report, nurse sign-offs, metadata, admin users, audit log,
and refresh tokens for JWT authentication.
"""

import aiosqlite
import json
import uuid
from datetime import datetime
from pathlib import Path

from backend.auth import hash_password, verify_password, is_bcrypt_hash

DB_PATH = Path(__file__).parent.parent / "medrelay.db"

# ─── Schema ──────────────────────────────────────────────────────────────────
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT    UNIQUE NOT NULL,
    outgoing_nurse      TEXT    DEFAULT '',
    incoming_nurse      TEXT    DEFAULT '',
    patient_name        TEXT    DEFAULT '',
    patient_room        TEXT    DEFAULT '',
    patient_mrn         TEXT    DEFAULT '',
    patient_age         TEXT    DEFAULT '',
    diagnosis           TEXT    DEFAULT '',
    sbar_json           TEXT    DEFAULT '{}',
    alerts_json         TEXT    DEFAULT '[]',
    rendered            TEXT    DEFAULT '',
    high_alert_count    INTEGER DEFAULT 0,
    medium_alert_count  INTEGER DEFAULT 0,
    low_alert_count     INTEGER DEFAULT 0,
    signed_by_outgoing  INTEGER DEFAULT 0,
    signed_by_incoming  INTEGER DEFAULT 0,
    signed_at           TEXT    DEFAULT NULL,
    timestamp           TEXT    NOT NULL,
    created_at          TEXT    NOT NULL,
    is_demo             INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS admin_users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    UNIQUE NOT NULL,
    username    TEXT    UNIQUE NOT NULL,
    display_name TEXT   DEFAULT '',
    role        TEXT    DEFAULT 'nurse',
    pin_hash    TEXT    NOT NULL,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT    NOT NULL,
    last_login  TEXT    DEFAULT NULL,
    password_changed_at TEXT DEFAULT NULL,
    failed_login_count  INTEGER DEFAULT 0,
    locked_until        TEXT    DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id    TEXT    UNIQUE NOT NULL,
    user_id     TEXT    NOT NULL,
    token_hash  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    revoked     INTEGER DEFAULT 0,
    revoked_at  TEXT    DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id      TEXT    UNIQUE NOT NULL,
    user_id     TEXT    DEFAULT '',
    username    TEXT    DEFAULT 'system',
    action      TEXT    NOT NULL,
    target_type TEXT    DEFAULT '',
    target_id   TEXT    DEFAULT '',
    details     TEXT    DEFAULT '',
    ip_address  TEXT    DEFAULT '',
    timestamp   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS system_settings (
    key         TEXT    PRIMARY KEY,
    value       TEXT    DEFAULT '',
    updated_at  TEXT    NOT NULL,
    updated_by  TEXT    DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_sessions_patient ON sessions(patient_name);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_hash ON refresh_tokens(token_hash);
"""

async def init_db() -> None:
    """Create the database file and tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_INIT_SQL)
        await db.commit()

        # ── Migrate schema: add new columns if missing ────────────────────
        try:
            await db.execute("SELECT password_changed_at FROM admin_users LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE admin_users ADD COLUMN password_changed_at TEXT DEFAULT NULL")
            await db.commit()
        try:
            await db.execute("SELECT failed_login_count FROM admin_users LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE admin_users ADD COLUMN failed_login_count INTEGER DEFAULT 0")
            await db.commit()
        try:
            await db.execute("SELECT locked_until FROM admin_users LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE admin_users ADD COLUMN locked_until TEXT DEFAULT NULL")
            await db.commit()
        try:
            await db.execute("SELECT role FROM admin_users LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE admin_users ADD COLUMN role TEXT DEFAULT 'nurse'")
            await db.commit()
            # Existing admin user should keep admin role
            await db.execute("UPDATE admin_users SET role = 'admin' WHERE username = 'admin'")
            await db.commit()

        # ── Seed default admin user if none exists ────────────────────────
        cur = await db.execute("SELECT COUNT(*) FROM admin_users WHERE role='admin'")
        row = await cur.fetchone()
        count = row[0] if row else 0
        if count == 0:
            now = datetime.now().isoformat()
            await db.execute(
                "INSERT INTO admin_users (user_id, username, display_name, role, pin_hash, created_at, password_changed_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), "admin", "System Administrator", "admin", hash_password("admin1234"), now, now),
            )
            await db.commit()
            print("[DB] Seeded default admin user (password: admin1234)")
        else:
            # ── Migrate legacy SHA-256 passwords to bcrypt ────────────────
            cur = await db.execute("SELECT user_id, pin_hash FROM admin_users")
            rows = await cur.fetchall()
            for uid, phash in rows:
                if phash and not is_bcrypt_hash(phash):
                    # Re-hash with bcrypt using legacy PIN "1234" as placeholder
                    # Users will need to reset passwords after migration
                    print(f"[DB] Legacy password detected for user {uid} — requires password reset")

        # ── Seed default settings if empty ────────────────────────────────
        cur = await db.execute("SELECT COUNT(*) FROM system_settings")
        row = await cur.fetchone()
        scount = row[0] if row else 0
        if scount == 0:
            now = datetime.now().isoformat()
            defaults = [
                ("hospital_name", "MedRelay General Hospital", now),
                ("department", "Critical Care", now),
                ("auto_demo_enabled", "true", now),
                ("session_retention_days", "90", now),
                ("require_dual_signoff", "true", now),
            ]
            await db.executemany(
                "INSERT INTO system_settings (key, value, updated_at) VALUES (?,?,?)",
                defaults,
            )
            await db.commit()
            print("[DB] Seeded default system settings")

    print(f"[DB] Initialized at {DB_PATH}")


async def save_session(final_report) -> str:
    """
    Persist a completed handoff FinalReport to the database.
    Returns the session_id string.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    sbar = final_report.sbar
    alerts = final_report.alerts

    high   = sum(1 for a in alerts if a.severity == "HIGH")
    medium = sum(1 for a in alerts if a.severity == "MEDIUM")
    low    = sum(1 for a in alerts if a.severity == "LOW")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO sessions (
                session_id, outgoing_nurse, incoming_nurse,
                patient_name, patient_room, patient_mrn, patient_age,
                diagnosis, sbar_json, alerts_json, rendered,
                high_alert_count, medium_alert_count, low_alert_count,
                signed_by_outgoing, signed_by_incoming,
                timestamp, created_at, is_demo
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                session_id,
                final_report.outgoing_nurse,
                final_report.incoming_nurse,
                sbar.patient.name or "",
                sbar.patient.room or "",
                sbar.patient.mrn  or "",
                sbar.patient.age  or "",
                sbar.situation.primary_diagnosis or "",
                json.dumps(sbar.model_dump()),
                json.dumps([a.model_dump() for a in alerts]),
                final_report.rendered or "",
                high, medium, low,
                int(final_report.signed_by_outgoing),
                int(final_report.signed_by_incoming),
                final_report.timestamp,
                now,
                int(final_report.is_demo),
            ),
        )
        await db.commit()

    return session_id


async def update_signoff(session_id: str, outgoing: bool, incoming: bool) -> bool:
    """Update the sign-off status for a session. Returns True if row was found."""
    signed_at = datetime.now().isoformat() if (outgoing and incoming) else None
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            UPDATE sessions
            SET signed_by_outgoing = ?,
                signed_by_incoming = ?,
                signed_at = ?
            WHERE session_id = ?
            """,
            (int(outgoing), int(incoming), signed_at, session_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_sessions(limit: int = 50) -> list[dict]:
    """Return a summary list of the most recent sessions."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT session_id, outgoing_nurse, incoming_nurse,
                   patient_name, patient_room, patient_mrn, diagnosis,
                   high_alert_count, medium_alert_count, low_alert_count,
                   signed_by_outgoing, signed_by_incoming, signed_at,
                   timestamp, is_demo
            FROM sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            # Normalize SQLite integers to booleans for the frontend
            d["signed_by_outgoing"] = bool(d["signed_by_outgoing"])
            d["signed_by_incoming"] = bool(d["signed_by_incoming"])
            d["is_demo"] = bool(d["is_demo"])
            results.append(d)
        return results


async def get_session(session_id: str) -> dict | None:
    """Return the full session record including SBAR JSON and rendered report."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        # Parse JSON fields back into Python objects
        d["sbar_json"]    = json.loads(d["sbar_json"])
        d["alerts_json"]  = json.loads(d["alerts_json"])
        # Normalize SQLite integers to booleans
        d["signed_by_outgoing"] = bool(d["signed_by_outgoing"])
        d["signed_by_incoming"] = bool(d["signed_by_incoming"])
        d["is_demo"] = bool(d["is_demo"])
        return d


async def delete_session(session_id: str) -> bool:
    """Delete a session by ID. Returns True if deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        await db.commit()
        return cur.rowcount > 0


async def get_stats() -> dict:
    """Return aggregate statistics across all sessions."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT
                COUNT(*)                   AS total_sessions,
                COALESCE(SUM(is_demo), 0)  AS demo_sessions,
                COALESCE(SUM(high_alert_count), 0) AS total_high_alerts,
                COALESCE(SUM(CASE WHEN signed_by_outgoing = 1 AND signed_by_incoming = 1 THEN 1 ELSE 0 END), 0) AS fully_signed,
                MIN(timestamp)             AS first_session,
                MAX(timestamp)             AS last_session
            FROM sessions
            """
        )
        row = await cur.fetchone()
        return dict(row) if row else {}


async def get_analytics() -> dict:
    """Rich analytics data for the dashboard."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Daily session counts (last 30 days)
        cur = await db.execute("""
            SELECT DATE(timestamp) as day, COUNT(*) as count
            FROM sessions GROUP BY DATE(timestamp) ORDER BY day ASC LIMIT 30
        """)
        daily = [dict(r) for r in await cur.fetchall()]

        # Alert severity totals
        cur = await db.execute("""
            SELECT COALESCE(SUM(high_alert_count),0) as high,
                   COALESCE(SUM(medium_alert_count),0) as medium,
                   COALESCE(SUM(low_alert_count),0) as low
            FROM sessions
        """)
        severity_row = await cur.fetchone()
        severity = dict(severity_row) if severity_row else {"high": 0, "medium": 0, "low": 0}

        # Sign-off compliance
        cur = await db.execute("""
            SELECT COUNT(*) as total,
                COALESCE(SUM(CASE WHEN signed_by_outgoing=1 AND signed_by_incoming=1 THEN 1 ELSE 0 END),0) as fully_signed,
                COALESCE(SUM(CASE WHEN signed_by_outgoing=1 OR signed_by_incoming=1 THEN 1 ELSE 0 END),0) as partially_signed,
                COALESCE(SUM(CASE WHEN signed_by_outgoing=0 AND signed_by_incoming=0 THEN 1 ELSE 0 END),0) as unsigned
            FROM sessions
        """)
        signoff_row = await cur.fetchone()
        signoff = dict(signoff_row) if signoff_row else {"total": 0, "fully_signed": 0, "partially_signed": 0, "unsigned": 0}

        # Hour-of-day distribution
        cur = await db.execute("""
            SELECT CAST(SUBSTR(timestamp,12,2) AS INTEGER) as hour, COUNT(*) as count
            FROM sessions WHERE timestamp IS NOT NULL AND LENGTH(timestamp)>=13
            GROUP BY hour ORDER BY hour
        """)
        hourly = [dict(r) for r in await cur.fetchall()]

        # Top diagnoses
        cur = await db.execute("""
            SELECT diagnosis, COUNT(*) as count
            FROM sessions WHERE diagnosis!='' GROUP BY diagnosis ORDER BY count DESC LIMIT 8
        """)
        diagnoses = [dict(r) for r in await cur.fetchall()]

        # Unique patients
        cur = await db.execute(
            "SELECT COUNT(DISTINCT patient_name) as count FROM sessions WHERE patient_name!=''"
        )
        patients_row = await cur.fetchone()
        patients_count = patients_row["count"] if patients_row else 0

        return {
            "daily_sessions": daily,
            "severity_distribution": severity,
            "signoff_compliance": signoff,
            "hourly_distribution": hourly,
            "top_diagnoses": diagnoses,
            "unique_patients": patients_count,
        }


async def get_patient_timeline(patient_name: str) -> list[dict]:
    """Get all sessions for a specific patient, ordered chronologically."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT session_id, outgoing_nurse, incoming_nurse,
                   patient_name, patient_room, patient_mrn, diagnosis,
                   high_alert_count, medium_alert_count, low_alert_count,
                   signed_by_outgoing, signed_by_incoming, timestamp, is_demo
            FROM sessions WHERE LOWER(patient_name) = LOWER(?)
            ORDER BY timestamp ASC
        """, (patient_name,))
        rows = await cur.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["signed_by_outgoing"] = bool(d["signed_by_outgoing"])
            d["signed_by_incoming"] = bool(d["signed_by_incoming"])
            d["is_demo"] = bool(d["is_demo"])
            results.append(d)
        return results


async def get_patients() -> list[dict]:
    """Get unique patient list with session count."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT patient_name, patient_mrn, patient_room,
                   COUNT(*) as session_count,
                   MAX(timestamp) as last_handoff,
                   SUM(high_alert_count) as total_high_alerts
            FROM sessions WHERE patient_name!=''
            GROUP BY LOWER(patient_name) ORDER BY last_handoff DESC
        """)
        return [dict(r) for r in await cur.fetchall()]


# ─── Admin: Authentication ───────────────────────────────────────────────────

async def admin_login(username: str, password: str) -> dict | None:
    """
    Validate admin login with bcrypt. Returns user dict or None.
    Also handles legacy SHA-256 password migration to bcrypt.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM admin_users WHERE username = ? AND is_active = 1",
            (username,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)

        # Verify password
        if not verify_password(password, d["pin_hash"]):
            # Increment failed login count
            await db.execute(
                "UPDATE admin_users SET failed_login_count = COALESCE(failed_login_count, 0) + 1 WHERE user_id = ?",
                (d["user_id"],),
            )
            await db.commit()
            return None

        # If legacy SHA-256, migrate to bcrypt on successful login
        if not is_bcrypt_hash(d["pin_hash"]):
            new_hash = hash_password(password)
            await db.execute(
                "UPDATE admin_users SET pin_hash = ? WHERE user_id = ?",
                (new_hash, d["user_id"]),
            )
            await db.commit()
            print(f"[DB] Migrated password to bcrypt for user {username}")

        # Reset failed login count and update last_login
        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE admin_users SET last_login = ?, failed_login_count = 0, locked_until = NULL WHERE user_id = ?",
            (now, d["user_id"]),
        )
        await db.commit()

        d.pop("pin_hash", None)
        d["is_active"] = bool(d["is_active"])
        return d


# ─── Admin: User Management ─────────────────────────────────────────────────

async def get_admin_users() -> list[dict]:
    """Get all admin users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT user_id, username, display_name, role, is_active, created_at, last_login FROM admin_users ORDER BY created_at ASC"
        )
        rows = await cur.fetchall()
        return [dict(r) | {"is_active": bool(dict(r)["is_active"])} for r in rows]


async def create_admin_user(username: str, display_name: str, role: str, password: str) -> dict:
    """Create a new admin user with bcrypt-hashed password."""
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO admin_users (user_id, username, display_name, role, pin_hash, created_at, password_changed_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, username, display_name, role, hash_password(password), now, now),
        )
        await db.commit()
    return {"user_id": user_id, "username": username, "display_name": display_name, "role": role, "created_at": now}


async def update_admin_user(user_id: str, **kwargs) -> bool:
    """Update admin user fields. Supports: display_name, role, is_active, password."""
    sets = []
    vals = []
    for key in ("display_name", "role", "is_active"):
        if key in kwargs:
            sets.append(f"{key} = ?")
            vals.append(int(kwargs[key]) if key == "is_active" else kwargs[key])
    if "pin" in kwargs and kwargs["pin"]:
        sets.append("pin_hash = ?")
        vals.append(hash_password(kwargs["pin"]))
        sets.append("password_changed_at = ?")
        vals.append(datetime.now().isoformat())
    if "password" in kwargs and kwargs["password"]:
        sets.append("pin_hash = ?")
        vals.append(hash_password(kwargs["password"]))
        sets.append("password_changed_at = ?")
        vals.append(datetime.now().isoformat())
    if not sets:
        return False
    vals.append(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(f"UPDATE admin_users SET {', '.join(sets)} WHERE user_id = ?", vals)
        await db.commit()
        return cur.rowcount > 0


async def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """Change a user's password after verifying the old one."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT pin_hash FROM admin_users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return False
        if not verify_password(old_password, row["pin_hash"]):
            return False
        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE admin_users SET pin_hash = ?, password_changed_at = ? WHERE user_id = ?",
            (hash_password(new_password), now, user_id),
        )
        await db.commit()
        return True


async def delete_admin_user(user_id: str) -> bool:
    """Delete an admin user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM admin_users WHERE user_id = ?", (user_id,))
        await db.commit()
        return cur.rowcount > 0


# ─── Admin: Audit Log ────────────────────────────────────────────────────────

async def add_audit_log(username: str, action: str, target_type: str = "", target_id: str = "", details: str = "") -> None:
    """Record an audit log entry."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO audit_log (log_id, username, action, target_type, target_id, details, timestamp) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), username, action, target_type, target_id, details, datetime.now().isoformat()),
        )
        await db.commit()


async def get_audit_log(limit: int = 100) -> list[dict]:
    """Return recent audit log entries."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]


# ─── Admin: System Settings ──────────────────────────────────────────────────

async def get_settings() -> dict:
    """Return all system settings as a dict."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT key, value FROM system_settings")
        return {r["key"]: r["value"] for r in await cur.fetchall()}


async def update_settings(settings: dict, updated_by: str = "admin") -> None:
    """Update multiple system settings."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in settings.items():
            await db.execute(
                "INSERT OR REPLACE INTO system_settings (key, value, updated_at, updated_by) VALUES (?,?,?,?)",
                (key, str(value), now, updated_by),
            )
        await db.commit()


# ─── Admin: Bulk Operations ─────────────────────────────────────────────────

async def bulk_delete_sessions(session_ids: list[str]) -> int:
    """Delete multiple sessions. Returns count deleted."""
    if not session_ids:
        return 0
    placeholders = ",".join("?" for _ in session_ids)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(f"DELETE FROM sessions WHERE session_id IN ({placeholders})", session_ids)
        await db.commit()
        return cur.rowcount


async def purge_demo_sessions() -> int:
    """Delete all demo sessions. Returns count deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM sessions WHERE is_demo = 1")
        await db.commit()
        return cur.rowcount


# ─── Refresh Tokens ──────────────────────────────────────────────────────────

async def store_refresh_token(user_id: str, token_hash: str, expires_at: str) -> str:
    """Store a refresh token hash. Returns the token_id."""
    token_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO refresh_tokens (token_id, user_id, token_hash, expires_at, created_at) VALUES (?,?,?,?,?)",
            (token_id, user_id, token_hash, expires_at, now),
        )
        await db.commit()
    return token_id


async def validate_refresh_token(token_hash: str) -> dict | None:
    """Check if a refresh token hash is valid (not revoked, not expired)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM refresh_tokens WHERE token_hash = ? AND revoked = 0",
            (token_hash,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        # Check expiry
        try:
            exp = datetime.fromisoformat(d["expires_at"])
            now = datetime.now(exp.tzinfo) if exp.tzinfo else datetime.now()
            if exp < now:
                return None
        except (ValueError, TypeError):
            return None
        return d


async def revoke_refresh_token(token_hash: str) -> bool:
    """Revoke a refresh token."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE refresh_tokens SET revoked = 1, revoked_at = ? WHERE token_hash = ?",
            (now, token_hash),
        )
        await db.commit()
        return cur.rowcount > 0


async def revoke_all_user_tokens(user_id: str) -> int:
    """Revoke all refresh tokens for a user (e.g., on password change)."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE refresh_tokens SET revoked = 1, revoked_at = ? WHERE user_id = ? AND revoked = 0",
            (now, user_id),
        )
        await db.commit()
        return cur.rowcount


async def cleanup_expired_tokens() -> int:
    """Remove expired and revoked refresh tokens."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM refresh_tokens WHERE revoked = 1 OR expires_at < ?",
            (now,),
        )
        await db.commit()
        return cur.rowcount


async def get_user_by_id(user_id: str) -> dict | None:
    """Fetch a user by user_id. Returns dict without pin_hash."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT user_id, username, display_name, role, is_active, created_at, last_login, password_changed_at FROM admin_users WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["is_active"] = bool(d["is_active"])
        return d


# ─── Enhanced Analytics ──────────────────────────────────────────────────────

async def get_nurse_analytics() -> dict:
    """Per-nurse handoff performance: sessions conducted, alert rates, sign-off rates."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Outgoing nurse stats
        cur = await conn.execute("""
            SELECT outgoing_nurse as nurse,
                   COUNT(*) as total_handoffs,
                   COALESCE(SUM(high_alert_count), 0) as high_alerts,
                   COALESCE(SUM(medium_alert_count), 0) as medium_alerts,
                   COALESCE(SUM(low_alert_count), 0) as low_alerts,
                   COALESCE(SUM(CASE WHEN signed_by_outgoing=1 AND signed_by_incoming=1 THEN 1 ELSE 0 END), 0) as fully_signed,
                   MIN(timestamp) as first_handoff,
                   MAX(timestamp) as last_handoff
            FROM sessions WHERE outgoing_nurse != ''
            GROUP BY LOWER(outgoing_nurse) ORDER BY total_handoffs DESC
        """)
        outgoing = [dict(r) for r in await cur.fetchall()]

        # Incoming nurse stats
        cur = await conn.execute("""
            SELECT incoming_nurse as nurse,
                   COUNT(*) as total_received,
                   COALESCE(SUM(CASE WHEN signed_by_incoming=1 THEN 1 ELSE 0 END), 0) as signed_off,
                   MAX(timestamp) as last_received
            FROM sessions WHERE incoming_nurse != ''
            GROUP BY LOWER(incoming_nurse) ORDER BY total_received DESC
        """)
        incoming = [dict(r) for r in await cur.fetchall()]

        # Top nurse pairs
        cur = await conn.execute("""
            SELECT outgoing_nurse || ' → ' || incoming_nurse as pair,
                   COUNT(*) as count
            FROM sessions WHERE outgoing_nurse != '' AND incoming_nurse != ''
            GROUP BY LOWER(outgoing_nurse), LOWER(incoming_nurse)
            ORDER BY count DESC LIMIT 10
        """)
        pairs = [dict(r) for r in await cur.fetchall()]

        return {
            "outgoing_nurses": outgoing,
            "incoming_nurses": incoming,
            "top_pairs": pairs,
        }


async def get_trend_analytics() -> dict:
    """Weekly and monthly trend data with period-over-period comparisons."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Weekly sessions (last 12 weeks)
        cur = await conn.execute("""
            SELECT strftime('%Y-W%W', timestamp) as week,
                   COUNT(*) as sessions,
                   COALESCE(SUM(high_alert_count), 0) as high_alerts,
                   COALESCE(AVG(high_alert_count + medium_alert_count + low_alert_count), 0) as avg_alerts_per_session,
                   COALESCE(SUM(CASE WHEN signed_by_outgoing=1 AND signed_by_incoming=1 THEN 1 ELSE 0 END), 0) as fully_signed
            FROM sessions
            WHERE timestamp >= date('now', '-84 days')
            GROUP BY week ORDER BY week ASC
        """)
        weekly = [dict(r) for r in await cur.fetchall()]

        # Monthly sessions (last 12 months)
        cur = await conn.execute("""
            SELECT strftime('%Y-%m', timestamp) as month,
                   COUNT(*) as sessions,
                   COALESCE(SUM(high_alert_count), 0) as high_alerts,
                   COALESCE(AVG(high_alert_count + medium_alert_count + low_alert_count), 0) as avg_alerts_per_session,
                   COALESCE(SUM(CASE WHEN signed_by_outgoing=1 AND signed_by_incoming=1 THEN 1 ELSE 0 END), 0) as fully_signed,
                   COUNT(DISTINCT patient_name) as unique_patients
            FROM sessions
            WHERE timestamp >= date('now', '-365 days')
            GROUP BY month ORDER BY month ASC
        """)
        monthly = [dict(r) for r in await cur.fetchall()]

        # Alert trend (last 30 days, daily)
        cur = await conn.execute("""
            SELECT DATE(timestamp) as day,
                   COALESCE(SUM(high_alert_count), 0) as high,
                   COALESCE(SUM(medium_alert_count), 0) as medium,
                   COALESCE(SUM(low_alert_count), 0) as low
            FROM sessions
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY day ORDER BY day ASC
        """)
        alert_trend = [dict(r) for r in await cur.fetchall()]

        return {
            "weekly": weekly,
            "monthly": monthly,
            "alert_trend": alert_trend,
        }


async def get_quality_analytics() -> dict:
    """Handoff quality scoring based on SBAR completeness and compliance metrics."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Overall quality metrics
        cur = await conn.execute("""
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN signed_by_outgoing=1 AND signed_by_incoming=1 THEN 1 ELSE 0 END), 0) as dual_signed,
                COALESCE(SUM(CASE WHEN patient_name != '' THEN 1 ELSE 0 END), 0) as has_patient_name,
                COALESCE(SUM(CASE WHEN patient_mrn != '' THEN 1 ELSE 0 END), 0) as has_mrn,
                COALESCE(SUM(CASE WHEN diagnosis != '' THEN 1 ELSE 0 END), 0) as has_diagnosis,
                COALESCE(SUM(CASE WHEN patient_room != '' THEN 1 ELSE 0 END), 0) as has_room,
                COALESCE(SUM(CASE WHEN rendered != '' THEN 1 ELSE 0 END), 0) as has_report,
                COALESCE(AVG(high_alert_count + medium_alert_count + low_alert_count), 0) as avg_alerts
            FROM sessions
        """)
        row = await cur.fetchone()
        overall = dict(row) if row else {}
        total = overall.get("total", 0) or 1

        # Compute quality score (0-100)
        completeness_score = (
            (overall.get("has_patient_name", 0) / total) * 20 +
            (overall.get("has_mrn", 0) / total) * 15 +
            (overall.get("has_diagnosis", 0) / total) * 25 +
            (overall.get("has_room", 0) / total) * 10 +
            (overall.get("has_report", 0) / total) * 10 +
            (overall.get("dual_signed", 0) / total) * 20
        )

        # Quality trend (weekly)
        cur = await conn.execute("""
            SELECT strftime('%Y-W%W', timestamp) as week,
                   COUNT(*) as total,
                   COALESCE(SUM(CASE WHEN signed_by_outgoing=1 AND signed_by_incoming=1 THEN 1 ELSE 0 END), 0) as dual_signed,
                   COALESCE(SUM(CASE WHEN patient_name!='' AND diagnosis!='' AND patient_mrn!='' THEN 1 ELSE 0 END), 0) as complete_records,
                   COALESCE(AVG(high_alert_count), 0) as avg_high_alerts
            FROM sessions
            WHERE timestamp >= date('now', '-84 days')
            GROUP BY week ORDER BY week ASC
        """)
        weekly_quality = []
        for r in await cur.fetchall():
            d = dict(r)
            wk_total = d["total"] or 1
            d["quality_score"] = round(
                (d["complete_records"] / wk_total) * 60 +
                (d["dual_signed"] / wk_total) * 40,
                1,
            )
            weekly_quality.append(d)

        # Completeness breakdown
        completeness = {
            "patient_name": round((overall.get("has_patient_name", 0) / total) * 100, 1),
            "mrn": round((overall.get("has_mrn", 0) / total) * 100, 1),
            "diagnosis": round((overall.get("has_diagnosis", 0) / total) * 100, 1),
            "room": round((overall.get("has_room", 0) / total) * 100, 1),
            "report_generated": round((overall.get("has_report", 0) / total) * 100, 1),
            "dual_signoff": round((overall.get("dual_signed", 0) / total) * 100, 1),
        }

        return {
            "overall_quality_score": round(completeness_score, 1),
            "total_sessions": overall.get("total", 0),
            "avg_alerts_per_session": round(overall.get("avg_alerts", 0), 2),
            "completeness": completeness,
            "weekly_quality": weekly_quality,
        }
