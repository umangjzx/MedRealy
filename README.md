# MedRelay

AI-assisted clinical handoff platform for nursing shift transitions.

MedRelay captures (or imports) handoff data, structures it into SBAR, runs risk checks, generates a human-readable report, and supports digital sign-off plus admin operations.

---

## What this system includes

- Real-time handoff flow over WebSocket
- Audio transcription using `SpeechRecognition` (Google Speech API)
- Multi-stage SBAR extraction with fallback pipeline
- Risk analysis against clinical thresholds
- SQLite persistence for sessions, analytics, and timelines
- Admin console backend APIs (users, settings, audit, session maintenance)
- Demo mode + complete demo patient payload
- Excel feed import endpoint for structured handoff ingestion

---

## Architecture

### Backend (FastAPI)

- Entry: `backend/main.py`
- Pipeline: `backend/pipeline.py`
- Agents:
  - `backend/agents/relay_agent.py` (audio + transcription)
  - `backend/agents/extract_agent.py` (LLM/HF extraction)
  - `backend/agents/sentinel_agent.py` (risk alerts)
  - `backend/agents/bridge_agent.py` (final report text)
- Data layer: `backend/database.py` (SQLite)
- Data models: `backend/models.py`

### Frontend (React + Vite + Tailwind v4)

- Entry: `frontend/src/App.jsx`
- Screens:
  - Start / Active Handoff / Report
  - History / Dashboard / Patient Timeline
  - Admin panel

---

## Requirements

- Windows (current workspace target)
- Python 3.11+ (3.13 works)
- Node.js 18+ and npm
- Virtual environment at `.venv`

---

## Quick start (Windows / PowerShell)

### 1) Backend

```powershell
cd "c:\Users\UMANG JAISWAL N\OneDrive\Desktop\MedRelay"
& ".\.venv\Scripts\Activate.ps1"
& ".\.venv\Scripts\python.exe" -m pip install -r .\backend\requirements.txt
$env:PYTHONPATH = $PWD.Path
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2) Frontend

```powershell
cd "c:\Users\UMANG JAISWAL N\OneDrive\Desktop\MedRelay\frontend"
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 3) Open app

- Frontend: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:8000/health`

---

## Demo data options

### A) Pipeline demo run

`POST /demo` runs a full synthetic handoff pipeline and saves a session.

### B) Full demo patient payload

`GET /demo/patient` returns a complete SBAR-compatible demo patient object with all required fields.

### C) Excel feed file

Prebuilt workbook:

- `demo/medrelay_feed_data.xlsx`

Includes sheets:

- `Feed_Instructions`
- `Patient_Feed_Template`
- `Risk_Alerts_Seed`
- `Transcript_Seed`

---

## Excel import endpoint

### Endpoint

`POST /import/excel?dry_run=true|false`

- Upload a `.xlsx` file as multipart form field: `file`
- Uses sheet `Patient_Feed_Template` if present, otherwise first sheet
- Validates required columns per row (at minimum `patient_name`, `primary_diagnosis`)
- Returns row-level import errors and imported session IDs

### Example (PowerShell using curl)

```powershell
$filePath = "c:\Users\UMANG JAISWAL N\OneDrive\Desktop\MedRelay\demo\medrelay_feed_data.xlsx"
curl.exe -X POST "http://127.0.0.1:8000/import/excel?dry_run=true" -F "file=@$filePath"
```

---

## Admin API

### Auth

- `POST /admin/login`
- Default seeded admin: `admin / 1234`

### Core endpoints

- `GET /admin/users`
- `POST /admin/users`
- `PATCH /admin/users/{user_id}`
- `DELETE /admin/users/{user_id}`
- `GET /admin/settings`
- `PUT /admin/settings`
- `GET /admin/audit?limit=100`
- `POST /admin/sessions/bulk-delete`

### Safe demo purge

`POST /admin/sessions/purge-demos?dry_run=true|false`

- Default behavior is safe (`dry_run=true`)
- Dry run returns `would_delete`
- Actual delete requires `dry_run=false`

---

## Role-Based Access Control (RBAC)

MedRelay supports four permission roles, each with granular access:

| Role | Display Name | Key Permissions |
| ------ | ------------- | ----------------- |
| `admin` | Administrator | Full access — manage users, settings, audit, sessions, analytics, import/export |
| `supervisor` | Supervisor | View analytics, audit logs, manage sessions, view/create handoffs, sign-off |
| `charge_nurse` | Charge Nurse | View analytics, create handoffs, sign-off, import Excel, export data |
| `nurse` | Nurse | View sessions, create handoffs, sign-off (minimal access) |

### Permission strings

- `manage_users` — create/edit/delete users (admin only)
- `manage_settings` — edit system settings (admin only)
- `view_audit` — read audit log (admin, supervisor)
- `manage_sessions` — bulk-delete, purge sessions (admin, supervisor)
- `view_analytics` — access analytics dashboard (admin, supervisor, charge_nurse)
- `view_sessions` — list/view handoff sessions (all roles)
- `create_handoff` — start new handoffs (all roles)
- `sign_off` — sign off on handoffs (all roles)
- `import_excel` — import Excel feed files (admin, supervisor, charge_nurse)
- `export_data` — export session data (admin, supervisor, charge_nurse)

### RBAC endpoints

- `GET /roles` — list all roles with display names and permissions
- `GET /auth/permissions` — get current user's role and permissions

### Creating users with roles

When creating via `POST /admin/users`, set the `role` field to one of: `admin`, `supervisor`, `charge_nurse`, `nurse`.

---

## Analytics Dashboard

The dashboard provides four views accessible via tabs:

### Overview

- Total sessions, unique patients, high alerts, sign-off rate, quality score
- Daily handoff volume bar chart
- Alert severity distribution
- Sign-off compliance ring
- Hourly heatmap
- Top diagnoses

### Nurse Performance

- Top outgoing nurses (by handoffs given) with sign-off rates
- Top incoming nurses (by handoffs received)
- Most frequent nurse pairs

### Trends

- Weekly sessions vs fully signed (12 weeks)
- Monthly sessions vs unique patients (12 months)
- Daily alert trend by severity (30 days) — stacked bars

### Quality

- Overall quality score (0–100) based on data completeness + sign-off compliance
- Summary statistics (avg alerts/session, completeness %)
- Per-field completeness bars (patient name, MRN, diagnosis, room, report, dual sign-off)
- Weekly quality score trend with color-coded thresholds

### Analytics API endpoints

- `GET /analytics` — overview analytics (existing)
- `GET /stats` — quick stats (existing)
- `GET /analytics/nurses` — nurse performance data
- `GET /analytics/trends` — weekly/monthly/daily trend data
- `GET /analytics/quality` — quality score and completeness metrics

---

## WebSocket handoff protocol

Endpoint: `ws://127.0.0.1:8000/ws/handoff`

### Client messages

- Start real handoff:

```json
{"type":"start","outgoing":"Nurse A","incoming":"Nurse B"}
```

- Stream binary audio chunks
- End handoff:

```json
{"type":"end"}
```

- Run demo handoff:

```json
{"type":"demo","outgoing":"Nurse A","incoming":"Nurse B"}
```

### Server stage messages

- `listening`
- `transcribing`
- `transcript`
- `extracting`
- `extract`
- `sentinel`
- `bridge`
- `complete`
- `error`

---

## Important runtime behavior

### Real transcription fallback guardrail

For live (non-demo) handoff:

- If audio fails to transcribe, MedRelay now returns an explicit error
- It **does not** silently inject demo/fake patient data

Demo data is only used when explicitly requested (`/demo` or WebSocket `type: demo`).

---

## Troubleshooting

### Backend starts but API times out

1. Kill stale processes:

```powershell
taskkill /F /IM uvicorn.exe 2>$null
taskkill /F /IM python.exe 2>$null
```

1. Restart backend without stale reload chain:

```powershell
cd "c:\Users\UMANG JAISWAL N\OneDrive\Desktop\MedRelay"
$env:PYTHONPATH = $PWD.Path
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Frontend `npm run dev` exits unexpectedly

Use explicit host/port:

```powershell
cd "c:\Users\UMANG JAISWAL N\OneDrive\Desktop\MedRelay\frontend"
npm run dev -- --host 127.0.0.1 --port 5173
```

### Live recording gives no transcript

- Confirm browser mic permission is granted
- Confirm input device is active and receiving audio
- Speak for at least 8–12 seconds before ending
- Check backend logs for relay/transcription errors

### Import endpoint fails with multipart error

Install dependency in `.venv`:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install python-multipart
```

---

## Data storage

SQLite DB file:

- `medrelay.db`

Contains:

- session records
- sign-off states
- admin users
- system settings
- audit logs

---

## Security note (demo defaults)

The seeded admin credentials (`admin / 1234`) are for local demo/development only. Rotate immediately for shared or production environments.

---

## Current model stack (local + fallback)

- Transcription: `SpeechRecognition` (Google Speech API, requires internet)
- SBAR extraction: Claude if valid key, else HuggingFace fallback
- Risk checks: deterministic threshold-based sentinel rules

---

## License / usage

This repository is currently configured for internal demo and development workflows.
