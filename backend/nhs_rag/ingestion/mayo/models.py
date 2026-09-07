from __future__ import annotations

from typing import Literal

from nhs_rag.models import GuideDocument
from pydantic import BaseModel, Field

LICENCE = "Copyright Mayo Foundation for Medical Education and Research. All rights reserved."
INDEX_URL = "https://www.mayoclinic.org/symptom-checker/select-symptom/itt-20009075"
PARSER_VERSION = "mayo-1"


class MayoSource(BaseModel):
    title: str
    url: str
    population: Literal["adult", "child"]

    @property
    def slug(self) -> str:
        return self.url.split("/")[4]


class FactorOption(BaseModel):
    source_id: str
    label: str = Field(min_length=1)


class FactorGroup(BaseModel):
    heading: str = Field(min_length=1)
    options: list[FactorOption] = Field(min_length=1)


class MayoDocument(GuideDocument):
    publisher: Literal["Mayo Clinic"] = "Mayo Clinic"
    licence: str = LICENCE
    parser_version: str = PARSER_VERSION
    schema_version: Literal["1"] = "1"
    symptom_id: str
    population: Literal["adult", "child"]
    factor_groups: list[FactorGroup] = Field(min_length=1)
    acquisition: Literal["http", "browser_snapshot"]
    # Advice is preserved verbatim, without mapping US advice into NHS triage levels.
    urgency_classification: Literal["not_performed"] = "not_performed"
    cause_mapping_status: Literal["not_collected"] = "not_collected"
