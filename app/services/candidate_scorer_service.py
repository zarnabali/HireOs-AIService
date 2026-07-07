from typing import Any

from app.services.ai_utils import (
    extract_job_requirements,
    extract_resume_skills,
    flatten_text,
    get_any,
    overlap_score,
    protected_attribute_warnings,
    quantified_achievement_count,
)


class CandidateScorerService:
    def score_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        job = get_any(payload, "job", default={})
        applications = list(get_any(payload, "applications", default=[]))
        resumes = list(get_any(payload, "resumes", default=[]))
        requirements = extract_job_requirements(job)
        resume_by_id = {str(get_any(resume, "id", default="")): resume for resume in resumes}

        rankings = []
        warnings = protected_attribute_warnings(job)
        for application in applications:
            resume_id = str(get_any(application, "resume_id", "resumeId", default=""))
            resume_row = resume_by_id.get(resume_id, {})
            structured = get_any(resume_row, "structured_data", "structuredData", "structured_resume", "structuredResume", default={})
            rankings.append(self._score_candidate(application, resume_row, structured, requirements))
            warnings.extend(protected_attribute_warnings(structured))

        if not applications and resumes:
            for resume_row in resumes:
                structured = get_any(resume_row, "structured_data", "structuredData", "structured_resume", "structuredResume", default={})
                rankings.append(self._score_candidate({}, resume_row, structured, requirements))
                warnings.extend(protected_attribute_warnings(structured))

        rankings.sort(key=lambda item: item["score"], reverse=True)
        return {
            "success": True,
            "data": {"rankings": rankings, "jobRequirements": requirements},
            "rankings": rankings,
            "confidence": 0.84 if rankings else 0.35,
            "warnings": list(dict.fromkeys(warnings)),
            "reviewRequired": bool(warnings),
            "error": None,
        }

    def _score_candidate(
        self,
        application: dict[str, Any],
        resume_row: dict[str, Any],
        structured: dict[str, Any],
        requirements: list[str],
    ) -> dict[str, Any]:
        skills = extract_resume_skills(structured)
        evidence_text = flatten_text(structured).lower()
        overlap, matched, missing = overlap_score(skills, requirements)
        text_matched = [
            requirement
            for requirement in missing
            if requirement and requirement.lower() in evidence_text
        ]
        if text_matched:
            matched = [*matched, *text_matched]
            missing = [requirement for requirement in missing if requirement not in text_matched]
            overlap = round((len(matched) / max(1, len(requirements))) * 100)
        achievement_bonus = min(15, quantified_achievement_count(structured) * 3)
        project_bonus = 8 if get_any(structured, "projects", default=[]) else 0
        experience_bonus = 10 if get_any(structured, "experience", default=[]) else 0
        education_bonus = 4 if get_any(structured, "education", default=[]) else 0
        extracted_signal_bonus = 0
        if skills:
            extracted_signal_bonus += 8
        if evidence_text.strip():
            extracted_signal_bonus += 4
        score = min(100, round(overlap * 0.72 + achievement_bonus + project_bonus + experience_bonus + education_bonus + extracted_signal_bonus))
        if evidence_text.strip() and score == 0:
            score = 12
        candidate_id = get_any(application, "candidate_id", "candidateId", default=get_any(resume_row, "candidate_id", "candidateId", default=""))
        resume_id = get_any(application, "resume_id", "resumeId", default=get_any(resume_row, "id", default=""))
        warnings = []
        if not evidence_text.strip():
            warnings.append("No extracted resume text or structured resume data was available for this applicant.")
        if not skills:
            warnings.append("No skills were extracted from this resume; run extraction again before making a hiring decision.")
        return {
            "candidateId": candidate_id,
            "resumeId": resume_id,
            "score": score,
            "matchedRequirements": matched,
            "missingRequirements": [item.title() for item in missing[:10]],
            "evidence": {
                "skills": skills,
                "hasProjects": bool(get_any(structured, "projects", default=[])),
                "quantifiedAchievements": quantified_achievement_count(structured),
                "matchedFromResumeText": text_matched,
            },
            "concerns": [f"Missing {item.title()}" for item in missing[:4]],
            "interviewFocus": [item.title() for item in (missing[:5] or matched[:5])],
            "confidence": 0.82 if evidence_text.strip() else 0.2,
            "warnings": warnings,
        }
