# MedRelay 🏥

> **Next-Generation Clinical Intelligence & Handoff Platform**

MedRelay is an advanced AI-powered system designed to modernize nursing shift transitions. It captures verbal handoffs, structures them into standardized SBAR reports using local AI models, performs real-time risk analysis, and provides deep clinical analytics—all wrapped in a premium, glassmorphism-inspired interface.

---

## 🌟 Key Features

### 🧠 Intelligent Handoffs
- **Real-time Transcription**: Converts voice to text instantly during bedside handoffs.
- **SBAR Structuring**: Automatically organizes chaotic speech into Situation, Background, Assessment, Recommendation.
- **Multi-Agent AI**: Specialized agents for Risk (Sentinel), Education, Pharmacy, and Debriefing.

### 📊 Advanced Analytics
- **Efficiency Trends**: Track handoff duration and efficiency scores over time.
- **Risk Heatmaps**: Visualize recurring high-severity alerts to identify systemic issues.
- **Quality Scoring**: Automated grading of handoff completeness and clarity (0-100 scale).

### 🎨 Modern Experience
- **Glassmorphism UI**: A stunning, dark-themed interface with dynamic gradients and blur effects.
- **Floating Dock Navigation**: App-like experience with smooth transitions.
- **Interactive Workflows**: Step-by-step guidance from recording to digital sign-off.

---

## 🏗️ Architecture

MedRelay uses a modern decoupled architecture with a FastAPI backend and React frontend, connected via WebSockets for real-time streaming.

```mermaid
graph TD
    subgraph Frontend [React + Vite]
        UI[Glassmorphism UI]
        WS_Client[WebSocket ClientWrapper]
        Recorder[Audio Handler]
    end

    subgraph Backend [FastAPI + Python]
        API[Admin REST API]
        WS_Server[WebSocket Endpoint]
        
        subgraph Pipeline [Agent Orchestration]
            Transcriber[Relay Agent<br/>(Transcription)]
            SBAR[Extract Agent<br/>(SBAR Creation)]
            Risk[Sentinel Agent<br/>(Risk Analysis)]
            Report[Bridge Agent<br/>(Text Gen)]
            
            subgraph Analytics_Logic
                Scores[Debrief Agent]
                Meds[Pharma Agent]
                History[Trend Agent]
                Learn[Educator Agent]
            end
        end
        
        DB[(SQLite Database)]
    end

    UI --> Recorder
    Recorder --> WS_Client
    WS_Client <--> WS_Server
    WS_Server --> Pipeline
    Pipeline --> DB
    API <--> DB
```

### Core Agents
1.  **Relay Agent**: Handles audio stream processing and transcription.
2.  **Extract Agent**: Uses optimized models to parse unstructured text into structured JSON.
3.  **Sentinel Agent**: Deterministic rules engine to flag high-risk keywords (e.g., "sepsis", "unstable").
4.  **Bridge Agent**: Synthesizes the final readable report.
5.  **Specialists**: Pharma (medication safety), Educator (learning resources), Debrief (quality scoring), Trend (historical analysis).

---

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLite (`aiosqlite`) - Zero-config persistence.
- **Concurrency**: Asyncio & WebSockets.
- **AI/ML**: `transformers`, `torch`, `langgraph` (Moving towards optimized local execution).

### Frontend
- **Framework**: React 19 + Vite.
- **Styling**: Tailwind CSS v4 + Custom CSS Variables.
- **Design System**: Premium Glassmorphism (blur/transparency/gradients).
- **State**: React Context API + Custom Hooks.
- **Visuals**: CSS-only charts for lightweight performance.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### 1. Backend Setup
```powershell
cd MedRelay
# Create & Activate Virtual Env
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install Dependencies
pip install -r backend/requirements.txt

# Run Server (Hot Reload)
python -m uvicorn backend.main:app --reload
```

### 2. Frontend Setup
```powershell
cd MedRelay/frontend
# Install Dependencies
npm install

# Run Dev Server
npm run dev
```

### 3. Access
- **App**: [http://localhost:5173](http://localhost:5173)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔐 Admin & Security
Default Credentials (Demo Mode):
- **User**: `admin`
- **Pass**: `1234`

**Role-Based Access Control (RBAC):**
- **Admin**: Full system access, analytics, user management.
- **Supervisor**: Analytics view, audit logs.
- **Nurse**: Handoff creation, history view.

---

## 📈 Analytics Dashboard
access the new dashboard at `/dashboard` (Admin role required).
1.  **Overview**: Real-time census, acuity breakdown, compliance stats.
2.  **Trends**: Efficiency scores and handoff volume analysis.
3.  **Quality**: Automated scoring of handoff fidelity and completeness.
4.  **Risk**: Heatmap visualization of frequent clinical alerts.

---

## 🤝 Contribution
1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit changes (`git commit -m 'Add AmazingFeature'`).
4.  Push to branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

**MedRelay** — *Streamlining Care, One Handoff at a Time.*
