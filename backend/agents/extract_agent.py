"""
Agent 2 — Extract Agent
Uses a local HuggingFace Flan-T5 model for SBAR extraction.
No external API key required — model is downloaded once and cached locally.
"""

from backend.models import SBARData


class ExtractAgent:
    def __init__(self):
        self._hf_agent = None  # lazy-loaded on first call

    def _get_hf_agent(self):
        if self._hf_agent is None:
            from backend.agents.hf_extract_agent import HFExtractAgent
            self._hf_agent = HFExtractAgent()
        return self._hf_agent

    async def extract(self, transcript: str) -> SBARData:
        """Extract SBAR data using the local HuggingFace Flan-T5 model."""
        try:
            hf = self._get_hf_agent()
            result = await hf.extract(transcript)
            print("[ExtractAgent] HuggingFace extraction succeeded")
            return result
        except Exception as e:
            print(f"[ExtractAgent] HuggingFace extraction failed: {e}")
            return SBARData()


