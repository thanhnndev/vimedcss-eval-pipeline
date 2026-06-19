from pydantic import BaseModel, Field
from typing import Optional, Literal


class ICD10Record(BaseModel):
    code: str
    level: Literal["chapter", "section", "type", "disease"]
    label_en: str
    label_vi: str
    chapter_code: str
    chapter_label_en: str
    chapter_label_vi: str
    parent_code: Optional[str] = None
    source: str = "kcb_icd10_tt06"
    source_url: str
    fetched_at: str  # ISO 8601


class ICD10ErrorRecord(BaseModel):
    code: str
    language: Literal["en", "vi"]
    error_type: str  # "http_error", "parse_error", "status_failure", "timeout", "missing_language"
    error_message: str
    attempt: int
    timestamp: str  # ISO 8601
