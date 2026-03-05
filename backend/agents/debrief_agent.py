"""
Agent 9 — Debrief Agent
Evaluates the quality of a nurse handoff communication:
  - SBAR completeness scoring
  - Clarity and specificity metrics
  - Critical information coverage
  - Time efficiency assessment
  - Actionable coaching feedback

Useful for quality improvement (QI) programs, nurse training,
and accreditation/audit evidence.

Uses a deterministic scoring rubric for consistency. Optionally
uses Claude to generate personalised coaching notes.
"""

import re
from backend.models import (
    SBARData, RiskAlert, HandoffScorecard, DebriefReport,
)



class DebriefAgent:
    """Scores handoff quality and generates coaching feedback."""

    async def evaluate(
        self,
        sbar: SBARData,
        alerts: list[RiskAlert],
        transcript: str = "",
        duration_seconds: float = 0,
    ) -> DebriefReport:
        scorecards = [
            self._score_completeness(sbar),
            self._score_clarity(sbar, transcript),
            self._score_safety(sbar, alerts),
            self._score_structure(transcript),
            self._score_efficiency(transcript, duration_seconds),
        ]

        total = sum(sc.score for sc in scorecards)
        max_total = sum(sc.max_score for sc in scorecards)
        overall = round((total / max_total) * 100, 1) if max_total else 0
        grade = self._grade(overall)

        strengths = []
        improvements = []
        for sc in scorecards:
            pct = (sc.score / sc.max_score * 100) if sc.max_score else 0
            if pct >= 80:
                strengths.append(f"{sc.category}: {sc.score}/{sc.max_score}")
            elif pct < 60:
                improvements.extend(sc.findings)

        # Generate coaching note
        coaching = await self._coaching_note(sbar, scorecards, overall, grade, transcript)

        return DebriefReport(
            overall_score=overall,
            grade=grade,
            scorecards=scorecards,
            strengths=strengths,
            improvements=improvements,
            coaching_note=coaching,
        )

    # ── 1. Completeness Score (0-10) ─────────────────────────────────────────

    def _score_completeness(self, sbar: SBARData) -> HandoffScorecard:
        score = 0.0
        findings = []

        # Patient identification (2 pts)
        if sbar.patient.name:
            score += 1
        else:
            findings.append("Patient name missing")
        if sbar.patient.mrn or sbar.patient.age:
            score += 1
        else:
            findings.append("No second identifier (MRN or age)")

        # Situation (2 pts)
        if sbar.situation.primary_diagnosis:
            score += 1
        else:
            findings.append("Primary diagnosis not documented")
        if sbar.situation.current_status:
            score += 1
        else:
            findings.append("Current clinical status missing")

        # Background (2 pts)
        if sbar.background.medications:
            score += 1
        else:
            findings.append("Medication list empty")
        if sbar.background.allergies:
            score += 0.5
        else:
            findings.append("Allergies not documented")
        if sbar.background.relevant_history:
            score += 0.5
        else:
            findings.append("Relevant history missing")

        # Assessment (2 pts)
        v = sbar.assessment.vitals
        vitals_present = sum([
            bool(v.bp), bool(v.hr), bool(v.rr),
            bool(v.temp), v.spo2 is not None,
        ])
        score += min(vitals_present * 0.4, 2)
        if vitals_present < 3:
            findings.append(f"Only {vitals_present}/5 vital signs documented")

        # Recommendation (2 pts)
        if sbar.recommendation.care_plan:
            score += 1
        else:
            findings.append("No care plan documented")
        if sbar.recommendation.escalation_triggers:
            score += 1
        else:
            findings.append("No escalation triggers defined")

        return HandoffScorecard(
            category="Completeness",
            score=round(min(score, 10), 1),
            max_score=10,
            findings=findings,
        )

    # ── 2. Clarity & Specificity Score (0-10) ────────────────────────────────

    def _score_clarity(self, sbar: SBARData, transcript: str) -> HandoffScorecard:
        score = 0.0
        findings = []

        # Specific vitals values vs vague (e.g., "BP is low" vs "BP 88/54")
        v = sbar.assessment.vitals
        if v.bp and re.match(r"\d+/\d+", v.bp):
            score += 2
        elif v.bp:
            score += 1
            findings.append("Blood pressure should include specific numbers (e.g., 120/80)")

        if v.hr is not None:
            score += 1.5
        if v.spo2 is not None:
            score += 1.5

        # Medication specificity (dose + route included)
        med_specific = sum(
            1 for m in sbar.background.medications
            if re.search(r"\d+\s*(mg|g|mcg|ml|units?)", m, re.I)
        )
        if sbar.background.medications:
            med_ratio = med_specific / len(sbar.background.medications)
            score += med_ratio * 2
            if med_ratio < 0.5:
                findings.append("Include dose, route, and frequency for all medications")
        else:
            findings.append("No medications listed — unable to assess specificity")

        # Diagnosis specificity
        dx = sbar.situation.primary_diagnosis or ""
        if len(dx) > 10:
            score += 1.5
        elif dx:
            score += 0.5
            findings.append("Diagnosis should be more specific (include etiology if known)")

        # Escalation specificity (has numbers/thresholds)
        esc = sbar.recommendation.escalation_triggers or ""
        if re.search(r"\d", esc):
            score += 1.5
        elif esc:
            score += 0.5
            findings.append("Escalation triggers should include specific numeric thresholds")
        else:
            findings.append("No escalation triggers — add specific criteria (e.g., MAP < 65)")

        return HandoffScorecard(
            category="Clarity & Specificity",
            score=round(min(score, 10), 1),
            max_score=10,
            findings=findings,
        )

    # ── 3. Safety Score (0-10) ────────────────────────────────────────────────

    def _score_safety(self, sbar: SBARData, alerts: list[RiskAlert]) -> HandoffScorecard:
        score = 10.0  # Start high, deduct for issues
        findings = []

        high_alerts = [a for a in alerts if a.severity == "HIGH"]
        med_alerts = [a for a in alerts if a.severity == "MEDIUM"]

        # Deductions
        score -= len(high_alerts) * 2.5
        score -= len(med_alerts) * 1.0

        if high_alerts:
            findings.append(f"{len(high_alerts)} HIGH-severity risk(s) detected")
        if med_alerts:
            findings.append(f"{len(med_alerts)} MEDIUM-severity risk(s) detected")

        # Bonus: allergy documented
        if sbar.background.allergies:
            score += 0.5

        # Bonus: escalation plan exists
        if sbar.recommendation.escalation_triggers:
            score += 0.5

        return HandoffScorecard(
            category="Patient Safety",
            score=round(max(min(score, 10), 0), 1),
            max_score=10,
            findings=findings,
        )

    # ── 4. Structure (SBAR adherence) Score (0-10) ───────────────────────────

    def _score_structure(self, transcript: str) -> HandoffScorecard:
        score = 0.0
        findings = []
        t = transcript.lower()

        # Check for SBAR section markers in the transcript
        sections = {
            "situation":      ["situation", "current issue", "presenting with", "admitted for", "diagnosis is"],
            "background":     ["background", "history", "allergies", "medications", "pmh", "past medical"],
            "assessment":     ["assessment", "vitals", "blood pressure", "heart rate", "labs", "current findings"],
            "recommendation": ["recommendation", "plan", "next steps", "escalation", "follow up", "care plan"],
        }

        for section, keywords in sections.items():
            if any(kw in t for kw in keywords):
                score += 2.5
            else:
                findings.append(f"'{section.title()}' section not clearly identified in handoff")

        if score >= 7.5:
            pass  # Good structure
        elif score >= 5:
            findings.insert(0, "Consider using explicit SBAR section headings for clearer communication")
        else:
            findings.insert(0, "Handoff lacks clear SBAR structure — use S-B-A-R framework for safer handoffs")

        return HandoffScorecard(
            category="SBAR Structure",
            score=round(min(score, 10), 1),
            max_score=10,
            findings=findings,
        )

    # ── 5. Efficiency Score (0-10) ────────────────────────────────────────────

    def _score_efficiency(self, transcript: str, duration_seconds: float) -> HandoffScorecard:
        score = 5.0  # Default if no duration data
        findings = []

        word_count = len(transcript.split()) if transcript else 0

        if duration_seconds > 0:
            minutes = duration_seconds / 60
            if minutes <= 3:
                score = 10.0  # Excellent — concise
            elif minutes <= 5:
                score = 8.0   # Good
            elif minutes <= 8:
                score = 6.0
                findings.append(f"Handoff took {minutes:.1f} min — aim for 3-5 minutes for bedside handoffs")
            elif minutes <= 12:
                score = 4.0
                findings.append(f"Handoff took {minutes:.1f} min — consider being more concise")
            else:
                score = 2.0
                findings.append(f"Handoff took {minutes:.1f} min — significantly exceeds recommended 3-5 min duration")
        else:
            findings.append("Duration not recorded — unable to assess time efficiency")

        # Word count assessment
        if word_count > 0:
            if word_count < 50:
                score = max(score - 2, 0)
                findings.append(f"Only {word_count} words — handoff may be too brief to be clinically useful")
            elif word_count > 1500:
                score = max(score - 1, 0)
                findings.append(f"{word_count} words — consider summarising to focus on critical information")

        return HandoffScorecard(
            category="Efficiency",
            score=round(min(score, 10), 1),
            max_score=10,
            findings=findings,
        )

    # ── Grading ───────────────────────────────────────────────────────────────

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"

    # ── Coaching Note (AI-powered or fallback) ────────────────────────────

    async def _coaching_note(
        self,
        sbar: SBARData,
        scorecards: list[HandoffScorecard],
        overall: float,
        grade: str,
        transcript: str,
    ) -> str:
        return self._fallback_coaching(scorecards, overall, grade)

    @staticmethod
    def _fallback_coaching(
        scorecards: list[HandoffScorecard], overall: float, grade: str,
    ) -> str:
        weakest = min(scorecards, key=lambda sc: sc.score / sc.max_score if sc.max_score else 1)
        strongest = max(scorecards, key=lambda sc: sc.score / sc.max_score if sc.max_score else 0)

        lines = [f"Handoff Quality: {grade} ({overall}/100)."]
        lines.append(f"Strongest area: {strongest.category} ({strongest.score}/{strongest.max_score}).")

        if weakest.findings:
            lines.append(f"Priority improvement: {weakest.category} — {weakest.findings[0]}")
        else:
            lines.append(f"Area to focus on: {weakest.category}.")

        if overall >= 80:
            lines.append("Great handoff overall! Keep using the SBAR framework consistently.")
        elif overall >= 60:
            lines.append("Good foundation. Focus on the identified gaps to reach the next level.")
        else:
            lines.append("Review the SBAR framework and practice including all critical elements in your next handoff.")

        return " ".join(lines)
