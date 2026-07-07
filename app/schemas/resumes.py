from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ErrorDetail


class ResumeExtractionOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    force_reprocess: bool = Field(default=False, alias="forceReprocess")
    include_raw_sections: bool = Field(default=True, alias="includeRawSections")


class ResumeExtractionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(alias="documentId")
    candidate_id: str | None = Field(default=None, alias="candidateId")
    file_path: str | None = Field(default=None, alias="filePath")
    file_name: str | None = Field(default=None, alias="fileName")
    file_content_base64: str | None = Field(default=None, alias="fileContentBase64")
    source_mime_type: str = Field(alias="sourceMimeType")
    options: ResumeExtractionOptions = Field(default_factory=ResumeExtractionOptions)


class LinkItem(BaseModel):
    label: str
    url: str


class ContactInfo(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class ExperienceItem(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    achievements: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProjectItem(BaseModel):
    name: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class StructuredResume(BaseModel):
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    links: list[LinkItem] = Field(default_factory=list)
    raw_sections: dict[str, Any] = Field(default_factory=dict)


class ExtractionProvenance(BaseModel):
    source: str = "agentic-document-extraction-pdf"
    document_id: str
    candidate_id: str | None = None
    file_path: str
    processing_id: str | None = None
    document_type: str | None = None
    schema_name: str | None = None
    total_vlm_calls: int = 0
    raw_confidence: float = 0.0


class ResumeExtractionData(BaseModel):
    document_id: str = Field(alias="documentId")
    candidate_id: str | None = Field(default=None, alias="candidateId")
    structured_resume: StructuredResume = Field(alias="structuredResume")
    provenance: ExtractionProvenance


class ResumeExtractionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool
    data: ResumeExtractionData | None = None
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = Field(default=False, alias="reviewRequired")
    error: ErrorDetail | None = None
