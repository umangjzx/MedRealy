"""
Agent 2 — Extract Agent
Tries Claude first for SBAR extraction. If Claude is unavailable (no API key,
quota exceeded, etc.), falls back to a local HuggingFace Flan-T5 model.
"""

import json
import re
import anthropic
from backend.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from backend.models import SBARData

_client = None
if ANTHROPIC_API_KEY:
    try:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    except: pass

_SBAR_SCHEMA = """{
  "patient": { "name": "", "age": "", "mrn": "", "room": "" },
  "situation": { "primary_diagnosis": "", "reason_for_admission": "", "current_status": "" },
  "background": { "relevant_history": "", "medications": [], "allergies": [], "recent_procedures": [] },
  "assessment": { 
    "vitals": { "bp": "", "hr": 0, "rr": 0, "temp": 0.0, "spo2": 0 }, 
    "labs_pending": [], "labs_recent": [], 
    "pain_level": 0, 
    "neurological_status": "" 
  },
  "recommendation": { 
    "care_plan": "", 
    "escalation_triggers": "", 
    "pending_orders": [], 
    "next_steps": "", 
    "action_items": [
      { "task": "", "priority": "MEDIUM", "due_time": "", "assignee": "Incoming Nurse" }
    ]
  },
  "risk_score": { 
    "score": 0, 
    "risk_level": "LOW", 
    "contributing_factors": [] 
  }
}"""


class ExtractAgent:
    def __init__(self):
        self._hf_agent = None  # lazy-loaded HuggingFace fallback

    def _get_hf_agent(self):
        if self._hf_agent is None:
            from backend.agents.hf_extract_agent import HFExtractAgent
            self._hf_agent = HFExtractAgent()
        return self._hf_agent

    async def extract(self, transcript: str) -> SBARData:
        """Extract SBAR data: try Claude first, then HuggingFace local model."""

        # ── 1. Try Claude (Primary) ──────────────────────────────────────
        if _client:
            try:
                result = await self._extract_claude(transcript)
                if result.patient.name is not None:
                    print("[ExtractAgent] Claude extraction succeeded")
                    return result
            except Exception as e:
                print(f"[ExtractAgent] Claude failed: {e}")

        # ── 2. Fall back to local HuggingFace model ──────────────────────
        try:
            print("[ExtractAgent] Falling back to HuggingFace local model...")
            hf = self._get_hf_agent()
            result = await hf.extract(transcript)
            return result
        except Exception as e:
            print(f"[ExtractAgent] HuggingFace extraction failed: {e}")

        return SBARData()

    async def _extract_claude(self, transcript: str) -> SBARData:
        """Extract SBAR structured data using Claude API."""
        prompt = (
            "You are a clinical data extraction system. Given this nurse handoff transcript, "
            "extract all patient information into the following JSON schema. "
            "Be precise. If information is not mentioned, use null. "
            "Do not hallucinate clinical data.\n\n"
            f"TRANSCRIPT:\n{transcript}\n\n"
            "Return ONLY valid JSON matching this schema (no markdown, no explanation):\n"
            f"{_SBAR_SCHEMA}"
        )
        response = await _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        block = response.content[0]
        raw = (getattr(block, "text", "") or "").strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)

        data = json.loads(raw)
        return SBARData(**data)
