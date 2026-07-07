import json
import re
from typing import Any

from app.clients.openai_client import CachedOpenAIJsonClient
from app.services.ai_utils import extract_keywords, get_any, unique_list


class HiringAssistantService:
    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = str(get_any(payload, "message", default=""))
        context = get_any(payload, "context", default={})
        recruiter_summary = _extract_recruiter_summary(context)
        intent = self._intent(message)
        keywords = extract_keywords(message)
        actions = self._actions(intent, keywords, context)
        answer = self._answer(intent, keywords, recruiter_summary)
        llm = _cached_chat_refinement(
            role="recruiter",
            intent=intent,
            message=message,
            keywords=keywords,
            actions=actions,
            context=context,
            context_summary=recruiter_summary,
            fallback=answer,
        )
        return {
            "success": True,
            "data": {"intent": intent, "keywords": keywords, "actions": actions, "contextSummary": recruiter_summary, "cachePolicy": "prompt_hash_ttl_3600"},
            "message": llm,
            "intent": intent,
            "actions": actions,
            "confidence": 0.82,
            "warnings": [],
            "reviewRequired": intent in {"shortlist", "compare"},
            "error": None,
        }

    def _intent(self, message: str) -> str:
        lower = message.lower()
        if any(word in lower for word in ["shortlist", "top 10", "top candidates"]):
            return "shortlist"
        if any(word in lower for word in ["compare", "versus", "vs"]):
            return "compare"
        if any(word in lower for word in ["interview", "questions", "screen"]):
            return "interview_focus"
        if any(word in lower for word in ["who", "show", "find", "search", "has worked"]):
            return "search_candidates"
        return "general_hiring_help"

    def _actions(self, intent: str, keywords: list[str], context: dict[str, Any]) -> list[dict[str, Any]]:
        if intent == "search_candidates":
            return [{"type": "search_candidates", "filters": {"skills": keywords}, "requiresBackendExecution": True}]
        if intent == "shortlist":
            return [{"type": "generate_shortlist", "jobId": context.get("jobId") or context.get("job_id"), "requiresBackendExecution": True}]
        if intent == "compare":
            return [{"type": "compare_candidates", "requiresBackendExecution": True}]
        if intent == "interview_focus":
            return [{"type": "generate_interview_focus", "skills": keywords, "requiresBackendExecution": True}]
        return [{"type": "answer_only", "requiresBackendExecution": False}]

    def _answer(self, intent: str, keywords: list[str], recruiter_summary: str) -> str:
        if intent == "search_candidates":
            return f"I can search your scoped applicants for: {', '.join(keywords[:8])}.\n\n{recruiter_summary}"
        if intent == "shortlist":
            return f"I can generate a shortlist with reasons, concerns, and interview focus from your current applicant pool.\n\n{recruiter_summary}"
        if intent == "compare":
            return f"I can compare scoped candidates on job requirements, evidence, missing skills, and interview risks.\n\n{recruiter_summary}"
        if intent == "interview_focus":
            return f"I can create interview focus areas tied to candidate evidence and job requirements.\n\n{recruiter_summary}"
        return f"I can help with scoped candidate search, shortlist generation, comparisons, and interview planning.\n\n{recruiter_summary}"


def _extract_recruiter_summary(ctx: dict[str, Any]) -> str:
    recruiter_context = ctx.get("recruiterContext") if isinstance(ctx, dict) else {}
    if not isinstance(recruiter_context, dict):
        return "No recruiter context was supplied by backend."

    recruiter = recruiter_context.get("recruiter") or {}
    companies = recruiter_context.get("companies") or []
    jobs = recruiter_context.get("jobs") or []
    applicants = recruiter_context.get("applicants") or []
    lines: list[str] = []

    if isinstance(recruiter, dict):
        name = recruiter.get("fullName") or recruiter.get("email")
        profile = recruiter.get("profile") or {}
        title = profile.get("title") if isinstance(profile, dict) else None
        if name or title:
            lines.append(f"Recruiter: {name or 'Unknown'}{f' - {title}' if title else ''}")

    if isinstance(companies, list) and companies:
        company_names = []
        for company in companies[:4]:
            if isinstance(company, dict) and company.get("name"):
                company_names.append(str(company["name"]))
        if company_names:
            lines.append(f"Companies: {', '.join(company_names)}")

    if isinstance(jobs, list) and jobs:
        open_jobs = [job for job in jobs if isinstance(job, dict) and job.get("status") == "open"]
        lines.append(f"Jobs in scope: {len(jobs)} total, {len(open_jobs)} open")
        job_lines = []
        for job in jobs[:8]:
            if not isinstance(job, dict):
                continue
            company = job.get("companies") or {}
            company_name = company.get("name") if isinstance(company, dict) else ""
            skills = job.get("required_skills") or []
            skill_text = ", ".join(str(skill) for skill in skills[:5]) if isinstance(skills, list) else ""
            job_lines.append(f"{job.get('title', 'Untitled role')} at {company_name or 'company'} ({job.get('status', 'unknown')}; {skill_text})")
        if job_lines:
            lines.append(f"Relevant jobs: {'; '.join(job_lines)}")

    if isinstance(applicants, list) and applicants:
        lines.append(f"Applicants in scope: {len(applicants)}")
        applicant_lines = []
        scored: list[dict[str, Any]] = []
        for applicant in applicants:
            if isinstance(applicant, dict) and isinstance(applicant.get("aiScore"), dict):
                scored.append(applicant)
        scored.sort(key=lambda item: float((item.get("aiScore") or {}).get("score") or 0), reverse=True)
        source = scored[:6] or [item for item in applicants[:6] if isinstance(item, dict)]
        for applicant in source:
            user = applicant.get("users") or {}
            resume = applicant.get("resumes") or {}
            structured = resume.get("structured_data") if isinstance(resume, dict) else {}
            contact = structured.get("contact") if isinstance(structured, dict) else {}
            name = ""
            if isinstance(user, dict):
                name = str(user.get("full_name") or user.get("email") or "")
            if not name and isinstance(contact, dict):
                name = str(contact.get("full_name") or contact.get("email") or "")
            skills = structured.get("skills") if isinstance(structured, dict) else []
            skills_text = ", ".join(str(skill) for skill in skills[:6]) if isinstance(skills, list) else ""
            score = (applicant.get("aiScore") or {}).get("score") if isinstance(applicant.get("aiScore"), dict) else None
            applicant_lines.append(f"{name or 'Candidate'} ({applicant.get('status', 'applied')}; score {score if score is not None else 'unscored'}; {skills_text})")
        if applicant_lines:
            lines.append(f"Candidate snapshot: {'; '.join(applicant_lines)}")

    return "\n".join(lines) if lines else "Backend supplied recruiter context, but it contained no jobs or applicants yet."


# ─── Career Context Helpers ──────────────────────────────────────────────────

def _extract_candidate_summary(ctx: dict[str, Any]) -> str:
    """Build a concise text summary of the candidate's profile for the system prompt."""
    lines: list[str] = []

    profile = ctx.get("profile") or {}
    if profile.get("headline"):
        lines.append(f"Role: {profile['headline']}")
    if profile.get("desired_role"):
        lines.append(f"Target role: {profile['desired_role']}")
    if profile.get("location"):
        lines.append(f"Location: {profile['location']}")
    if profile.get("open_to_remote"):
        lines.append("Open to remote: yes")

    primary = ctx.get("primaryResume") or {}
    structured = primary.get("structuredData") or {}

    # Skills
    skills: list[str] = []
    raw_skills = structured.get("skills") or []
    if isinstance(raw_skills, list):
        for s in raw_skills[:30]:
            if isinstance(s, str):
                skills.append(s)
            elif isinstance(s, dict):
                name = s.get("name") or s.get("skill") or ""
                if name:
                    skills.append(str(name))
    if skills:
        lines.append(f"Skills: {', '.join(skills)}")

    # Summary
    summary = structured.get("professional_summary") or structured.get("summary") or profile.get("summary") or ""
    if summary:
        lines.append(f"Summary: {str(summary)[:400]}")

    # Work experience
    experience = structured.get("work_experience") or structured.get("experience") or []
    if isinstance(experience, list) and experience:
        exp_lines = []
        for exp in experience[:4]:
            if isinstance(exp, dict):
                title = exp.get("title") or exp.get("position") or ""
                company = exp.get("company") or exp.get("employer") or ""
                duration = exp.get("duration") or exp.get("dates") or ""
                if title or company:
                    exp_lines.append(f"{title} at {company} ({duration})".strip(" ()"))
        if exp_lines:
            lines.append(f"Experience: {'; '.join(exp_lines)}")

    # Education
    education = structured.get("education") or []
    if isinstance(education, list) and education:
        edu_lines = []
        for edu in education[:2]:
            if isinstance(edu, dict):
                degree = edu.get("degree") or ""
                institution = edu.get("institution") or edu.get("school") or ""
                if degree or institution:
                    edu_lines.append(f"{degree} from {institution}".strip())
        if edu_lines:
            lines.append(f"Education: {'; '.join(edu_lines)}")

    # Projects
    projects = structured.get("projects") or []
    if isinstance(projects, list) and projects:
        proj_names = [str(p.get("name") or p.get("title") or "") for p in projects[:5] if isinstance(p, dict)]
        proj_names = [n for n in proj_names if n]
        if proj_names:
            lines.append(f"Projects: {', '.join(proj_names)}")

    # Applications
    apps = ctx.get("recentApplications") or []
    if apps:
        app_lines = [f"{a.get('jobTitle','?')} at {a.get('company','?')} ({a.get('status','?')})" for a in apps[:5]]
        lines.append(f"Recent applications: {'; '.join(app_lines)}")

    return "\n".join(lines) if lines else "No profile data available yet."


def _find_job_for_cover_letter(message: str, available_jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Try to match a job from the message by title or company name."""
    lower = message.lower()
    # Exact title match first
    for job in available_jobs:
        title = str(job.get("title") or "").lower()
        company = str(job.get("company") or "").lower()
        if title and title in lower:
            return job
        if company and company in lower:
            return job
    # Return first job if message says "cover letter" generically
    cover_kws = ["cover letter", "write a cover", "draft a cover", "covering letter"]
    if any(kw in lower for kw in cover_kws) and available_jobs:
        return available_jobs[0]
    return None


def _build_cover_letter(
    candidate_summary: str,
    job: dict[str, Any],
    message: str,
) -> str:
    """Generate a cover letter using LLM with full candidate and job context."""
    job_desc = str(job.get("description") or "")[:1200]
    skills = ", ".join(job.get("requiredSkills") or [])
    llm = CachedOpenAIJsonClient().complete_json(
        system_prompt=(
            "You are an expert career coach helping a candidate write a professional, personalised cover letter. "
            "Return JSON with a single key 'coverLetter' containing the full letter as a multi-line string. "
            "The letter must: open with a strong hook, highlight 2-3 specific achievements from their experience, "
            "connect their skills to the job requirements, show genuine enthusiasm, and close with a call to action. "
            "Use a professional but warm tone. Length: 3-4 paragraphs."
        ),
        payload=(
            f"Candidate profile:\n{candidate_summary}\n\n"
            f"Target job: {job.get('title','?')} at {job.get('company','?')}\n"
            f"Required skills: {skills}\n"
            f"Job description: {job_desc}\n\n"
            f"User request: {message}"
        ),
        fallback={},
        temperature=0.6,
    )
    return str(llm.get("coverLetter") or "I could not generate a cover letter. Please ensure you have a primary resume uploaded and try again.")


# ─── Career Assistant ─────────────────────────────────────────────────────────

class CareerAssistantService:
    COVER_KWS = ["cover letter", "write a cover", "draft a cover", "covering letter"]
    SKILL_KWS = ["skill", "learn", "roadmap", "what should i", "how to improve", "technology", "course"]
    RESUME_KWS = ["resume", "cv", "ats", "improve my resume", "fix my resume"]
    JOB_KWS = ["job", "remote", "salary", "find me", "job search", "match me"]
    INTERVIEW_KWS = ["interview", "mock", "prepare", "question"]

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = str(get_any(payload, "message", default=""))
        candidate_context = get_any(payload, "candidateContext", default={})
        context = get_any(payload, "context", default={})

        intent = self._intent(message)
        candidate_summary = _extract_candidate_summary(candidate_context)
        available_jobs = candidate_context.get("availableJobs") or []

        # Cover letter: special-case, return immediately
        if intent == "cover_letter":
            target_job = _find_job_for_cover_letter(message, available_jobs)
            if target_job:
                letter = _build_cover_letter(candidate_summary, target_job, message)
                return self._response(
                    message=f"Here is your personalised cover letter for **{target_job.get('title')} at {target_job.get('company')}**:\n\n{letter}",
                    intent=intent,
                    actions=[{"type": "cover_letter_generated", "jobId": target_job.get("id"), "requiresBackendExecution": False}],
                )
            else:
                # List available jobs for selection
                job_list = "\n".join(
                    f"- **{j.get('title')}** at {j.get('company')}" for j in available_jobs[:10]
                ) or "No open jobs available right now."
                return self._response(
                    message=f"I'd love to write a cover letter for you! Here are the available positions:\n\n{job_list}\n\nJust tell me which one (e.g. 'Write a cover letter for Software Engineer at Acme').",
                    intent=intent,
                    actions=[{"type": "answer_only", "requiresBackendExecution": False}],
                )

        # All other intents: use LLM with full candidate context
        keywords = unique_list(extract_keywords(message))
        actions = self._actions(intent, keywords, context, candidate_context)

        llm_response = self._llm_chat(
            intent=intent,
            message=message,
            candidate_summary=candidate_summary,
            keywords=keywords,
            actions=actions,
            available_jobs=available_jobs,
        )

        return self._response(message=llm_response, intent=intent, actions=actions)

    def _intent(self, message: str) -> str:
        lower = message.lower()
        if any(kw in lower for kw in self.COVER_KWS):
            return "cover_letter"
        if any(kw in lower for kw in self.RESUME_KWS):
            return "resume_advice"
        if any(kw in lower for kw in self.JOB_KWS):
            return "job_search_help"
        if any(kw in lower for kw in self.INTERVIEW_KWS):
            return "interview_prep"
        if any(kw in lower for kw in self.SKILL_KWS):
            return "skill_roadmap"
        return "career_guidance"

    def _actions(self, intent: str, keywords: list[str], context: dict[str, Any], candidate_context: dict[str, Any]) -> list[dict[str, Any]]:
        primary_id = (candidate_context.get("primaryResume") or {}).get("id")
        if intent == "resume_advice":
            return [{"type": "analyze_resume", "resumeId": primary_id, "requiresBackendExecution": bool(primary_id)}]
        if intent == "job_search_help":
            return [{"type": "match_jobs", "filters": {"keywords": keywords}, "requiresBackendExecution": True}]
        if intent == "interview_prep":
            return [{"type": "generate_mock_interview", "focusAreas": keywords[:5], "requiresBackendExecution": True}]
        if intent == "skill_roadmap":
            return [{"type": "create_skill_roadmap", "skills": keywords[:8], "requiresBackendExecution": False}]
        return [{"type": "answer_only", "requiresBackendExecution": False}]

    def _llm_chat(
        self,
        *,
        intent: str,
        message: str,
        candidate_summary: str,
        keywords: list[str],
        actions: list[dict[str, Any]],
        available_jobs: list[dict[str, Any]],
    ) -> str:
        # Stable system prompt (long prefix gets cached by OpenAI prompt caching)
        system_prompt = (
            "You are HireOS AI Career Coach — a world-class, highly personalised AI career advisor. "
            "You always respond in a conversational, direct, and encouraging way. "
            "You have full access to the candidate's profile, resume, skills, work history, and job applications. "
            "Always personalise your response using their actual data — never give generic advice. "
            "If they ask about skills to learn, recommend specifically based on their current skills and experience gaps. "
            "If they ask about their resume, reference their actual work experience and skills. "
            "If they ask about jobs, consider their profile and experience level. "
            "Format responses with markdown: use **bold** for important terms, bullet lists for steps/lists, and clear structure. "
            "Return JSON with a single key 'message' containing your full response as a markdown string."
        )

        job_listing = "\n".join(
            f"- {j.get('title')} at {j.get('company')} (skills: {', '.join((j.get('requiredSkills') or [])[:5])})"
            for j in available_jobs[:8]
        )

        user_payload = (
            f"=== CANDIDATE PROFILE ===\n{candidate_summary}\n\n"
            f"=== AVAILABLE JOBS ===\n{job_listing or 'No open jobs.'}\n\n"
            f"=== CONVERSATION ===\n"
            f"Intent: {intent}\nKeywords: {', '.join(keywords[:10])}\n"
            f"User message: {message}"
        )

        llm = CachedOpenAIJsonClient().complete_json(
            system_prompt=system_prompt,
            payload=user_payload[:8000],
            fallback={},
            temperature=0.5,
        )

        refined = str(llm.get("message") or "").strip()
        if refined:
            return refined

        # Fallback if OpenAI unavailable
        return self._fallback(intent, candidate_summary)

    def _fallback(self, intent: str, candidate_summary: str) -> str:
        if intent == "skill_roadmap":
            return "Based on your profile, focus on skills that appear most in your target roles. Check the job listings in the Jobs tab to see which skills appear most frequently, then build projects using those technologies."
        if intent == "resume_advice":
            return "Visit the **Resumes** tab to run an AI analysis on your resume. I can give specific improvement suggestions based on your actual content once I see the analysis results."
        if intent == "job_search_help":
            return "Head to the **Jobs** tab and click **AI Match** to find roles that fit your resume. I can help you prepare for any of those roles once you have your matches."
        if intent == "interview_prep":
            return "Visit the **Mock Interview** tab and select the role you're targeting. I'll generate questions based on the job description and your skill set."
        return "I'm your AI Career Coach. Ask me about your resume, skills to learn, job matches, interview prep, or cover letters for any available position."

    def _response(self, *, message: str, intent: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "success": True,
            "data": {"intent": intent, "actions": actions, "cachePolicy": "prompt_hash_ttl_3600"},
            "message": message,
            "intent": intent,
            "actions": actions,
            "confidence": 0.92,
            "warnings": [],
            "reviewRequired": False,
            "error": None,
        }


def _cached_chat_refinement(
    *,
    role: str,
    intent: str,
    message: str,
    keywords: list[str],
    actions: list[dict[str, Any]],
    context: dict[str, Any],
    context_summary: str,
    fallback: str,
) -> str:
    context_keys = sorted(str(key) for key in context.keys())[:12] if isinstance(context, dict) else []
    llm = CachedOpenAIJsonClient().complete_json(
        system_prompt=(
            "Return compact JSON with key message only. You are HireOS AI Recruiter for a recruiter user. "
            "Use the supplied scoped recruiter context: recruiter profile, company, posted jobs, applicants, resumes, and AI scores. "
            "Never invent candidates or jobs. If data is missing, say what is missing. "
            "Keep backend actions explicit and do not expose sensitive full resume text."
        ),
        payload=str(
            {
                "role": role,
                "intent": intent,
                "userMessage": message[:500],
                "keywords": keywords[:10],
                "actions": actions[:3],
                "contextKeys": context_keys,
                "scopedRecruiterContext": context_summary[:6000],
            }
        ),
        fallback={},
    )
    refined = str(llm.get("message") or "").strip()
    return refined or fallback
