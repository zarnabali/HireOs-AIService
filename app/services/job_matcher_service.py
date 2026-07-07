from typing import Any

from app.services.ai_utils import extract_job_requirements, extract_keywords, extract_resume_skills, flatten_text, get_any, overlap_score


class JobMatcherService:
    def match(self, payload: dict[str, Any]) -> dict[str, Any]:
        resume = get_any(payload, "structuredResume", "structured_resume", default={})
        jobs = list(get_any(payload, "jobs", default=[]))
        limit = int(get_any(payload, "limit", default=20) or 20)
        filters = get_any(payload, "filters", default={})
        resume_skills = extract_resume_skills(resume)
        resume_text = flatten_text(resume).lower()
        resume_keywords = extract_keywords(resume_text)
        resume_profile_terms = self._resume_profile_terms(resume, resume_skills, resume_keywords)
        matches = [self._match_job(job, resume_skills, resume_keywords, resume_profile_terms, resume_text, filters) for job in jobs]
        matches.sort(key=lambda item: item["matchScore"], reverse=True)
        matches = matches[:limit]
        warnings = []
        if not jobs:
            warnings.append("No jobs were provided by backend for matching.")
        if not resume_skills and not resume_text.strip():
            warnings.append("No extracted resume profile was provided. Run resume extraction before trusting match quality.")
        return {
            "success": True,
            "data": {"matches": matches, "candidateSkills": resume_skills, "candidateKeywords": resume_keywords},
            "matches": matches,
            "confidence": 0.84 if jobs and resume_text.strip() else 0.35,
            "warnings": warnings,
            "reviewRequired": False,
            "error": None,
        }

    def _match_job(
        self,
        job: dict[str, Any],
        resume_skills: list[str],
        resume_keywords: list[str],
        resume_profile_terms: list[str],
        resume_text: str,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        requirements = extract_job_requirements(job)
        skill_score, skill_matched, _skill_missing = overlap_score(resume_skills, requirements)
        keyword_score, keyword_matched, keyword_missing = overlap_score(resume_keywords, requirements)
        profile_score, profile_matched, _profile_missing = overlap_score(resume_profile_terms, requirements)
        base_score = round(skill_score * 0.62 + keyword_score * 0.23 + profile_score * 0.15)
        matched = self._unique([*skill_matched, *keyword_matched, *profile_matched])
        missing = [requirement for requirement in requirements if requirement.lower() not in {item.lower() for item in matched}]
        title = get_any(job, "title", default="Untitled job")
        job_id = get_any(job, "id", "job_id", "jobId", default="")
        text_matched = [
            requirement
            for requirement in missing
            if requirement and requirement.lower() in resume_text
        ]
        if text_matched:
            matched = [*matched, *text_matched]
            missing = [requirement for requirement in missing if requirement not in text_matched]
            direct_text_score = round((len(matched) / max(1, len(requirements))) * 100)
            base_score = max(base_score, direct_text_score)

        filter_bonus = self._filter_alignment_bonus(job, filters)
        evidence_bonus = 4 if resume_text.strip() else 0
        score = min(100, round(base_score * 0.86 + filter_bonus + evidence_bonus))
        explanation = self._explain(title, matched, missing, filter_bonus)
        return {
            "jobId": job_id,
            "title": title,
            "companyName": get_any(get_any(job, "companies", "company", default={}), "name", default=""),
            "matchScore": score,
            "matchedSkills": matched,
            "missingSkills": missing[:10],
            "reasons": [explanation],
            "evidence": {
                "candidateSkills": resume_skills,
                "candidateKeywords": resume_keywords[:30],
                "candidateProfileTerms": resume_profile_terms[:30],
                "jobRequirements": requirements,
                "matchedFromResumeText": text_matched,
                "skillScore": skill_score,
                "keywordScore": keyword_score,
                "profileScore": profile_score,
                "filterAlignmentBonus": filter_bonus,
            },
            "confidence": 0.82 if resume_text.strip() else 0.35,
        }

    def _resume_profile_terms(
        self,
        resume: dict[str, Any],
        resume_skills: list[str],
        resume_keywords: list[str],
    ) -> list[str]:
        experience = get_any(resume, "experience", "work_experience", "workExperience", default=[])
        projects = get_any(resume, "projects", default=[])
        education = get_any(resume, "education", default=[])
        summary = get_any(resume, "summary", "professional_summary", "professionalSummary", default="")
        profile_text = flatten_text(
            {
                "summary": summary,
                "experience": experience,
                "projects": projects,
                "education": education,
            }
        )
        title_terms = []
        experience_items = experience if isinstance(experience, list) else []
        for item in experience_items:
            if isinstance(item, dict):
                title_terms.append(str(get_any(item, "title", "role", "position", default="")))
        return self._unique([*resume_skills, *resume_keywords, *extract_keywords(profile_text), *title_terms])

    def _unique(self, values: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                output.append(cleaned)
        return output

    def _filter_alignment_bonus(self, job: dict[str, Any], filters: dict[str, Any]) -> int:
        if not isinstance(filters, dict):
            return 0
        bonus = 0
        if get_any(filters, "remoteType", "remote_type", default="") and get_any(filters, "remoteType", "remote_type", default="") == get_any(job, "remote_type", "remoteType", default=""):
            bonus += 4
        if get_any(filters, "seniority", default="") and get_any(filters, "seniority", default="") == get_any(job, "seniority", default=""):
            bonus += 4
        if get_any(filters, "employmentType", "employment_type", default="") and get_any(filters, "employmentType", "employment_type", default="") == get_any(job, "employment_type", "employmentType", default=""):
            bonus += 3
        location_filter = str(get_any(filters, "location", default="")).strip().lower()
        job_location = str(get_any(job, "location", default="")).lower()
        if location_filter and location_filter in job_location:
            bonus += 3
        return bonus

    def _explain(self, title: str, matched: list[str], missing: list[str], filter_bonus: int) -> str:
        matched_text = ", ".join(matched[:5]) if matched else "limited explicit overlap"
        missing_text = ", ".join(missing[:4]) if missing else "no major required skills missing"
        filter_text = " Search filters also align." if filter_bonus else ""
        return f"{title} match is based on {matched_text}; review {missing_text}.{filter_text}"
