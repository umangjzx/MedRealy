"""
Agent 2b — HuggingFace SBAR Extraction Agent
Uses a local Flan-T5 model for clinical data extraction from transcripts.
No API key needed — model is downloaded once and cached locally.

Strategy: Multiple focused QA-style prompts (flan-t5 excels at these).
"""

import re
import asyncio
from backend.models import (
    SBARData, PatientInfo, Situation, Background,
    Assessment, Recommendation, Vitals,
)
from backend.config import HF_SBAR_MODEL

# ── Lazy-loaded globals ──────────────────────────────────────────────────────
_model = None
_tokenizer = None


def _load_model():
    """Lazy-load the HuggingFace model + tokenizer on first call (downloads once)."""
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    print(f"[HF-SBAR] Loading model '{HF_SBAR_MODEL}' (first run downloads ~1 GB)...")
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

    _tokenizer = AutoTokenizer.from_pretrained(HF_SBAR_MODEL)
    _model = AutoModelForSeq2SeqLM.from_pretrained(HF_SBAR_MODEL)
    print("[HF-SBAR] Model loaded successfully")
    return _model, _tokenizer


def _ask(model, tokenizer, question: str, context: str, max_tokens: int = 64) -> str:
    """Ask a single question about the clinical text and return the answer."""
    prompt = f"{question}\n\nContext: {context}"
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    outputs = model.generate(**inputs, max_new_tokens=max_tokens, num_beams=2)
    return tokenizer.decode(outputs[0], skip_special_tokens=True).strip()


def _clean(val: str) -> str | None:
    """Return None for empty / 'not mentioned' / 'unknown' answers."""
    if not val:
        return None
    low = val.lower().strip()
    if low in ("none", "unknown", "n/a", "not mentioned", "not stated",
               "not available", "no", "no information", "no data", ""):
        return None
    return val.strip()


def _parse_number(val: str) -> int | float | None:
    """Extract a number from a model answer."""
    if not val:
        return None
    m = re.search(r"(\d+\.?\d*)", val)
    if m:
        s = m.group(1)
        return float(s) if "." in s else int(s)
    return None


def _parse_list(val: str) -> list[str]:
    """Split a comma/semicolon/and-separated answer into a list."""
    if not val or _clean(val) is None:
        return []
    items = re.split(r"[,;]|\band\b", val)
    return [i.strip() for i in items if i.strip() and i.strip().lower() not in ("none", "unknown")]


# ── Agent class ──────────────────────────────────────────────────────────────
class HFExtractAgent:
    """Extract SBAR structured data using focused QA-style prompts to Flan-T5."""

    async def extract(self, transcript: str) -> SBARData:
        """Run the Flan-T5 model (in a thread) to extract SBAR fields."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_sync, transcript)

    def _extract_sync(self, transcript: str) -> SBARData:
        """Sync implementation of extraction logic."""
        try:
            model, tokenizer = _load_model()
            t = transcript[:2000]  # truncate to fit context

            print("[HF-SBAR] Extracting SBAR fields via focused QA prompts...")

            # ── Patient demographics ──
            name = _clean(_ask(model, tokenizer, "What is the patient's full name?", t))
            age = _clean(_ask(model, tokenizer, "What is the patient's age?", t))
            room = _clean(_ask(model, tokenizer, "What room or bed is the patient in?", t))

            # ── Situation ──
            dx = _clean(_ask(model, tokenizer, "What is the primary diagnosis or medical condition?", t))
            reason = _clean(_ask(model, tokenizer, "Why was the patient admitted?", t))
            status = _clean(_ask(model, tokenizer, "What is the patient's current clinical status?", t))

            # ── Vitals ──
            bp = _clean(_ask(model, tokenizer, "What is the blood pressure reading?", t, max_tokens=16))
            hr = _parse_number(_ask(model, tokenizer, "What is the heart rate in bpm?", t, max_tokens=16))
            rr = _parse_number(_ask(model, tokenizer, "What is the respiratory rate?", t, max_tokens=16))
            temp = _parse_number(_ask(model, tokenizer, "What is the body temperature?", t, max_tokens=16))
            spo2 = _parse_number(_ask(model, tokenizer, "What is the SpO2 or oxygen saturation percentage?", t, max_tokens=16))

            # ── Background ──
            meds_raw = _ask(model, tokenizer, "List all medications the patient is taking.", t, max_tokens=128)
            allergy_raw = _ask(model, tokenizer, "List all known allergies.", t, max_tokens=64)
            history = _clean(_ask(model, tokenizer, "What is the relevant medical history?", t))

            # ── Recommendation ──
            plan = _clean(_ask(model, tokenizer, "What is the care plan or treatment plan?", t, max_tokens=128))
            next_steps = _clean(_ask(model, tokenizer, "What are the next steps or pending actions?", t, max_tokens=128))

            result = SBARData(
                patient=PatientInfo(name=name, age=age, room=room),
                situation=Situation(
                    primary_diagnosis=dx,
                    reason_for_admission=reason,
                    current_status=status,
                ),
                background=Background(
                    relevant_history=history,
                    medications=_parse_list(meds_raw),
                    allergies=_parse_list(allergy_raw),
                    recent_procedures=[],
                ),
                assessment=Assessment(
                    vitals=Vitals(
                        bp=bp,
                        hr=int(hr) if hr else None,
                        rr=int(rr) if rr else None,
                        temp=float(temp) if temp else None,
                        spo2=int(spo2) if spo2 else None,
                    ),
                    labs_pending=[],
                    labs_recent=[],
                ),
                recommendation=Recommendation(
                    care_plan=plan,
                    next_steps=next_steps,
                    pending_orders=[],
                ),
            )

            print(f"[HF-SBAR] Extracted: patient={name}, dx={dx}, bp={bp}, hr={hr}")
            return result

        except Exception as e:
            print(f"[HF-SBAR] Extraction failed: {e}")
            return SBARData()
