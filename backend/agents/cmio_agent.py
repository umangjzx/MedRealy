"""
Agent 12 — CMIO Agent (Chief Medical Intelligence Officer)
Analyzes system-wide analytics, billing data, and clinical trends
to provide executive summaries and "Morning Briefings".
"""

import json
import anthropic
import google.generativeai as genai
from datetime import datetime
from backend.config import ANTHROPIC_API_KEY, GEMINI_API_KEY, CLAUDE_MODEL

# Initialize Gemini if available
_gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel('gemini-flash-latest')
    except Exception as e:
        print(f"CMIO Agent: Failed to initialize Gemini client: {e}")

# Only initialize Anthropic client if a valid key is provided AND Gemini is not active
_client = None
if ANTHROPIC_API_KEY and not _gemini_model:
    try:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    except Exception:
        print("CMIO Agent: Failed to initialize Anthropic client (invalid key)")

class CMIOAgent:
    async def generate_briefing(self, stats: dict, recent_alerts: list) -> dict:
        """
        Generate a "Morning Briefing" executive summary.
        
        Args:
            stats: Dictionary containing:
                   - daily_sessions (volume)
                   - severity_distribution (risk)
                   - signoff_compliance (quality)
                   - billing_potential (revenue estimate)
                   - staffing_status (unit load)
            recent_alerts: List of recent high-severity alerts (clinical drill-down)
            
        Returns:
            JSON object with:
            - system_health_score (0-100)
            - narrative_summary (markdown)
            - key_insights (bullet points)
            - revenue_forecast (text)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        prompt = (
            "You are the AI Chief Medical Intelligence Officer (CMIO) for a hospital unit. "
            "Your job is to digest complex operational data into a clear, strategic executive summary.\n\n"
            f"TIMESTAMP: {timestamp}\n\n"
            f"OPERATIONAL DATA:\n{json.dumps(stats, indent=2)}\n\n"
            f"RECENT CRITICAL ALERTS:\n{json.dumps(recent_alerts, indent=2)}\n\n"
            "TASK:\n"
            "1. Calculated a 'System Health Score' (0-100) based on compliance, risk levels, and staffing.\n"
            "2. Write a 'Morning Briefing' narrative (2-3 paragraphs) summarizing unit status.\n"
            "3. Extract 3-4 key strategic insights (e.g., 'Sepsis cases up 20%', 'Night shift staffing critical').\n"
            "4. Estimate revenue impact if billing data is present. Provide an integer value for 'projected_revenue'.\n\n"
            "RETURN JSON ONLY:\n"
            "{\n"
            '  "system_health_score": 85,\n'
            '  "narrative_summary": "Overall unit performance is stable, though night shift shows signs of strain...",\n'
            '  "strategic_insights": ["Insight 1", "Insight 2", "Insight 3"],\n'
            '  "projected_revenue": 15000\n'
            "}"
        )

        # Helper to format output
        def _format_output(data):
            # Ensure keys match frontend expectations
            data["strategic_insights"] = data.get("strategic_insights") or data.get("key_insights") or []
            data["projected_revenue"] = data.get("projected_revenue") or 0
            if isinstance(data["projected_revenue"], str):
                 # Try to parse "$15,000" -> 15000
                 try:
                     import re
                     nums = re.findall(r'\d+', data["projected_revenue"].replace(',', ''))
                     data["projected_revenue"] = int(nums[0]) if nums else 0
                 except:
                     data["projected_revenue"] = 0

            # Add computed metadata
            data["generated_at"] = datetime.now().isoformat()
            data["active_census"] = stats.get("unique_patients", 0)  # Proxy for census
            data["critical_alerts_24h"] = stats.get("severity_distribution", {}).get("high", 0)
            return data

        if _gemini_model:
            try:
                response = await _gemini_model.generate_content_async(
                    prompt,
                    generation_config=genai.types.GenerationConfig(temperature=0.3)
                )
                content = response.text
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "{" in content:
                    content = content[content.find("{"):content.rfind("}")+1]
                return _format_output(json.loads(content))
            except Exception as e:
                print(f"CMIO Agent (Gemini) Error: {e}")
                # Fall through to fallback

        if not _client:
             print("CMIO Agent: No API key available, using demo fallback.")
             return _format_output({
                "system_health_score": 85,
                "narrative_summary": "**Demo Mode:** AI analysis is unavailable because neither Gemini nor Anthropic API keys are configured correctly. Please check `.env`.",
                "strategic_insights": ["Demo Insight 1: API Key missing", "Demo Insight 2: Using fallback data"],
                "projected_revenue": 0
            })

        try:
            response = await _client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                temperature=0.3,
                system="You are an expert Medical Executive AI. Precise, strategic, and data-driven.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "{" in content:
                content = content[content.find("{"):content.rfind("}")+1]
                
            return _format_output(json.loads(content))

        except Exception as e:
            print(f"CMIO Agent Error: {e}")
            return {
                "system_health_score": 0,
                "narrative_summary": "AI Analysis unavailable.",
                "key_insights": ["System error during analysis"],
                "revenue_forecast": "N/A"
            }
