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
    shift_status TEXT   DEFAULT 'active',  -- 'active', 'absent', 'break', 'on_call'
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

-- ── Nurse Scheduling ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS patients_registry (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      TEXT    UNIQUE NOT NULL,
    name            TEXT    NOT NULL,
    mrn             TEXT    DEFAULT '',
    room            TEXT    DEFAULT '',
    bed             TEXT    DEFAULT '',
    acuity          INTEGER DEFAULT 3 CHECK(acuity BETWEEN 1 AND 5),
    diagnosis       TEXT    DEFAULT '',
    admission_date  TEXT    NOT NULL,
    discharge_date  TEXT    DEFAULT NULL,
    status          TEXT    DEFAULT 'admitted',
    notes           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id     TEXT    UNIQUE NOT NULL,
    shift_date      TEXT    NOT NULL,
    shift_type      TEXT    NOT NULL,
    status          TEXT    DEFAULT 'draft',
    created_by      TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    published_at    TEXT    DEFAULT NULL,
    notes           TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS schedule_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   TEXT    UNIQUE NOT NULL,
    schedule_id     TEXT    NOT NULL,
    nurse_user_id   TEXT    NOT NULL,
    patient_id      TEXT    NOT NULL,
    is_primary      INTEGER DEFAULT 1,
    notes           TEXT    DEFAULT '',
    handoff_status  TEXT    DEFAULT 'pending',
    created_at      TEXT    NOT NULL,
    FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id),
    FOREIGN KEY (nurse_user_id) REFERENCES admin_users(user_id),
    FOREIGN KEY (patient_id) REFERENCES patients_registry(patient_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_patient ON sessions(patient_name);
CREATE INDEX IF NOT EXISTS idx_sessions_mrn ON sessions(patient_mrn);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_patients_status ON patients_registry(status);
CREATE INDEX IF NOT EXISTS idx_patients_mrn ON patients_registry(mrn);
CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(shift_date);
CREATE INDEX IF NOT EXISTS idx_assignments_schedule ON schedule_assignments(schedule_id);
CREATE INDEX IF NOT EXISTS idx_assignments_nurse ON schedule_assignments(nurse_user_id);
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

        # ── Migrate schema: add new Agent columns ─────────────────────────
        for col in ["compliance_json", "pharma_json", "trend_json", "educator_json", "debrief_json"]:
            try:
                await db.execute(f"SELECT {col} FROM sessions LIMIT 1")
            except Exception:
                await db.execute(f"ALTER TABLE sessions ADD COLUMN {col} TEXT DEFAULT '{{}}'")
                await db.commit()
                print(f"[DB] Added column {col} to sessions table")

        # ── Migrate schema: add handoff_status to schedule_assignments ────
        try:
            await db.execute("SELECT handoff_status FROM schedule_assignments LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE schedule_assignments ADD COLUMN handoff_status TEXT DEFAULT 'pending'")
            await db.commit()
            print("[DB] Added column handoff_status to schedule_assignments table")

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

    # Serialize new agent outputs
    def _to_json(obj):
        return json.dumps(obj.model_dump()) if obj else "{}"

    compliance_json = _to_json(getattr(final_report, "compliance", None))
    pharma_json     = _to_json(getattr(final_report, "pharma", None))
    trend_json      = _to_json(getattr(final_report, "trend", None))
    educator_json   = _to_json(getattr(final_report, "educator", None))
    debrief_json    = _to_json(getattr(final_report, "debrief", None))
    billing_json    = _to_json(getattr(final_report, "billing", None))
    literature_json = _to_json(getattr(final_report, "literature", None))

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO sessions (
                session_id, outgoing_nurse, incoming_nurse,
                patient_name, patient_room, patient_mrn, patient_age,
                diagnosis, sbar_json, alerts_json, rendered,
                high_alert_count, medium_alert_count, low_alert_count,
                signed_by_outgoing, signed_by_incoming,
                timestamp, created_at, is_demo,
                compliance_json, pharma_json, trend_json, educator_json, debrief_json, billing_json, literature_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                compliance_json,
                pharma_json,
                trend_json,
                educator_json,
                debrief_json,
                billing_json,
                literature_json,
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
        # New agents
        d["compliance"]   = json.loads(d.get("compliance_json") or "{}")
        d["pharma"]       = json.loads(d.get("pharma_json") or "{}")
        d["trend"]        = json.loads(d.get("trend_json") or "{}")
        d["educator"]     = json.loads(d.get("educator_json") or "{}")
        d["debrief"]      = json.loads(d.get("debrief_json") or "{}")

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

        # Detailed Handoff Metrics (Quality, Efficiency, Risk)
        # Fetching bulk sessions to compute advanced metrics in Python
        cur = await db.execute("""
            SELECT alerts_json, debrief_json, timestamp
            FROM sessions
            ORDER BY created_at DESC
            LIMIT 100
        """)
        recent_rows = await cur.fetchall()

        daily_quality = {}   # {YYYY-MM-DD: [scores]}
        daily_words = {}     # {YYYY-MM-DD: [word_counts]} (efficiency proxy)
        risk_heatmap = {}    # {alert_description: count}

        for row in recent_rows:
            try:
                ts_str = row["timestamp"][:10]  # YYYY-MM-DD
                
                # Risk Heatmap
                try:
                    alerts = json.loads(row["alerts_json"])
                    for a in alerts:
                        if isinstance(a, dict) and a.get("severity") == "HIGH":
                            desc = a.get("description", "").split("—")[0].strip()
                            risk_heatmap[desc] = risk_heatmap.get(desc, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

                # Quality & Efficiency Trends
                try:
                    debrief = json.loads(row["debrief_json"])
                    if isinstance(debrief, dict):
                        # Quality (Overall Score)
                        score = debrief.get("overall_score", 0)
                        if score > 0:
                            daily_quality.setdefault(ts_str, []).append(score)
                        
                        # Efficiency (via Clarity/Efficiency scorecard logic or raw word count from structure)
                        # We don't have raw word count in debrief_json top-level, 
                        # but we can infer from "Efficiency" scorecard if available
                        scorecards = debrief.get("scorecards", [])
                        for sc in scorecards:
                            if sc.get("category") == "Efficiency":
                                # Extract word count from finding string if possible? 
                                # Finding: "X words — optimal range..."
                                # Too brittle. Let's just use the efficiency score (0-10)
                                eff_score = sc.get("score", 0)
                                daily_words.setdefault(ts_str, []).append(eff_score)
                except (json.JSONDecodeError, TypeError):
                    pass

            except Exception:
                continue

        # Aggregate Trends
        quality_trend = [
            {"day": day, "avg_score": round(sum(scores)/len(scores), 1)}
            for day, scores in sorted(daily_quality.items())
        ]
        efficiency_trend = [
            {"day": day, "avg_score": round(sum(sc)/len(sc), 1)}
            for day, sc in sorted(daily_words.items())
        ]
        risk_top_5 = sorted(risk_heatmap.items(), key=lambda x: x[1], reverse=True)[:5]
        risk_heatmap_list = [{"alert": k, "count": v} for k, v in risk_top_5]

        return {
            "daily_sessions": daily,
            "severity_distribution": severity,
            "signoff_compliance": signoff,
            "hourly_distribution": hourly,
            "top_diagnoses": diagnoses,
            "unique_patients": patients_count,
            "quality_trend": quality_trend,
            "efficiency_trend": efficiency_trend,
            "risk_heatmap": risk_heatmap_list,
        }


async def get_recent_critical_alerts(limit: int = 5) -> list[dict]:
    """Get the most recent ALERT json snippets where severity=HIGH."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT session_id, alerts_json, timestamp, patient_name 
            FROM sessions 
            WHERE high_alert_count > 0 
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
        
        results = []
        for r in rows:
            try:
                alerts = json.loads(r["alerts_json"])
                # Filter just the high ones
                highs = [a for a in alerts if a.get("severity") == "HIGH"]
                results.append({
                    "session_id": r["session_id"],
                    "timestamp": r["timestamp"],
                    "patient": r["patient_name"],
                    "alerts": highs
                })
            except Exception: pass
        return results

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
            "SELECT user_id, username, display_name, role, is_active, created_at, last_login, shift_status FROM admin_users ORDER BY created_at ASC"
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
    """Update admin user fields. Supports: display_name, role, is_active, password, shift_status."""
    sets = []
    vals = []
    for key in ("display_name", "role", "is_active", "shift_status"):
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


async def get_history_for_trends(mrn: str | None, name: str | None, limit: int = 5) -> list[dict]:
    """Retrieve the most recent handoff sessions for a patient to analyze trends."""
    if not mrn and not name:
        return []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT sbar_json, timestamp, alerts_json
            FROM sessions
            WHERE (patient_mrn = ? AND patient_mrn != '')
               OR (patient_name = ? AND patient_name != '')
            ORDER BY id DESC
            LIMIT ?
        """
        cursor = await db.execute(sql, (mrn or '', name or '', limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  NURSE SCHEDULING
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Patients Registry ────────────────────────────────────────────────────────

async def create_patient(name: str, mrn: str = "", room: str = "", bed: str = "",
                         acuity: int = 3, diagnosis: str = "", notes: str = "",
                         admission_date: str | None = None) -> dict:
    """Register a new patient in the hospital."""
    patient_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    admission = admission_date or now
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """INSERT INTO patients_registry
               (patient_id, name, mrn, room, bed, acuity, diagnosis, admission_date, notes, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (patient_id, name, mrn, room, bed, acuity, diagnosis, admission, notes, "admitted", now, now),
        )
        await conn.commit()
    return {"patient_id": patient_id, "name": name, "mrn": mrn, "room": room, "bed": bed,
            "acuity": acuity, "diagnosis": diagnosis, "admission_date": admission,
            "status": "admitted", "notes": notes, "created_at": now}


async def update_patient(patient_id: str, **kwargs) -> bool:
    """Update patient fields: name, mrn, room, bed, acuity, diagnosis, status, notes, discharge_date."""
    allowed = {"name", "mrn", "room", "bed", "acuity", "diagnosis", "status", "notes", "discharge_date"}
    sets, vals = [], []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(datetime.now().isoformat())
    vals.append(patient_id)
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(f"UPDATE patients_registry SET {', '.join(sets)} WHERE patient_id = ?", vals)
        await conn.commit()
        return cur.rowcount > 0


async def delete_patient(patient_id: str) -> bool:
    """Remove a patient from the registry."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("DELETE FROM patients_registry WHERE patient_id = ?", (patient_id,))
        await conn.commit()
        return cur.rowcount > 0


async def get_patients_registry(status: str | None = None) -> list[dict]:
    """Get all patients, optionally filtered by status."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        if status:
            cur = await conn.execute(
                "SELECT * FROM patients_registry WHERE status = ? ORDER BY room, bed, name", (status,))
        else:
            cur = await conn.execute("SELECT * FROM patients_registry ORDER BY room, bed, name")
        return [dict(r) for r in await cur.fetchall()]


async def get_patient_by_id(patient_id: str) -> dict | None:
    """Look up a single patient."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM patients_registry WHERE patient_id = ?", (patient_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ─── Schedules ────────────────────────────────────────────────────────────────

async def create_schedule(shift_date: str, shift_type: str, created_by: str, notes: str = "") -> dict:
    """Create a new schedule draft."""
    schedule_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """INSERT INTO schedules (schedule_id, shift_date, shift_type, status, created_by, created_at, updated_at, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (schedule_id, shift_date, shift_type, "draft", created_by, now, now, notes),
        )
        await conn.commit()
    return {"schedule_id": schedule_id, "shift_date": shift_date, "shift_type": shift_type,
            "status": "draft", "created_by": created_by, "created_at": now, "notes": notes}


async def get_schedules(shift_date: str | None = None, status: str | None = None) -> list[dict]:
    """List schedules with optional date/status filter."""
    clauses, vals = [], []
    if shift_date:
        clauses.append("shift_date = ?")
        vals.append(shift_date)
    if status:
        clauses.append("status = ?")
        vals.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(f"""
            SELECT s.*, u.display_name as creator_name, u.username as creator_username
            FROM schedules s
            LEFT JOIN admin_users u ON s.created_by = u.user_id
            {where}
            ORDER BY shift_date DESC, CASE shift_type
                WHEN 'day' THEN 1 WHEN 'evening' THEN 2 WHEN 'night' THEN 3 END
        """, vals)
        return [dict(r) for r in await cur.fetchall()]


async def get_schedule(schedule_id: str) -> dict | None:
    """Get a schedule with its assignments + nurse/patient details."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        cur = await conn.execute("""
            SELECT s.*, u.display_name as creator_name, u.username as creator_username
            FROM schedules s
            LEFT JOIN admin_users u ON s.created_by = u.user_id
            WHERE s.schedule_id = ?
        """, (schedule_id,))
        row = await cur.fetchone()
        if not row:
            return None
        sched = dict(row)

        # Fetch assignments with nurse + patient info
        cur = await conn.execute("""
            SELECT sa.*,
                   au.username as nurse_username, au.display_name as nurse_name, au.role as nurse_role,
                   pr.name as patient_name, pr.mrn as patient_mrn, pr.room as patient_room,
                   pr.bed as patient_bed, pr.acuity as patient_acuity, pr.diagnosis as patient_diagnosis
            FROM schedule_assignments sa
            JOIN admin_users au ON sa.nurse_user_id = au.user_id
            JOIN patients_registry pr ON sa.patient_id = pr.patient_id
            WHERE sa.schedule_id = ?
            ORDER BY au.display_name, pr.room, pr.bed
        """, (schedule_id,))
        assignments = [dict(r) for r in await cur.fetchall()]
        sched["assignments"] = assignments
        return sched


async def update_schedule(schedule_id: str, **kwargs) -> bool:
    """Update schedule fields: status, notes, published_at."""
    allowed = {"status", "notes", "published_at"}
    sets, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(datetime.now().isoformat())
    vals.append(schedule_id)
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(f"UPDATE schedules SET {', '.join(sets)} WHERE schedule_id = ?", vals)
        await conn.commit()
        return cur.rowcount > 0


async def delete_schedule(schedule_id: str) -> bool:
    """Delete a schedule and all its assignments."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM schedule_assignments WHERE schedule_id = ?", (schedule_id,))
        cur = await conn.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))
        await conn.commit()
        return cur.rowcount > 0


# ─── Schedule Assignments ────────────────────────────────────────────────────

async def add_assignment(schedule_id: str, nurse_user_id: str, patient_id: str,
                         is_primary: bool = True, notes: str = "") -> dict:
    """Add a single nurse ↔ patient assignment to a schedule."""
    assignment_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """INSERT INTO schedule_assignments
               (assignment_id, schedule_id, nurse_user_id, patient_id, is_primary, notes, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (assignment_id, schedule_id, nurse_user_id, patient_id, int(is_primary), notes, now),
        )
        await conn.commit()
    return {"assignment_id": assignment_id, "schedule_id": schedule_id,
            "nurse_user_id": nurse_user_id, "patient_id": patient_id,
            "is_primary": is_primary, "notes": notes}


async def remove_assignment(assignment_id: str) -> bool:
    """Remove a single assignment."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("DELETE FROM schedule_assignments WHERE assignment_id = ?", (assignment_id,))
        await conn.commit()
        return cur.rowcount > 0


async def clear_schedule_assignments(schedule_id: str) -> int:
    """Remove all assignments for a schedule (before re-generating)."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("DELETE FROM schedule_assignments WHERE schedule_id = ?", (schedule_id,))
        await conn.commit()
        return cur.rowcount


# ─── Auto-Scheduling Algorithm ───────────────────────────────────────────────

async def auto_schedule(schedule_id: str, max_patients_per_nurse: int = 6) -> dict:
    """
    Automatically assign admitted patients to active nurses using an
    acuity-balanced greedy algorithm.

    Strategy:
      1. Fetch all admitted patients sorted by acuity DESC (sickest first).
      2. Fetch all active nurse-role users.
      3. Use a min-heap style approach: assign each patient to the nurse
         with the lowest current total acuity load, respecting the per-nurse cap.
      4. Persist the assignments and return summary.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        now = datetime.now().isoformat()

        # 1. Admitted patients
        cur = await conn.execute(
            "SELECT patient_id, name, acuity, room, bed FROM patients_registry WHERE status = 'admitted' ORDER BY acuity DESC, room, bed"
        )
        patients = [dict(r) for r in await cur.fetchall()]

        # 2. Active nurses (role IN nurse, charge_nurse, supervisor — NOT admin)
        cur = await conn.execute(
            "SELECT user_id, username, display_name, role FROM admin_users WHERE is_active = 1 AND role IN ('nurse', 'charge_nurse', 'supervisor') ORDER BY display_name"
        )
        nurses = [dict(r) for r in await cur.fetchall()]

        if not nurses:
            return {"error": "No active nurses found", "assigned": 0, "unassigned": len(patients)}
        if not patients:
            return {"error": "No admitted patients found", "assigned": 0, "unassigned": 0}

        # 3. Clear existing assignments
        await conn.execute("DELETE FROM schedule_assignments WHERE schedule_id = ?", (schedule_id,))

        # 4. Greedy acuity-balanced assignment
        # Track each nurse's load: {user_id: {"acuity_total": int, "count": int}}
        nurse_load = {n["user_id"]: {"acuity_total": 0, "count": 0, "info": n} for n in nurses}
        assigned = []
        unassigned = []

        for patient in patients:
            # Find the nurse with the lowest acuity load who hasn't hit the cap
            best_nurse_id = None
            best_load = float("inf")
            for uid, load in nurse_load.items():
                if load["count"] < max_patients_per_nurse and load["acuity_total"] < best_load:
                    best_load = load["acuity_total"]
                    best_nurse_id = uid

            if best_nurse_id is None:
                # All nurses at capacity
                unassigned.append(patient)
                continue

            assignment_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO schedule_assignments
                   (assignment_id, schedule_id, nurse_user_id, patient_id, is_primary, notes, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (assignment_id, schedule_id, best_nurse_id, patient["patient_id"], 1, "", now),
            )
            nurse_load[best_nurse_id]["acuity_total"] += patient["acuity"]
            nurse_load[best_nurse_id]["count"] += 1
            assigned.append({"patient": patient["name"], "nurse": nurse_load[best_nurse_id]["info"]["display_name"],
                             "acuity": patient["acuity"]})

        await conn.commit()

        # Build summary per nurse
        nurse_summary = []
        for uid, load in nurse_load.items():
            if load["count"] > 0:
                nurse_summary.append({
                    "nurse": load["info"]["display_name"] or load["info"]["username"],
                    "user_id": uid,
                    "patient_count": load["count"],
                    "total_acuity": load["acuity_total"],
                    "avg_acuity": round(load["acuity_total"] / load["count"], 1) if load["count"] else 0,
                })

        return {
            "assigned": len(assigned),
            "unassigned": len(unassigned),
            "total_patients": len(patients),
            "total_nurses": len(nurses),
            "max_patients_per_nurse": max_patients_per_nurse,
            "nurse_summary": nurse_summary,
            "unassigned_patients": [{"name": p["name"], "acuity": p["acuity"]} for p in unassigned],
        }


async def get_previous_shift_nurse(patient_id: str, shift_date: str, shift_type: str) -> dict | None:
    """
    Find which nurse had this patient in the PREVIOUS shift.
    Shift order: day → evening → night → (next day) day.
    Returns {nurse_user_id, nurse_name, shift_date, shift_type} or None.
    """
    # Determine the previous shift
    if shift_type == "evening":
        prev_type, prev_date = "day", shift_date
    elif shift_type == "night":
        prev_type, prev_date = "evening", shift_date
    else:  # day → previous night
        from datetime import timedelta
        d = datetime.strptime(shift_date, "%Y-%m-%d") - timedelta(days=1)
        prev_type, prev_date = "night", d.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("""
            SELECT sa.nurse_user_id,
                   COALESCE(au.display_name, au.username) AS nurse_name,
                   s.shift_date, s.shift_type
            FROM schedule_assignments sa
            JOIN schedules s ON sa.schedule_id = s.schedule_id
            JOIN admin_users au ON sa.nurse_user_id = au.user_id
            WHERE sa.patient_id = ?
              AND s.shift_date = ?
              AND s.shift_type = ?
              AND s.status IN ('draft', 'published')
            LIMIT 1
        """, (patient_id, prev_date, prev_type))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_nurse_schedule(nurse_user_id: str, shift_date: str | None = None) -> list[dict]:
    """Get a specific nurse's assigned patients across schedules, optionally filtered by date."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        if shift_date:
            cur = await conn.execute("""
                SELECT s.schedule_id, s.shift_date, s.shift_type, s.status,
                       sa.assignment_id, sa.is_primary, sa.notes as assignment_notes,
                       sa.handoff_status,
                       pr.patient_id, pr.name as patient_name, pr.mrn, pr.room, pr.bed,
                       pr.acuity, pr.diagnosis, pr.status as patient_status
                FROM schedule_assignments sa
                JOIN schedules s ON sa.schedule_id = s.schedule_id
                JOIN patients_registry pr ON sa.patient_id = pr.patient_id
                WHERE sa.nurse_user_id = ? AND s.shift_date = ? AND s.status IN ('draft', 'published')
                ORDER BY s.shift_type, pr.acuity DESC, pr.room, pr.bed
            """, (nurse_user_id, shift_date))
        else:
            cur = await conn.execute("""
                SELECT s.schedule_id, s.shift_date, s.shift_type, s.status,
                       sa.assignment_id, sa.is_primary, sa.notes as assignment_notes,
                       sa.handoff_status,
                       pr.patient_id, pr.name as patient_name, pr.mrn, pr.room, pr.bed,
                       pr.acuity, pr.diagnosis, pr.status as patient_status
                FROM schedule_assignments sa
                JOIN schedules s ON sa.schedule_id = s.schedule_id
                JOIN patients_registry pr ON sa.patient_id = pr.patient_id
                WHERE sa.nurse_user_id = ? AND s.status IN ('draft', 'published')
                ORDER BY s.shift_date DESC, s.shift_type, pr.acuity DESC, pr.room, pr.bed
            """, (nurse_user_id,))
        return [dict(r) for r in await cur.fetchall()]


async def get_schedule_stats() -> dict:
    """Get scheduling overview statistics."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Total counts
        cur = await conn.execute("SELECT COUNT(*) as count FROM patients_registry WHERE status = 'admitted'")
        row = await cur.fetchone()
        admitted = row["count"] if row else 0

        cur = await conn.execute("SELECT COUNT(*) as count FROM admin_users WHERE is_active = 1 AND role IN ('nurse', 'charge_nurse', 'supervisor')")
        row = await cur.fetchone()
        active_nurses = row["count"] if row else 0

        cur = await conn.execute("SELECT COUNT(*) as count FROM schedules WHERE status = 'published'")
        row = await cur.fetchone()
        published = row["count"] if row else 0

        cur = await conn.execute("SELECT COUNT(*) as count FROM schedules WHERE status = 'draft'")
        row = await cur.fetchone()
        drafts = row["count"] if row else 0

        # Acuity distribution
        cur = await conn.execute("""
            SELECT acuity, COUNT(*) as count
            FROM patients_registry WHERE status = 'admitted'
            GROUP BY acuity ORDER BY acuity DESC
        """)
        acuity_dist = [dict(r) for r in await cur.fetchall()]

        return {
            "admitted_patients": admitted,
            "active_nurses": active_nurses,
            "published_schedules": published,
            "draft_schedules": drafts,
            "acuity_distribution": acuity_dist,
            "avg_patients_per_nurse": round(admitted / active_nurses, 1) if active_nurses else 0,
        }


async def mark_assignment_handoff_complete(assignment_id: str) -> bool:
    """Mark a schedule assignment's handoff_status as 'completed'."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "UPDATE schedule_assignments SET handoff_status = 'completed' WHERE assignment_id = ?",
            (assignment_id,)
        )
        await conn.commit()
        return cur.rowcount > 0

