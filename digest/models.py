from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import unquote
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

Category = Literal['surgery', 'internal_medicine', 'oncology', 'other']
Evidence = Literal['abstract', 'full_text']
Design = Literal['randomized_controlled_trial', 'prospective', 'retrospective', 'systematic_review', 'case_series', 'case_report', 'other']
TAGS = {'oncology','orthopedics','soft_tissue_surgery','cardiology','nephrology','endocrinology','gastroenterology','neurology','respiratory','infectious_disease','emergency_critical_care','anesthesia','minimally_invasive_surgery','surgery','internal_medicine'}

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def normalize_doi(value):
    if not value:
        return None
    value = unquote(str(value)).strip().lower()
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value)
    if not re.fullmatch(r'10\.\d{4,9}/[^\s<>]+', value):
        raise ValueError('Invalid DOI')
    return value

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Metadata(StrictModel):
    title: str = Field(min_length=1)
    journal: str = Field(min_length=1)
    journal_id: str
    publication_date: date | None = None
    online_publication_date: date | None = None
    publication_date_raw: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    publisher_url: str | None = None
    pubmed_url: str | None = None
    abstract: str | None = None
    source: str
    source_id: str | None = None

    @field_validator('doi', mode='before')
    @classmethod
    def doi_format(cls, v):
        return normalize_doi(v)

    @field_validator('pmid')
    @classmethod
    def pmid_format(cls, v):
        if v is not None and not re.fullmatch(r'[1-9]\d*', v):
            raise ValueError('Invalid PMID')
        return v

    @field_validator('publisher_url', 'pubmed_url')
    @classmethod
    def safe_url(cls, v):
        if v is not None and not re.fullmatch(r'https?://[^\s]+', v):
            raise ValueError('Invalid HTTP URL')
        return v

class Finding(StrictModel):
    result: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)

class Analysis(StrictModel):
    clinical_relevance: Literal['direct', 'indirect', 'exclude']
    relevance_reason: str
    primary_category: Category
    tags: list[str]
    species: list[Literal['dog', 'cat']]
    disease_or_topic: str
    study_design: Design
    sample_size: StrictInt | None
    sample_size_quote: str | None
    objective: str | None
    study_methods: str | None = Field(default=None, description='Evidence-based account of population, design, intervention/comparator, follow-up and measured outcomes. Null if not reported.')
    one_sentence_summary: str = Field(description='Legacy field name: write an informative Korean overview, normally 2-4 sentences, with population/design, main numerical outcomes and scope. Do not reduce it to a vague one-liner.')
    key_results: list[Finding]
    authors_conclusion: str | None
    clinical_takeaway: str
    limitations: list[str]
    recommended: StrictBool
    recommendation_reason: str | None

    @field_validator('sample_size')
    @classmethod
    def positive_n(cls, v):
        if v is not None and v <= 0:
            raise ValueError('sample_size must be positive')
        return v

    @field_validator('tags')
    @classmethod
    def allowed_tags(cls, v):
        if any(t not in TAGS for t in v):
            raise ValueError('Unknown tag')
        return list(dict.fromkeys(v))

    @model_validator(mode='after')
    def consistent(self):
        if self.recommended and (not self.recommendation_reason or self.clinical_relevance != 'direct'):
            raise ValueError('Recommendation requires direct relevance and a reason')
        if self.clinical_relevance != 'exclude' and not self.species:
            raise ValueError('Included paper must concern dogs/cats')
        if self.sample_size is not None and not self.sample_size_quote:
            raise ValueError('Sample size requires evidence')
        return self

class Record(StrictModel):
    id: str
    metadata: Metadata
    aliases: list[str]
    discovered_at: datetime
    updated_at: datetime
    status: Literal['pending','processed','failed'] = 'pending'
    attempts: int = 0
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    analysis: Analysis | None = None
    evidence_source: Evidence | None = None
    evidence_url: str | None = None
    evidence_sha256: str | None = None
    summary_generated_at: datetime | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    @model_validator(mode='after')
    def processed_fields(self):
        if self.status == 'processed' and (self.analysis is None or self.evidence_source is None or self.summary_generated_at is None):
            raise ValueError('Processed record lacks analysis/provenance')
        return self

class State(StrictModel):
    version: Literal[1] = 1
    records: list[Record] = Field(default_factory=list)
    last_successful_collection: datetime | None = None
    last_attempt: datetime | None = None
    ai_budget_date: date | None = None
    ai_budget_used: int = 0
