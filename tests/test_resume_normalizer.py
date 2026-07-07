from app.integrations.document_extraction.normalizer import normalize_resume_extraction


def test_normalize_resume_extraction_maps_common_fields() -> None:
    state = {
        "merged_extraction": {
            "Full Name": {"value": "Jane Doe"},
            "Email": {"value": "jane@example.com"},
            "Skills": {"value": "Python, FastAPI, AWS"},
            "Projects": {
                "value": [
                    {
                        "name": "Hiring Agent",
                        "description": "AI recruiter workflow",
                        "technologies": ["LangGraph", "OpenAI"],
                    }
                ]
            },
        },
        "page_images": [{"text_content": "https://github.com/janedoe"}],
    }

    resume = normalize_resume_extraction(state)

    assert resume.contact.full_name == "Jane Doe"
    assert resume.contact.email == "jane@example.com"
    assert resume.skills == ["Python", "FastAPI", "AWS"]
    assert resume.projects[0].name == "Hiring Agent"
    assert resume.contact.github == "https://github.com/janedoe"


def test_normalize_resume_extraction_repairs_missing_sections_from_raw_text() -> None:
    state = {
        "merged_extraction": {},
        "page_images": [
            {
                "text_content": """
ZARNAB ALI
Islamabad, Pakistan| P: +92 3440997390| zarnabalibhatti@gmail.com

EDUCATION
FAST NUCES
Islamabad, Pakistan
Bachelor of Software Engineering
2022 - 2026

Skills
Programming Languages: Python, JavaScript
DevOps: Docker, Kubernetes, AWS
Database: PostgreSQL, Supabase, Redis
Frameworks/Libraries: React.js, Node.js, Next.js, Flask

WORK EXPERIENCE
AI AUTOMATION & INTEGRATION SPECIALIST
Mar 2026 - Present
Proto IT Consultants
Islamabad, Pakistan
- Developed end-to-end automation workflows using n8n, Make.io, and Zapier.
- Engineered integrated solutions using Softr and Airtable.

AI FULL STACK DEVELOPER
June 2024 - Feb 2026
Rubrix Code
Remote
- Delivered 9+ end-to-end projects, cutting turnaround time by 30%.
- Led architecture planning, increasing project delivery speed by 25%.

PROJECTS
WEARISM AI FASHION INTELLIGENCE PLATFORM
- Developed an AI-powered fashion platform featuring 4 core modules.
- Engineered a multi-stage AI pipeline consisting of 5 specialized models.

TOOLVIO DYNAMIC BACKEND APPLICATION
- Developed a schema-driven full-stack platform enabling dynamic entity creation.
"""
            }
        ],
    }

    resume = normalize_resume_extraction(state)

    assert resume.contact.full_name == "ZARNAB ALI"
    assert resume.contact.email == "zarnabalibhatti@gmail.com"
    assert resume.education[0].institution == "FAST NUCES"
    assert resume.education[0].degree == "Bachelor of Software Engineering"
    assert len(resume.experience) == 2
    assert resume.experience[0].title == "AI AUTOMATION & INTEGRATION SPECIALIST"
    assert resume.experience[0].company == "Proto IT Consultants"
    assert resume.experience[1].company == "Rubrix Code"
    assert len(resume.projects) == 2
    assert resume.projects[0].name == "WEARISM AI FASHION INTELLIGENCE PLATFORM"
    assert "Python" in resume.skills
    assert "Docker" in resume.skills
