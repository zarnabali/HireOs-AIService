import re
from collections.abc import Iterable
from typing import Any


PROTECTED_ATTRIBUTE_TERMS = {
    "age",
    "gender",
    "race",
    "religion",
    "disability",
    "marital",
    "ethnicity",
    "nationality",
    "pregnancy",
    "veteran",
    "photo",
}

COMMON_TECH_SKILLS = {
    "python",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "node.js",
    "express",
    "fastapi",
    "django",
    "flask",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "postgres",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "supabase",
    "graphql",
    "rest",
    "langgraph",
    "langchain",
    "openai",
    "celery",
    "sql",
    "java",
    "go",
    "rust",
    "c++",
    "c#",
    "terraform",
    "linux",
    "git",
}


def normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def unique_list(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item)).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def get_any(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, "", [], {}):
            return data[key]
    return default


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if hasattr(value, "model_dump"):
        return flatten_text(value.model_dump())
    return str(value)


def extract_resume_skills(structured_resume: dict[str, Any]) -> list[str]:
    skills = get_any(structured_resume, "skills", "Skills", default=[])
    if isinstance(skills, str):
        explicit = re.split(r"[\n,;|]+", skills)
    elif isinstance(skills, list):
        explicit = []
        for skill in skills:
            if isinstance(skill, dict):
                explicit.append(str(get_any(skill, "name", "title", "value", default="")))
            else:
                explicit.append(str(skill))
    else:
        explicit = []

    text = flatten_text(structured_resume).lower()
    inferred = [skill for skill in COMMON_TECH_SKILLS if skill in text]
    return unique_list([*explicit, *inferred])


def extract_keywords(text: str) -> list[str]:
    lowered = text.lower()
    skills = [skill for skill in COMMON_TECH_SKILLS if skill in lowered]
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.]{2,}", lowered)
    ignored = {
        "the",
        "and",
        "with",
        "for",
        "you",
        "our",
        "are",
        "will",
        "from",
        "this",
        "that",
        "role",
        "work",
        "team",
        "experience",
    }
    domain_words = [word for word in words if word not in ignored and len(word) > 3]
    return unique_list([*skills, *domain_words])[:40]


def extract_job_requirements(job: dict[str, Any]) -> list[str]:
    requirements = get_any(job, "requirements", "required_skills", "requiredSkills", default=[])
    if isinstance(requirements, str):
        explicit = re.split(r"[\n,;|]+", requirements)
    elif isinstance(requirements, list):
        explicit = [flatten_text(item) for item in requirements]
    else:
        explicit = []
    description = flatten_text(
        {
            "title": get_any(job, "title", default=""),
            "description": get_any(job, "description", "job_description", "jobDescription", default=""),
            "responsibilities": get_any(job, "responsibilities", default=""),
        }
    )
    return unique_list([*explicit, *extract_keywords(description)])[:30]


def overlap_score(source: Iterable[str], requirements: Iterable[str]) -> tuple[int, list[str], list[str]]:
    source_norm = {normalize_token(item) for item in source if str(item).strip()}
    req_norm = [normalize_token(item) for item in requirements if str(item).strip()]
    matched_norm = [item for item in req_norm if item in source_norm or any(item in s or s in item for s in source_norm)]
    missing_norm = [item for item in req_norm if item not in matched_norm]
    if not req_norm:
        return 50, [], []
    score = round((len(matched_norm) / len(req_norm)) * 100)
    return score, unique_list(matched_norm), unique_list(missing_norm)


def quantified_achievement_count(structured_resume: dict[str, Any]) -> int:
    text = flatten_text(structured_resume)
    return len(re.findall(r"(\d+%|\$\d+|\d+x|\d+\+|\b\d{2,}\b)", text))


def protected_attribute_warnings(value: Any) -> list[str]:
    text = flatten_text(value).lower()
    found = sorted(term for term in PROTECTED_ATTRIBUTE_TERMS if term in text)
    if not found:
        return []
    return [f"Protected-attribute terms detected and excluded from scoring: {', '.join(found)}"]
