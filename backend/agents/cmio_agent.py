"""
Agent 12 — CMIO Agent (Chief Medical Intelligence Officer)
Analyzes system-wide analytics, billing data, and clinical trends
to provide executive summaries and "Morning Briefings".
Uses Gemini exclusively. Falls back to a deterministic summary if Gemini is unavailable.
"""

import json
import re
from google import genai
from google.genai import types as genai_types
from datetime import datetime
from backend.config import GEMINI_API_KEY

# Initialize Gemini client
_gemini_client = None
if GEMINI_API_KEY:
    try:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"CMIO Agent: Failed to initialize Gemini client: {e}")

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

        if _gemini_client:
            try:
                response = await _gemini_client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(temperature=0.3)
                )
                content = response.text
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "{" in content:
                    content = content[content.find("{"):content.rfind("}")+1]
                return _format_output(json.loads(content))
            except Exception as e:
                print(f"CMIO Agent (Gemini) Error: {e}")

        # Gemini unavailable — return deterministic demo summary
        print("CMIO Agent: Gemini unavailable, using deterministic fallback.")
        return _format_output(_deterministic_briefing(stats))


def _deterministic_briefing(stats: dict) -> dict:
    """Rule-based fallback briefing when Gemini is unavailable."""
    sessions = stats.get("daily_sessions", 0)
    severity = stats.get("severity_distribution", {})
    high_count = severity.get("high", 0)
    compliance = stats.get("signoff_compliance", 100)
    staffing = stats.get("staffing_status", "unknown")

    # Health score: starts at 100, deducted for risk indicators
    score = 100
    score -= min(high_count * 5, 30)          # high alerts penalise
    score -= max(0, (100 - compliance) // 2)   # low compliance penalises
    if staffing in ("Red", "yellow"):
        score -= 15
    score = max(score, 0)

    insights = []
    if high_count > 0:
        insights.append(f"{high_count} high-severity alert(s) require immediate attention")
    if compliance < 90:
        insights.append(f"Sign-off compliance at {compliance}% — below target of 90%")
    if staffing not in ("Green", "unknown"):
        insights.append(f"Staffing status: {staffing} — consider activating on-call staff")
    if sessions > 0:
        insights.append(f"{sessions} handoff session(s) processed today")
    if not insights:
        insights.append("Unit operating within normal parameters")

    narrative = (
        f"Unit processed {sessions} handoff session(s) today. "
        f"System health score: {score}/100. "
        + (f"{high_count} high-severity alert(s) active. " if high_count else "No high-severity alerts. ")
        + f"Sign-off compliance: {compliance}%. Staffing: {staffing}."
    )

    return {
        "system_health_score": score,
        "narrative_summary": narrative,
        "strategic_insights": insights,
        "projected_revenue": stats.get("billing_potential", 0),
    }
