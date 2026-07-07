from typing import Any

from app.clients.openai_client import CachedOpenAIJsonClient
from app.services.ai_utils import (
    extract_keywords,
    extract_resume_skills,
    flatten_text,
    get_any,
    protected_attribute_warnings,
    quantified_achievement_count,
)


class ResumeAnalyzerService:
    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        resume = get_any(payload, "structuredResume", "structured_resume", default={})
        target_role = get_any(payload, "targetRole", "target_role", default="")
        target_jd = get_any(payload, "targetJobDescription", "target_job_description", default="")

        skills = extract_resume_skills(resume)
        experience = get_any(resume, "experience", default=[])
        education = get_any(resume, "education", default=[])
        projects = get_any(resume, "projects", default=[])
        contact = get_any(resume, "contact", default={})
        summary = get_any(resume, "summary", default="")
        quantified = quantified_achievement_count(resume)

        target_keywords = extract_keywords(f"{target_role} {target_jd}")
        skill_norm = {skill.lower() for skill in skills}
        matched_keywords = [kw for kw in target_keywords if kw.lower() in skill_norm or kw.lower() in flatten_text(resume).lower()]
        missing_keywords = [kw for kw in target_keywords if kw not in matched_keywords][:12]

        breakdown = {
            "atsCompatibility": self._score(bool(contact), len(skills) >= 6, bool(experience), bool(education)),
            "skillsCoverage": min(100, 30 + len(skills) * 7),
            "experienceClarity": self._score(bool(experience), quantified > 0, len(flatten_text(experience)) > 300),
            "measurableAchievements": min(100, quantified * 25),
            "roleAlignment": round((len(matched_keywords) / max(len(target_keywords), 1)) * 100) if target_keywords else 70,
            "sectionCompleteness": self._score(bool(summary), bool(skills), bool(experience), bool(education), bool(projects)),
        }
        score = round(sum(breakdown.values()) / len(breakdown))

        suggestions = self._suggestions(resume, skills, quantified, missing_keywords)
        warnings = protected_attribute_warnings(resume)

        llm = CachedOpenAIJsonClient().complete_json(
            system_prompt=(
                "You are a resume quality analyst. Return JSON with optional keys "
                "suggestions, rewriteExamples, warnings. Do not mention or infer protected attributes."
            ),
            payload=f"Resume: {resume}\nTarget role: {target_role}\nJob description: {target_jd}",
            fallback={},
        )
        suggestions = [*suggestions, *[str(item) for item in llm.get("suggestions", []) if str(item).strip()]]
        warnings = [*warnings, *[str(item) for item in llm.get("warnings", []) if str(item).strip()]]

        return {
            "success": True,
            "score": score,
            "data": {
                "score": score,
                "breakdown": breakdown,
                "matchedKeywords": matched_keywords,
                "missingKeywords": missing_keywords,
                "rewriteExamples": llm.get("rewriteExamples", []),
            },
            "breakdown": breakdown,
            "suggestions": suggestions,
            "warnings": warnings,
            "confidence": 0.86,
            "reviewRequired": score < 60 or bool(warnings),
            "error": None,
        }

    def _score(self, *checks: bool) -> int:
        return round((sum(1 for check in checks if check) / len(checks)) * 100)

    def _suggestions(
        self,
        resume: dict[str, Any],
        skills: list[str],
        quantified: int,
        missing_keywords: list[str],
    ) -> list[str]:
        suggestions: list[str] = []
        if not get_any(resume, "summary", default=""):
            suggestions.append("Add a concise professional summary targeted to the role.")
        if len(skills) < 6:
            suggestions.append("Add a dedicated skills section with tools, languages, frameworks, and cloud platforms.")
        if quantified == 0:
            suggestions.append("Add measurable achievements such as performance gains, cost savings, scale, or revenue impact.")
        if missing_keywords:
            suggestions.append(f"Add relevant keywords if truthful: {', '.join(missing_keywords[:6])}.")
        if not get_any(resume, "projects", default=[]):
            suggestions.append("Add 1-3 relevant projects with technologies, problem, and measurable outcome.")
        return suggestions
