import re
from typing import Any

from app.schemas.resumes import (
    ContactInfo,
    EducationItem,
    ExperienceItem,
    LinkItem,
    ProjectItem,
    StructuredResume,
)


def normalize_resume_extraction(state: dict[str, Any]) -> StructuredResume:
    merged = _flatten_values(state.get("merged_extraction", {}))
    raw_text = _join_raw_text(state)
    parsed = _parse_resume_text(raw_text)

    full_name = _first_text(merged, ["full_name", "name", "candidate_name"])
    email = _first_text(merged, ["email", "email_address"]) or _find_email(raw_text)
    phone = _first_text(merged, ["phone", "phone_number", "mobile"]) or _find_phone(raw_text)

    links = _extract_links(merged, raw_text)
    skills = _as_string_list(_first_value(merged, ["skills", "technical_skills", "core_skills"])) or parsed["skills"]
    experience = _as_experience_list(
        _first_value(merged, ["work_experience", "experience", "employment_history"])
    )
    education = _as_education_list(_first_value(merged, ["education", "academic_background"]))
    projects = _as_project_list(_first_value(merged, ["projects", "portfolio_projects"]))

    return StructuredResume(
        contact=ContactInfo(
            full_name=full_name or parsed["contact"].get("full_name"),
            email=email,
            phone=phone,
            location=_first_text(merged, ["location", "address", "city"]) or parsed["contact"].get("location"),
            linkedin=_first_link(links, "linkedin"),
            github=_first_link(links, "github"),
            portfolio=_first_link(links, "portfolio"),
        ),
        summary=_first_text(merged, ["professional_summary", "summary", "profile"]) or parsed["summary"],
        skills=skills,
        experience=experience or parsed["experience"],
        education=education or parsed["education"],
        projects=projects or parsed["projects"],
        certifications=_as_string_list(_first_value(merged, ["certifications", "certificates"])),
        languages=_as_string_list(_first_value(merged, ["languages"])),
        achievements=_as_string_list(_first_value(merged, ["achievements", "awards"])) or parsed["achievements"],
        links=links,
        raw_sections={**merged, "parsed_sections": parsed["raw_sections"]},
    )


def _flatten_values(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    output: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = _normalize_key(key)
        if isinstance(item, dict) and "value" in item:
            output[normalized_key] = item.get("value")
        else:
            output[normalized_key] = item
    return output


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _first_value(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        normalized = _normalize_key(key)
        value = data.get(normalized)
        if value not in (None, "", [], {}):
            return value
    return None


def _first_text(data: dict[str, Any], keys: list[str]) -> str | None:
    value = _first_value(data, keys)
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _as_string_list(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, str):
        parts = re.split(r"[\n,;|]+", value)
        return [_clean(part) for part in parts if _clean(part)]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(_clean(item))
            elif isinstance(item, dict):
                text = item.get("name") or item.get("title") or item.get("value")
                if text:
                    result.append(_clean(str(text)))
        return [item for item in result if item]
    return [_clean(str(value))]


def _as_experience_list(value: Any) -> list[ExperienceItem]:
    items = _as_dict_list(value)
    return [
        ExperienceItem(
            company=_optional_text(item, ["company", "employer", "organization"]),
            title=_optional_text(item, ["title", "role", "position"]),
            location=_optional_text(item, ["location"]),
            start_date=_optional_text(item, ["start_date", "start"]),
            end_date=_optional_text(item, ["end_date", "end"]),
            description=_optional_text(item, ["description", "summary"]),
            achievements=_as_string_list(item.get("achievements") or item.get("bullets")),
        )
        for item in items
    ]


def _as_education_list(value: Any) -> list[EducationItem]:
    items = _as_dict_list(value)
    return [
        EducationItem(
            institution=_optional_text(item, ["institution", "school", "university"]),
            degree=_optional_text(item, ["degree"]),
            field=_optional_text(item, ["field", "major"]),
            start_date=_optional_text(item, ["start_date", "start"]),
            end_date=_optional_text(item, ["end_date", "graduation_date", "end"]),
        )
        for item in items
    ]


def _as_project_list(value: Any) -> list[ProjectItem]:
    items = _as_dict_list(value)
    return [
        ProjectItem(
            name=_optional_text(item, ["name", "title"]),
            description=_optional_text(item, ["description", "summary"]),
            technologies=_as_string_list(item.get("technologies") or item.get("skills")),
            url=_optional_text(item, ["url", "link"]),
        )
        for item in items
    ]


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, dict):
        return [{_normalize_key(str(k)): v for k, v in value.items()}]
    if isinstance(value, list):
        return [
            {_normalize_key(str(k)): v for k, v in item.items()}
            for item in value
            if isinstance(item, dict)
        ]
    if isinstance(value, str):
        return [{"description": value}]
    return []


def _optional_text(data: dict[str, Any], keys: list[str]) -> str | None:
    value = _first_value(data, keys)
    if value in (None, "", [], {}):
        return None
    return _clean(str(value))


def _join_raw_text(state: dict[str, Any]) -> str:
    page_images = state.get("page_images", [])
    if not isinstance(page_images, list):
        return ""
    return "\n".join(
        str(page.get("text_content", ""))
        for page in page_images
        if isinstance(page, dict) and page.get("text_content")
    )


def _parse_resume_text(text: str) -> dict[str, Any]:
    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    sections = _split_sections(lines)
    contact = _parse_contact(lines)
    return {
        "contact": contact,
        "summary": _parse_summary(lines),
        "skills": _parse_skills(sections.get("skills", []), text),
        "experience": _parse_experience(sections.get("work_experience", [])),
        "education": _parse_education(sections.get("education", [])),
        "projects": _parse_projects(sections.get("projects", [])),
        "achievements": _find_achievement_lines(lines),
        "raw_sections": sections,
    }


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    heading_map = {
        "education": "education",
        "skills": "skills",
        "technical skills": "skills",
        "work experience": "work_experience",
        "experience": "work_experience",
        "professional experience": "work_experience",
        "projects": "projects",
        "certifications": "certifications",
        "languages": "languages",
    }
    sections: dict[str, list[str]] = {}
    current = "header"
    sections[current] = []
    for line in lines:
        normalized = _normalize_heading(line)
        if normalized in heading_map:
            current = heading_map[normalized]
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _normalize_heading(line: str) -> str:
    return re.sub(r"[^a-z ]+", "", line.lower()).strip()


def _parse_contact(lines: list[str]) -> dict[str, str | None]:
    header = lines[:8]
    full_name = header[0] if header else None
    location = None
    for line in header[1:]:
        if _normalize_heading(line) in {"education", "skills", "work experience", "projects"}:
            continue
        if "|" in line:
            location = line.split("|")[0].strip()
            break
        if "@" not in line and not re.search(r"\+?\d[\d\s().-]{7,}\d", line):
            location = line.strip()
            break
    return {
        "full_name": full_name,
        "location": location,
    }


def _parse_summary(lines: list[str]) -> str | None:
    skipped = {"education", "skills", "work experience", "experience", "projects"}
    content = []
    for line in lines[:10]:
        if _normalize_heading(line) in skipped:
            break
        if "@" in line or re.search(r"\+?\d[\d\s().-]{7,}\d", line):
            continue
        if line.isupper() and len(line.split()) <= 4:
            continue
        content.append(line)
    return " ".join(content[:3]) or None


def _parse_skills(skill_lines: list[str], full_text: str) -> list[str]:
    known = [
        "Python",
        "Dart",
        "Java",
        "JavaScript",
        "TypeScript",
        "Solidity",
        "C++",
        "C#",
        "React.js",
        "React",
        "Node.js",
        "Express.js",
        "Next.js",
        "Three.js",
        "React Native",
        "Flutter",
        "Spring Boot",
        "Vue.js",
        "Angular",
        "Docker",
        "Kubernetes",
        "AWS",
        "MySQL",
        "SQL",
        "SSMS",
        "MongoDB",
        "PostgreSQL",
        "Supabase",
        "Redis",
        "Firebase",
        "OpenCV",
        "PyTorch",
        "YOLO",
        "YOLOv8",
        "YOLOv11",
        "Flask",
        "n8n",
        "Make.io",
        "Zapier",
        "Softr",
        "Airtable",
        "Figma",
        "Git",
    ]
    source = "\n".join(skill_lines) if skill_lines else full_text
    lowered = source.lower()
    found = []
    for skill in known:
        pattern = re.escape(skill.lower()).replace(r"\.", r"\.?")
        if re.search(rf"(?<![a-z0-9+#]){pattern}(?![a-z0-9+#])", lowered):
            found.append(skill)
    return _dedupe(found)


def _parse_education(lines: list[str]) -> list[EducationItem]:
    if not lines:
        return []
    text = "\n".join(lines)
    date = _find_date_range(text)
    institution = None
    degree = None
    location = None
    for line in lines:
        lower = line.lower()
        if institution is None and any(token in lower for token in ["university", "nuces", "college", "institute", "school"]):
            institution = line
            continue
        if degree is None and any(token in lower for token in ["bachelor", "master", "bs ", "ms ", "degree", "software engineering"]):
            degree = line
            continue
        if location is None and "," in line and not _looks_like_date(line):
            location = line
    return [
        EducationItem(
            institution=institution,
            degree=degree,
            field=_extract_field_from_degree(degree),
            start_date=date[0],
            end_date=date[1],
        )
    ]


def _parse_experience(lines: list[str]) -> list[ExperienceItem]:
    blocks = _split_role_blocks(lines)
    experiences = []
    for block in blocks:
        item = _parse_experience_block(block)
        if item and (item.title or item.company or item.achievements):
            experiences.append(item)
    return experiences


def _split_role_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        starts_new = bool(current) and _looks_like_role_title(line)
        if starts_new:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _parse_experience_block(block: list[str]) -> ExperienceItem | None:
    if not block:
        return None
    title = block[0]
    date = _find_date_range("\n".join(block))
    date_index = next((index for index, line in enumerate(block) if _looks_like_date(line)), -1)
    company = None
    location = None
    if date_index >= 0:
        company = _next_non_bullet(block, date_index + 1)
        location = _next_non_bullet(block, date_index + 2)
    bullets = [_clean_bullet(line) for line in block if _is_bullet(line)]
    return ExperienceItem(
        company=company,
        title=title,
        location=location,
        start_date=date[0],
        end_date=date[1],
        description=None,
        achievements=[bullet for bullet in bullets if bullet],
    )


def _parse_projects(lines: list[str]) -> list[ProjectItem]:
    projects: list[ProjectItem] = []
    current_name: str | None = None
    current_bullets: list[str] = []
    for line in lines:
        if _is_project_heading(line):
            if current_name:
                projects.append(_project_from_block(current_name, current_bullets))
            current_name = line
            current_bullets = []
        elif current_name and _is_bullet(line):
            current_bullets.append(_clean_bullet(line))
    if current_name:
        projects.append(_project_from_block(current_name, current_bullets))
    return projects


def _project_from_block(name: str, bullets: list[str]) -> ProjectItem:
    description = " ".join(bullets[:3]) if bullets else None
    technologies = _parse_skills([name, *bullets], "")
    return ProjectItem(
        name=name,
        description=description,
        technologies=technologies,
        url=_find_url(" ".join([name, *bullets])),
    )


def _find_achievement_lines(lines: list[str]) -> list[str]:
    achievements = []
    for line in lines:
        if _is_bullet(line) and re.search(r"\b\d+%|\b\d+\+|\bover \d+|\b\d+x|\breduced\b|\bimproved\b|\bboost", line.lower()):
            achievements.append(_clean_bullet(line))
    return achievements[:20]


def _find_date_range(text: str) -> tuple[str | None, str | None]:
    range_match = re.search(
        r"((?:Jan|Feb|Mar|Apr|May|Jun|June|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4})\s*[-–]\s*((?:Jan|Feb|Mar|Apr|May|Jun|June|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4}|Present)",
        text,
        flags=re.IGNORECASE,
    )
    if range_match:
        return _clean(range_match.group(1)), _clean(range_match.group(2))
    return None, None


def _looks_like_role_title(line: str) -> bool:
    normalized = _normalize_heading(line)
    role_words = {"developer", "engineer", "specialist", "intern", "consultant", "architect", "manager"}
    return _mostly_upper(line) and any(word in normalized.split() for word in role_words)


def _is_project_heading(line: str) -> bool:
    if _is_bullet(line) or _looks_like_date(line):
        return False
    normalized = _normalize_heading(line)
    if normalized in {"projects", "work experience", "education", "skills"}:
        return False
    return _mostly_upper(line) and len(line.split()) >= 2


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^(?:[\u2022\u25cf\-*]|o\s+|â)", line.strip(), flags=re.IGNORECASE))


def _clean_bullet(line: str) -> str:
    return _clean(re.sub(r"^(?:[\u2022\u25cf\-*]|o\s+|â\S*)\s*", "", line.strip(), flags=re.IGNORECASE))


def _looks_like_date(line: str) -> bool:
    return bool(re.search(r"\d{4}|present|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", line, flags=re.IGNORECASE))


def _next_non_bullet(lines: list[str], start: int) -> str | None:
    for line in lines[start:]:
        if not _is_bullet(line) and not _looks_like_date(line):
            return line
    return None


def _extract_field_from_degree(degree: str | None) -> str | None:
    if not degree:
        return None
    lower = degree.lower()
    if "software engineering" in lower:
        return "Software Engineering"
    if "computer science" in lower:
        return "Computer Science"
    return None


def _find_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s)>\]]+", text)
    return match.group(0) if match else None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _mostly_upper(line: str) -> bool:
    letters = re.findall(r"[A-Za-z]", line)
    if not letters:
        return False
    upper = sum(1 for letter in letters if letter.isupper())
    return upper / len(letters) >= 0.65


def _find_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else None


def _find_phone(text: str) -> str | None:
    match = re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", text)
    return _clean(match.group(0)) if match else None


def _extract_links(data: dict[str, Any], text: str) -> list[LinkItem]:
    links: list[LinkItem] = []
    for label, keys in {
        "linkedin": ["linkedin", "linkedin_url"],
        "github": ["github", "github_url"],
        "portfolio": ["portfolio", "website", "personal_website"],
    }.items():
        value = _first_text(data, keys)
        if value:
            links.append(LinkItem(label=label, url=value))

    for url in re.findall(r"https?://[^\s)>\]]+", text):
        lowered = url.lower()
        label = "portfolio"
        if "linkedin.com" in lowered:
            label = "linkedin"
        elif "github.com" in lowered:
            label = "github"
        if not any(existing.url == url for existing in links):
            links.append(LinkItem(label=label, url=url))
    return links


def _first_link(links: list[LinkItem], label: str) -> str | None:
    for link in links:
        if link.label == label:
            return link.url
    return None


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
