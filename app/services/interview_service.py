import re
from typing import Any

from app.clients.openai_client import CachedOpenAIJsonClient
from app.services.ai_utils import extract_job_requirements, extract_resume_skills, get_any, unique_list


class InterviewService:
    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        resume = get_any(payload, "structuredResume", "structured_resume", default={})
        job = get_any(payload, "job", default={})
        recruiter_context = get_any(payload, "recruiterContext", "recruiter_context", default={})
        focus_areas = unique_list(get_any(payload, "focusAreas", "focus_areas", default=[]))
        difficulty = self._difficulty(get_any(payload, "difficulty", default="medium"))
        question_count = int(get_any(payload, "questionCount", "question_count", default=10) or 10)
        skills = extract_resume_skills(resume)
        requirements = extract_job_requirements(job)
        topics = unique_list([*focus_areas, *requirements[:6], *skills[:6]])[:10]
        questions = self._questions(topics, resume, job, difficulty, question_count)
        llm = CachedOpenAIJsonClient().complete_json(
            system_prompt=(
                "Return compact JSON with optional key questions containing unique interview question objects. "
                "Each object must include question, type, difficulty, skillTested, rubric, expectedSignals. "
                "Avoid duplicate wording and generic experience-only questions."
            ),
            payload=(
                f"Recruiter/company context: {_summarize_recruiter_context(recruiter_context)}\n"
                f"Resume: {resume}\n"
                f"Job: {job}\n"
                f"Focus areas: {topics}\n"
                f"Difficulty: {difficulty}"
            ),
            fallback={},
        )
        if isinstance(llm.get("questions"), list) and llm["questions"]:
            questions = self._normalize_llm_questions(llm["questions"], difficulty, question_count) or questions
        return {
            "success": True,
            "data": {"questions": questions, "focusAreas": topics, "difficulty": difficulty},
            "questions": questions,
            "confidence": 0.86,
            "warnings": [],
            "reviewRequired": False,
            "error": None,
        }

    def evaluate_mock_answer(self, payload: dict[str, Any]) -> dict[str, Any]:
        question = str(get_any(payload, "question", default=""))
        answer = str(get_any(payload, "answer", default=""))

        if not answer.strip():
            return {
                "success": True,
                "data": {"technicalScore": 0, "communication": 0, "confidence": 0, "clarity": 0, "completeness": 0, "feedback": ["No answer provided."], "suggestedNextQuestion": ""},
                "score": 0, "suggestions": ["No answer provided."], "warnings": ["Empty answer"], "confidence": 0.0, "reviewRequired": True, "error": None,
            }

        # Use LLM for real evaluation
        llm = CachedOpenAIJsonClient().complete_json(
            system_prompt=(
                "You are an expert technical interviewer. Evaluate the candidate's answer to the given question. "
                "Return JSON with these integer fields (0-100): technicalScore, clarity, completeness, communication. "
                "Also return: feedback (array of 1-3 specific improvement tips as strings), overallScore (integer 0-100). "
                "Be realistic and differentiated — a short vague answer should score 20-40, a solid answer 60-80, an excellent one 85-100. "
                "Do NOT give everyone 80. Base scores on actual content quality."
            ),
            payload=f"Question: {question}\n\nCandidate Answer: {answer}",
            fallback={},
        )

        technical = int(llm.get("technicalScore") or 0)
        clarity = int(llm.get("clarity") or 0)
        completeness = int(llm.get("completeness") or 0)
        communication = int(llm.get("communication") or 0)
        overall = int(llm.get("overallScore") or 0)

        # Fallback to heuristic if LLM returned zeros (e.g. OpenAI unavailable)
        if not any([technical, clarity, completeness, communication, overall]):
            technical = self._score_answer(question, answer)
            clarity = min(100, max(25, round(len(answer.split()) * 2.5)))
            completeness = min(100, 35 + len(re.findall(r"\b(because|for example|tradeoff|depends|first|second)\b", answer.lower())) * 15)
            communication = round((clarity + completeness) / 2)
            overall = min(100, round((technical + communication + completeness) / 3) + 5)

        raw_feedback = llm.get("feedback")
        if isinstance(raw_feedback, list) and raw_feedback:
            feedback = [str(f) for f in raw_feedback]
        else:
            feedback = self._feedback(technical, clarity, completeness)

        return {
            "success": True,
            "data": {
                "technicalScore": technical,
                "communication": communication,
                "confidence": overall,
                "clarity": clarity,
                "completeness": completeness,
                "feedback": feedback,
                "suggestedNextQuestion": self._next_question(question),
            },
            "score": overall,
            "suggestions": feedback,
            "warnings": [],
            "confidence": 0.9,
            "reviewRequired": overall < 55,
            "error": None,
        }

    def _difficulty(self, value: Any) -> str:
        cleaned = str(value or "medium").strip().lower()
        if cleaned in {"easy", "junior", "beginner"}:
            return "easy"
        if cleaned in {"hard", "senior", "advanced"}:
            return "hard"
        return "medium"

    def _questions(
        self,
        topics: list[str],
        resume: dict[str, Any],
        job: dict[str, Any],
        difficulty: str,
        question_count: int,
    ) -> list[dict[str, Any]]:
        base_topics = topics or ["system design", "recent project", "debugging", "team communication"]
        project_names = [
            str(project.get("name"))
            for project in get_any(resume, "projects", default=[])
            if isinstance(project, dict) and project.get("name")
        ]
        title = str(get_any(job, "title", default="the target role"))
        templates = [
            (
                "technical",
                "How would you use {topic} to build a reliable feature for {title}, and what failure mode would you guard against first?",
                ["Correct concept usage", "Failure-mode awareness", "Practical implementation detail"],
                ["technical depth", "risk thinking", "implementation clarity"],
            ),
            (
                "debugging",
                "A production issue appears in a {topic}-based service after deployment. What signals would you inspect and what would you change first?",
                ["Prioritizes logs, metrics, and traces", "Forms a testable hypothesis", "Avoids unsafe blind changes"],
                ["debugging process", "observability", "judgment"],
            ),
            (
                "system_design",
                "Design the {topic} part of a hiring platform that must handle bulk resume processing. Include API boundaries, queues, retries, and data validation.",
                ["Clear service boundary", "Queue and retry design", "Validation and persistence plan"],
                ["architecture", "scalability", "data safety"],
            ),
            (
                "behavioral",
                "Tell me about a time you had to make a tradeoff involving {topic}. What options did you reject and how did you measure the outcome?",
                ["Specific situation", "Rejected alternatives", "Measured result"],
                ["ownership", "communication", "impact"],
            ),
            (
                "project_deep_dive",
                "Pick one project{project_hint} and explain the hardest engineering decision. How did {topic} affect that decision?",
                ["Concrete project context", "Decision rationale", "Lessons learned"],
                ["project fluency", "tradeoff reasoning", "reflection"],
            ),
            (
                "role_fit",
                "For {title}, where is your {topic} experience strongest and where would you need ramp-up time?",
                ["Honest self-assessment", "Role alignment", "Learning plan"],
                ["self-awareness", "role fit", "growth mindset"],
            ),
        ]
        if difficulty == "easy":
            templates = templates[:2] + templates[3:5]
        elif difficulty == "hard":
            templates = [templates[2], templates[1], templates[0], templates[4], templates[3], templates[5]]

        questions: list[dict[str, Any]] = []
        seen: set[str] = set()
        index = 0
        while len(questions) < max(1, min(question_count, 15)) and index < len(base_topics) * len(templates):
            topic = base_topics[index % len(base_topics)]
            q_type, template, rubric, signals = templates[index % len(templates)]
            project_hint = f" such as {project_names[index % len(project_names)]}" if project_names else ""
            question = template.format(topic=topic, title=title, project_hint=project_hint)
            key = question.lower()
            if key not in seen:
                seen.add(key)
                questions.append(
                    {
                        "question": question,
                        "type": q_type,
                        "difficulty": difficulty if q_type != "system_design" else ("hard" if difficulty != "easy" else "medium"),
                        "skillTested": topic,
                        "rubric": rubric,
                        "expectedSignals": signals,
                    }
                )
            index += 1
        return questions

    def _normalize_llm_questions(
        self,
        questions: list[Any],
        difficulty: str,
        question_count: int,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in questions:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            if not question or question.lower() in seen:
                continue
            seen.add(question.lower())
            normalized.append(
                {
                    "question": question,
                    "type": str(item.get("type") or "technical"),
                    "difficulty": str(item.get("difficulty") or difficulty),
                    "skillTested": str(item.get("skillTested") or item.get("skill_tested") or "role fit"),
                    "rubric": item.get("rubric") if isinstance(item.get("rubric"), list) else ["Specificity", "Correctness", "Tradeoffs"],
                    "expectedSignals": item.get("expectedSignals") if isinstance(item.get("expectedSignals"), list) else ["clarity", "depth"],
                }
            )
        return normalized[: max(1, min(question_count, 15))]

    def _score_answer(self, question: str, answer: str) -> int:
        q_terms = set(re.findall(r"[a-zA-Z][a-zA-Z+#.]{3,}", question.lower()))
        a_terms = set(re.findall(r"[a-zA-Z][a-zA-Z+#.]{3,}", answer.lower()))
        overlap = len(q_terms & a_terms)
        return min(100, max(20, 35 + overlap * 12 + len(answer.split()) // 4))

    def _feedback(self, technical: int, clarity: int, completeness: int) -> list[str]:
        feedback = []
        if technical < 70:
            feedback.append("Tie the answer more directly to the technical concepts in the question.")
        if clarity < 70:
            feedback.append("Use a clearer structure: context, action, result, and tradeoff.")
        if completeness < 70:
            feedback.append("Add concrete examples, constraints, and measurable outcomes.")
        return feedback or ["Strong answer. Add one measurable result to make it even stronger."]

    def _next_question(self, question: str) -> str:
        if "design" in question.lower():
            return "What bottleneck would you monitor first and why?"
        return "Can you give a concrete example with impact metrics?"


def _summarize_recruiter_context(context: Any) -> str:
    if not isinstance(context, dict) or not context:
        return "No recruiter context supplied."
    recruiter = context.get("recruiter") or {}
    companies = context.get("companies") or []
    applicants = context.get("applicants") or []
    pieces: list[str] = []
    if isinstance(recruiter, dict):
        pieces.append(f"Recruiter {recruiter.get('fullName') or recruiter.get('email') or 'Unknown'}")
    if isinstance(companies, list) and companies:
        company_names = [str(company.get("name")) for company in companies[:3] if isinstance(company, dict) and company.get("name")]
        if company_names:
            pieces.append(f"companies: {', '.join(company_names)}")
    if isinstance(applicants, list):
        pieces.append(f"scoped applicants: {len(applicants)}")
    return "; ".join(pieces) or "Recruiter context supplied without usable summary fields."
