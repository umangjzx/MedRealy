"""
Agent 10 — Staffing Agent
Analyzes unit acuity, nurse load, and patient risk scores to provide
staffing recommendations and burnout warnings.
"""

import math
import anthropic
from datetime import datetime
from backend.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

class StaffingAgent:
    async def analyze(self, nurses: list, patients: list, assignments: list, risk_data: dict) -> dict:
        """
        Analyze the current staffing schedule and patient acuity.
        
        Args:
            nurses: List of nurse objects (id, name, role)
            patients: List of patient objects (id, name, acuity 1-5)
            assignments: List of assignment objects (nurse_id, patient_id)
            risk_data: Dict mapping patient_id -> {score: 0-100, alerts: [], trend: "stable"|"deteriorating"}
        
        Returns:
            JSON object with:
            - unit_status: "Green" | "Yellow" | "Red"
            - summary: Text summary of the unit state.
            - recommendations: List of specific actionable moves (e.g., "Move Patient X to Nurse Y").
            - burnout_risks: List of nurses at risk of overload.
        """
        
        # 1. Aggregate Data for Prompt
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # structure per nurse (only active ones)
        nurse_loads = {n['user_id']: {'name': n['display_name'], 'role': n['role'], 
                                      'status': n.get('shift_status', 'active'),
                                      'patients': [], 
                                      'total_acuity': 0, 'risk_sum': 0} 
                        for n in nurses if n.get('shift_status', 'active') in ('active', 'on_call')}
        
        # Track absent nurses to ensure their patients are moved
        absent_nurses = [n for n in nurses if n.get('shift_status') == 'absent']
        
        unassigned_patients = []
        
        # Map assignments
        for a in assignments:
            nid = a['nurse_user_id']
            pid = a['patient_id']
            pat = next((p for p in patients if p['patient_id'] == pid), None)
            
            if pat:
                risk = risk_data.get(pid, {'score': 0, 'alerts': []})
                p_item = {
                    'name': pat['name'],
                    'acuity': pat['acuity'],
                    'risk': risk['score'],
                    'diagnosis': pat['diagnosis']
                }

                if nid in nurse_loads:
                    nurse_loads[nid]['patients'].append(p_item)
                    nurse_loads[nid]['total_acuity'] += pat['acuity']
                    nurse_loads[nid]['risk_sum'] += risk['score']
                else:
                    # Nurse is absent/inactive -> mark patient as unassigned/needs move
                    unassigned_patients.append({**p_item, 'old_nurse_id': nid})

        prompt = (
            "You are a Charge Nurse AI Assistant. Analyze this unit's staffing schedule.\n"
            "Goal: Optimize patient safety, cover absent staff, and prevent burnout.\n"
            "Input:\n"
            f"TIMESTAMP: {timestamp}\n"
            f"ACTIVE STAFF:\n{nurse_loads}\n"
            f"ABSENT STAFF: {[n['display_name'] for n in absent_nurses]}\n"
            f"UNCOVERED PATIENTS (from absent staff): {unassigned_patients}\n\n"
            "Task:\n"
            "1. Determine Unit Status (Green/Yellow/Red).\n"
            "2. IMMEDIATELY assign all 'UNCOVERED PATIENTS' to the best available active nurses.\n"
            "   (Prioritize nurses with low acuity/risk sum).\n"
            "3. If load is too high, recommend activating 'on_call' staff if available.\n"
            "4. Predict next 4 hours: If avg acuity > 3.5, warn of potential overload.\n\n"
            "Return JSON ONLY:\n"
            "{\n"
            '  "unit_status": "Green|Yellow|Red",\n'
            '  "summary": "High-level summary including coverage plan for absent staff...",\n'
            '  "prediction": "Prediction for next 4 hours (e.g., Expecting 2 admissions + high acuity load).",\n'
            '  "recommendations": ["Assign Patient A (from absent Nurse X) to Nurse Y", "Activate On-Call Nurse Z"],\n'
            '  "burnout_risks": ["Nurse X is overloaded (Score 200)"]\n'
            "}"
        )

        try:
            response = await _client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1000,
                temperature=0.2,
                system="You are an expert Nurse Manager AI. Output valid JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract JSON
            content = response.content[0].text
            import json
            # naive JSON extraction if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "{" in content:
                content = content[content.find("{"):content.rfind("}")+1]
                
            return json.loads(content)

        except Exception as e:
            print(f"Staffing Agent Error: {e}")
            return {
                "unit_status": "Yellow",
                "summary": "AI Analysis failed to generation. Using fallback metrics.",
                "recommendations": ["Check manual assignments."],
                "burnout_risks": []
            }
